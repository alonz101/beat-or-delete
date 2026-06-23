import Foundation

enum AnalyzerError: Error, LocalizedError {
    case pythonNotFound
    case scriptNotFound
    case processFailed(String)
    case parseError(String)

    var errorDescription: String? {
        switch self {
        case .pythonNotFound: return "python3 not found — install via Homebrew"
        case .scriptNotFound: return "analyzer script not found at expected path"
        case .processFailed(let msg): return "Analysis failed: \(msg)"
        case .parseError(let msg): return "Could not parse result: \(msg)"
        }
    }
}

actor AnalyzerService {
    private static var analyzerRoot: String { AppSettings.shared.analyzerRoot }
    private static var analyzerScript: String { "\(analyzerRoot)/core/analyzer.py" }
    private static var batchScript: String { "\(analyzerRoot)/batch.py" }

    // Frozen executables bundled inside the .app (onedir layout: Resources/dj-analyze/dj-analyze)
    private static var bundledAnalyze: String? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let path = res.appendingPathComponent("dj-analyze/dj-analyze").path
        return FileManager.default.fileExists(atPath: path) ? path : nil
    }
    private static var bundledBatch: String? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let path = res.appendingPathComponent("dj-batch/dj-batch").path
        return FileManager.default.fileExists(atPath: path) ? path : nil
    }

    static func analyze(fileURL: URL) async throws -> AnalysisResult {
        let output: String
        if let bin = bundledAnalyze {
            output = try await runProcess(bin, args: [fileURL.path, "--spectrogram"])
        } else {
            let python = try findPython()
            guard FileManager.default.fileExists(atPath: analyzerScript) else {
                throw AnalyzerError.scriptNotFound
            }
            output = try await runProcess(python, args: [analyzerScript, fileURL.path, "--spectrogram"])
        }

        return try decode(output, for: fileURL.lastPathComponent)
    }

    static func runBatch(
        folderURL: URL,
        outputStem: String,
        progress: @escaping (String) -> Void
    ) async throws -> (csv: String, pdf: String) {
        let executable: String
        let args: [String]
        if let bin = bundledBatch {
            executable = bin
            args = [folderURL.path, "--output", outputStem]
        } else {
            let python = try findPython()
            guard FileManager.default.fileExists(atPath: batchScript) else {
                throw AnalyzerError.scriptNotFound
            }
            executable = python
            args = [batchScript, folderURL.path, "--output", outputStem]
        }

        let (_, stderr) = try await runProcessWithStderr(
            executable,
            args: args,
            onStderr: progress
        )

        // Extract paths from stderr output
        var csv = "", pdf = ""
        for line in stderr.components(separatedBy: "\n") {
            if line.hasPrefix("CSV →") { csv = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces) }
            if line.hasPrefix("PDF →") { pdf = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces) }
        }
        return (csv, pdf)
    }

    // MARK: - Private

    private static func findPython() throws -> String {
        // 0. User override
        if let override = AppSettings.shared.effectivePythonPath {
            if FileManager.default.fileExists(atPath: override) { return override }
        }

        let home = ProcessInfo.processInfo.environment["HOME"]
            ?? NSHomeDirectory()

        // 1. Check pyenv versions for one that has librosa installed
        let pyenvVersions = "\(home)/.pyenv/versions"
        if let versions = try? FileManager.default.contentsOfDirectory(atPath: pyenvVersions) {
            for version in versions.sorted().reversed() {
                let candidate = "\(pyenvVersions)/\(version)/bin/python3"
                if FileManager.default.fileExists(atPath: candidate) {
                    // Verify it has librosa (exit 0 = available)
                    if (try? runProcessSync(candidate, args: ["-c", "import librosa"])) != "__FAILED__" {
                        return candidate
                    }
                }
            }
        }

        // 2. Homebrew
        let brewCandidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
        ]
        for path in brewCandidates {
            if FileManager.default.fileExists(atPath: path),
               (try? runProcessSync(path, args: ["-c", "import librosa"])) != "__FAILED__" {
                return path
            }
        }

        // 3. Fallback: pyenv shim (may work if env is set up)
        let shim = "\(home)/.pyenv/shims/python3"
        if FileManager.default.fileExists(atPath: shim) { return shim }

        throw AnalyzerError.pythonNotFound
    }

    private static func decode(_ json: String, for filename: String) throws -> AnalysisResult {
        guard let data = json.data(using: .utf8) else {
            throw AnalyzerError.parseError("empty output for \(filename)")
        }
        do {
            return try JSONDecoder().decode(AnalysisResult.self, from: data)
        } catch {
            throw AnalyzerError.parseError(error.localizedDescription)
        }
    }

    private static func runProcess(_ executable: String, args: [String]) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: executable)
            proc.arguments = args

            // Pass PATH so Python can find ffprobe etc.
            var env = ProcessInfo.processInfo.environment
            env["PATH"] = (env["PATH"] ?? "") + ":/usr/local/bin:/opt/homebrew/bin"
            proc.environment = env

            let pipe = Pipe()
            let errPipe = Pipe()
            proc.standardOutput = pipe
            proc.standardError = errPipe

            do {
                try proc.run()
                proc.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                if proc.terminationStatus != 0 {
                    let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
                    let errMsg = String(data: errData, encoding: .utf8) ?? "unknown error"
                    continuation.resume(throwing: AnalyzerError.processFailed(errMsg))
                } else {
                    continuation.resume(returning: output)
                }
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    private static func runProcessWithStderr(
        _ executable: String,
        args: [String],
        onStderr: @escaping (String) -> Void
    ) async throws -> (stdout: String, stderr: String) {
        try await withCheckedThrowingContinuation { continuation in
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: executable)
            proc.arguments = args

            var env = ProcessInfo.processInfo.environment
            env["PATH"] = (env["PATH"] ?? "") + ":/usr/local/bin:/opt/homebrew/bin"
            proc.environment = env

            let outPipe = Pipe()
            let errPipe = Pipe()
            proc.standardOutput = outPipe
            proc.standardError = errPipe

            do {
                try proc.run()
                proc.waitUntilExit()
                let outData = outPipe.fileHandleForReading.readDataToEndOfFile()
                let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
                let stdout = String(data: outData, encoding: .utf8) ?? ""
                let stderr = String(data: errData, encoding: .utf8) ?? ""
                // Forward stderr lines to progress callback
                for line in stderr.components(separatedBy: "\n") where !line.isEmpty {
                    onStderr(line)
                }
                if proc.terminationStatus != 0 {
                    continuation.resume(throwing: AnalyzerError.processFailed(stderr))
                } else {
                    continuation.resume(returning: (stdout, stderr))
                }
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    // Returns nil on non-zero exit, stdout string on success
    @discardableResult
    private static func runProcessSync(_ executable: String, args: [String]) throws -> String {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = args
        let pipe = Pipe()
        let errPipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = errPipe
        try proc.run()
        proc.waitUntilExit()
        guard proc.terminationStatus == 0 else { return "__FAILED__" }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }
}
