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
    private static var analyzerRoot: String { AppSettings.shared.resolvedAnalyzerRoot }
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

    /// Analyze via the long-lived `dj-analyze --serve` process (imports paid once).
    /// `spectrogram: false` — thumbnails are rendered lazily by the card (T-7), so
    /// a cache-hit file returns in ms with no PNG render.
    static func analyze(fileURL: URL) async throws -> AnalysisResult {
        await configurePersistent()
        return try await PersistentAnalyzer.shared.request(path: fileURL.path, spectrogram: false)
    }

    /// Lazy-start the persistent process. Called on queue interaction (T-5) so the
    /// import cost overlaps with the user reviewing the queue.
    static func warm() async {
        await configurePersistent()
        await PersistentAnalyzer.shared.warm()
    }

    /// Tell the persistent process to exit cleanly (app termination, T-6).
    static func shutdown() async {
        await PersistentAnalyzer.shared.shutdown()
    }

    /// Inject the serve launch command into PersistentAnalyzer. Idempotent —
    /// resolution (bundled binary vs python source) runs lazily at process start.
    private static func configurePersistent() async {
        await PersistentAnalyzer.shared.setLaunchProvider {
            var env = ProcessInfo.processInfo.environment
            env["PATH"] = (env["PATH"] ?? "") + ":/usr/local/bin:/opt/homebrew/bin"
            if let bin = bundledAnalyze {
                return (bin, ["--serve"], env)
            }
            let python = try findPython()
            guard FileManager.default.fileExists(atPath: analyzerScript) else {
                throw AnalyzerError.scriptNotFound
            }
            return (python, [analyzerScript, "--serve"], env)
        }
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

        let (_, stderr) = try await ProcessRunner.runWithStderr(executable, args: args, onStderr: progress)

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
                    if (try? ProcessRunner.runSync(candidate, args: ["-c", "import librosa"])) != "__FAILED__" {
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
               (try? ProcessRunner.runSync(path, args: ["-c", "import librosa"])) != "__FAILED__" {
                return path
            }
        }

        // 3. Fallback: pyenv shim (may work if env is set up)
        let shim = "\(home)/.pyenv/shims/python3"
        if FileManager.default.fileExists(atPath: shim) { return shim }

        throw AnalyzerError.pythonNotFound
    }

}
