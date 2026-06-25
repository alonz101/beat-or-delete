import Foundation

enum SpectrogramError: Error, LocalizedError {
    case generationFailed(String)
    case parseError
    case pythonNotFound

    var errorDescription: String? {
        switch self {
        case .generationFailed(let msg): return "Spectrogram failed: \(msg)"
        case .parseError: return "Could not parse spectrogram output"
        case .pythonNotFound: return "python3 not found — install via Homebrew"
        }
    }
}

enum SpectrogramService {
    private static var spectrogramScript: String {
        "\(AppSettings.shared.resolvedAnalyzerRoot)/core/spectrogram_cli.py"
    }

    private static var bundledBin: String? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let path = res.appendingPathComponent("dj-spectrogram/dj-spectrogram").path
        return FileManager.default.fileExists(atPath: path) ? path : nil
    }

    static func generateFull(
        filePath: String,
        humHz: Double?,
        clipTimes: [Double]
    ) async throws -> String {
        var args = [filePath]
        if let hum = humHz {
            args += ["--hum-hz", String(hum)]
        }
        if !clipTimes.isEmpty {
            args += ["--clip-times", clipTimes.map { String($0) }.joined(separator: ",")]
        }

        let output: String
        if let bin = bundledBin {
            output = try await ProcessRunner.run(bin, args: args)
        } else {
            let python = try findPython()
            output = try await ProcessRunner.run(python, args: [spectrogramScript] + args)
        }

        guard let data = output.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: String],
              let path = json["spectrogram_path"] else {
            throw SpectrogramError.parseError
        }
        return path
    }

    // MARK: - Private

    private static func findPython() throws -> String {
        if let override = AppSettings.shared.effectivePythonPath,
           FileManager.default.fileExists(atPath: override) { return override }

        let home = ProcessInfo.processInfo.environment["HOME"] ?? NSHomeDirectory()
        let pyenvVersions = "\(home)/.pyenv/versions"
        if let versions = try? FileManager.default.contentsOfDirectory(atPath: pyenvVersions) {
            for version in versions.sorted().reversed() {
                let candidate = "\(pyenvVersions)/\(version)/bin/python3"
                if FileManager.default.fileExists(atPath: candidate),
                   (try? ProcessRunner.runSync(candidate, args: ["-c", "import librosa"])) != "__FAILED__" {
                    return candidate
                }
            }
        }
        for path in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"] {
            if FileManager.default.fileExists(atPath: path),
               (try? ProcessRunner.runSync(path, args: ["-c", "import librosa"])) != "__FAILED__" {
                return path
            }
        }
        throw SpectrogramError.pythonNotFound
    }
}
