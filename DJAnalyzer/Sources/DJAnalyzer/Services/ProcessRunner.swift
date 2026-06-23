import Foundation

enum ProcessRunnerError: Error {
    case processFailed(String)
}

struct ProcessRunner {
    static func run(_ executable: String, args: [String]) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            let proc = makeProcess(executable, args: args)
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
                    continuation.resume(throwing: ProcessRunnerError.processFailed(errMsg))
                } else {
                    continuation.resume(returning: output)
                }
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    static func runWithStderr(
        _ executable: String,
        args: [String],
        onStderr: @escaping (String) -> Void
    ) async throws -> (stdout: String, stderr: String) {
        try await withCheckedThrowingContinuation { continuation in
            let proc = makeProcess(executable, args: args)
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
                for line in stderr.components(separatedBy: "\n") where !line.isEmpty {
                    onStderr(line)
                }
                if proc.terminationStatus != 0 {
                    continuation.resume(throwing: ProcessRunnerError.processFailed(stderr))
                } else {
                    continuation.resume(returning: (stdout, stderr))
                }
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    @discardableResult
    static func runSync(_ executable: String, args: [String]) throws -> String {
        let proc = makeProcess(executable, args: args)
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

    private static func makeProcess(_ executable: String, args: [String]) -> Process {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = (env["PATH"] ?? "") + ":/usr/local/bin:/opt/homebrew/bin"
        proc.environment = env
        return proc
    }
}
