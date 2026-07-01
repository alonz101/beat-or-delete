import Foundation

/// Searches the SQLite cache by filename substring via the frozen `dj-analyze --history`
/// CLI, decoding a JSON array of reverdicted results. No FFT runs — search is a cheap
/// read + reverdict — so no concurrency gate is needed (unlike AnalyzerService.analyze).
enum HistoryService {
    // Replicated from AnalyzerService to keep file ownership disjoint (no edit to
    // AnalyzerService.swift). Factoring a shared executable resolver is a later refactor.
    private static var analyzerRoot: String { AppSettings.shared.resolvedAnalyzerRoot }
    private static var analyzerScript: String { "\(analyzerRoot)/core/analyzer.py" }

    private static var bundledAnalyze: String? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let path = res.appendingPathComponent("dj-analyze/dj-analyze").path
        return FileManager.default.fileExists(atPath: path) ? path : nil
    }

    static func search(query: String, limit: Int = 10) async throws -> [AnalysisResult] {
        let output: String
        if let bin = bundledAnalyze {
            output = try await ProcessRunner.run(bin, args: ["--history", query, "--limit", String(limit)])
        } else {
            let python = try findPython()
            guard FileManager.default.fileExists(atPath: analyzerScript) else {
                throw AnalyzerError.scriptNotFound
            }
            output = try await ProcessRunner.run(python, args: [analyzerScript, "--history", query, "--limit", String(limit)])
        }
        return try decode(output)
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

    private static func decode(_ json: String) throws -> [AnalysisResult] {
        let trimmed = json.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty || trimmed == "[]" { return [] }
        guard let data = trimmed.data(using: .utf8) else {
            throw AnalyzerError.parseError("empty history output")
        }
        do {
            return try JSONDecoder().decode([AnalysisResult].self, from: data)
        } catch {
            throw AnalyzerError.parseError(error.localizedDescription)
        }
    }
}
