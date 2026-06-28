import Foundation

/// Long-lived `dj-analyze --serve` process. Heavy Python imports are paid once;
/// each request is a JSON-Lines round-trip over stdin/stdout.
///
/// Protocol (see core/analyzer.py --serve):
///   request  (stdin):  {"id": <int>, "path": "<abs>", "spectrogram": <bool>}
///   response (stdout): {"id": <int>, "result": {...}}  or  {"id": <int>, "error": "..."}
///   shutdown (stdin):  {"cmd": "shutdown"}
/// Library noise (matplotlib/numba) is redirected to stderr by the child, so
/// stdout carries only response lines.
///
/// Decisions (PLAN): singleton; sequential dispatch (one request in flight at a
/// time, matching the sequential server); restart-once crash supervisor.
actor PersistentAnalyzer {
    static let shared = PersistentAnalyzer()

    enum PersistentError: Error, LocalizedError {
        case notConfigured
        case processDied
        case parseError(String)
        case serverError(String)

        var errorDescription: String? {
            switch self {
            case .notConfigured: return "PersistentAnalyzer launch command not configured"
            case .processDied: return "Analyzer process died"
            case .parseError(let m): return "Could not parse analyzer response: \(m)"
            case .serverError(let m): return m
            }
        }
    }

    /// Supplies the launch command, e.g. (`.../dj-analyze`, ["--serve"]) or
    /// (python, [".../core/analyzer.py", "--serve"]). Injected by AnalyzerService
    /// so this type stays decoupled from bundle/python resolution.
    private var launchProvider: (() throws -> (executable: String, args: [String], env: [String: String]))?

    private var process: Process?
    private var stdin: FileHandle?
    private var outPipe: Pipe?
    private var errPipe: Pipe?
    private var nextID = 0
    private var pending: [Int: CheckedContinuation<Data, Error>] = [:]

    /// Tail of the serial request chain — enforces one-in-flight dispatch.
    /// Retains `self`, but `self` is the `.shared` singleton so the cycle is benign.
    private var tail: Task<AnalysisResult, Error>?

    /// Set once shutdown begins; prevents the crash supervisor from resurrecting a
    /// child during teardown (which would orphan it and cross-resume a retry).
    private var isShuttingDown = false

    func setLaunchProvider(
        _ provider: @escaping () throws -> (executable: String, args: [String], env: [String: String])
    ) {
        self.launchProvider = provider
    }

    /// Start the process if not already running (lazy warm). Safe to call repeatedly.
    func warm() {
        try? ensureRunning()
    }

    /// Analyze a file through the persistent process. Requests are serialized so
    /// only one is in flight at a time (matches the sequential server, simplifies
    /// the crash supervisor).
    func request(path: String, spectrogram: Bool) async throws -> AnalysisResult {
        let predecessor = tail
        let task = Task { () throws -> AnalysisResult in
            // Wait for the previous request to finish (ignore its outcome).
            _ = try? await predecessor?.value
            return try await self.send(path: path, spectrogram: spectrogram, isRetry: false)
        }
        tail = task
        return try await task.value
    }

    /// Tell the process to exit cleanly, then tear down. Called on app termination.
    func shutdown() {
        isShuttingDown = true
        if let stdin = stdin {
            let line = "{\"cmd\":\"shutdown\"}\n"
            try? stdin.write(contentsOf: Data(line.utf8))
        }
        clearHandlers()
        process?.terminate()
        process = nil
        stdin = nil
        // Fail any in-flight request. The isShuttingDown guard in send() ensures
        // this does NOT trigger a restart, so no orphan child is created.
        failAllPending(PersistentError.processDied)
    }

    // MARK: - Core send + crash supervisor

    private func send(path: String, spectrogram: Bool, isRetry: Bool) async throws -> AnalysisResult {
        do {
            try ensureRunning()
            let id = nextID
            nextID += 1

            let req: [String: Any] = ["id": id, "path": path, "spectrogram": spectrogram]
            let reqData = try JSONSerialization.data(withJSONObject: req)
            var line = reqData
            line.append(0x0A) // newline

            let respData: Data = try await withCheckedThrowingContinuation { cont in
                pending[id] = cont
                guard let stdin = stdin else {
                    pending[id] = nil
                    cont.resume(throwing: PersistentError.processDied)
                    return
                }
                do {
                    try stdin.write(contentsOf: line)
                } catch {
                    pending[id] = nil
                    cont.resume(throwing: PersistentError.processDied)
                }
            }
            return try decode(respData)
        } catch {
            // Restart-once supervisor: a transient death recovers silently; a
            // second failure surfaces. Only retry process-death, not server/parse
            // errors (those are deterministic). Never retry during shutdown — that
            // would resurrect a child and orphan it (AC-8).
            if !isRetry, !isShuttingDown, isProcessDeath(error) {
                teardownDeadProcess()
                return try await send(path: path, spectrogram: spectrogram, isRetry: true)
            }
            throw error
        }
    }

    private func isProcessDeath(_ error: Error) -> Bool {
        if case PersistentError.processDied = error { return true }
        return false
    }

    // MARK: - Process lifecycle

    private func ensureRunning() throws {
        if isShuttingDown { throw PersistentError.processDied }
        if let p = process, p.isRunning { return }
        guard let provider = launchProvider else { throw PersistentError.notConfigured }
        let (executable, args, env) = try provider()

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = args
        proc.environment = env

        let inPipe = Pipe()
        let outPipe = Pipe()
        let errPipe = Pipe()
        proc.standardInput = inPipe
        proc.standardOutput = outPipe
        proc.standardError = errPipe

        // Background reader. The readabilityHandler is invoked serially by
        // Foundation for a single FileHandle, so the LineBuffer (order-sensitive
        // assembly) is touched on one thread only. Per-line routing is then
        // dispatched to the actor — order-independent since each line carries its
        // own id and resumes its own continuation.
        let lineBuffer = LineBuffer()
        outPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let chunk = handle.availableData
            guard !chunk.isEmpty else { return }
            for line in lineBuffer.feed(chunk) {
                Task { await self?.route(line) }
            }
        }
        // Drain stderr so the pipe never fills and blocks the child (logs only).
        errPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }
        // On death, fail every outstanding request so awaiting callers can retry.
        proc.terminationHandler = { [weak self] _ in
            Task { await self?.handleTermination() }
        }

        try proc.run()
        self.process = proc
        self.stdin = inPipe.fileHandleForWriting
        self.outPipe = outPipe
        self.errPipe = errPipe
    }

    /// Detach readability/termination handlers so they stop firing on a dead pipe
    /// and release their captured LineBuffer/self closures.
    private func clearHandlers() {
        outPipe?.fileHandleForReading.readabilityHandler = nil
        errPipe?.fileHandleForReading.readabilityHandler = nil
        process?.terminationHandler = nil
        outPipe = nil
        errPipe = nil
    }

    private func teardownDeadProcess() {
        clearHandlers()
        process?.terminate()
        process = nil
        stdin = nil
        failAllPending(PersistentError.processDied)
    }

    private func handleTermination() {
        // Process exited (crash or shutdown). Fail any in-flight request; the
        // supervisor in send() turns that into a single restart+retry.
        failAllPending(PersistentError.processDied)
        if let p = process, !p.isRunning {
            process = nil
            stdin = nil
        }
    }

    // MARK: - Response parsing

    private func route(_ lineData: Data) {
        // Clean-channel defense: skip anything that isn't a JSON object with an id.
        guard
            let obj = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
            let id = obj["id"] as? Int,
            let cont = pending.removeValue(forKey: id)
        else {
            return
        }
        if let result = obj["result"] {
            // Re-serialize just the result object for AnalysisResult decoding.
            if let resultData = try? JSONSerialization.data(withJSONObject: result) {
                cont.resume(returning: resultData)
            } else {
                cont.resume(throwing: PersistentError.parseError("result re-encode failed"))
            }
        } else if let message = obj["error"] as? String {
            cont.resume(throwing: PersistentError.serverError(message))
        } else {
            cont.resume(throwing: PersistentError.parseError("response missing result/error"))
        }
    }

    private func decode(_ data: Data) throws -> AnalysisResult {
        do {
            return try JSONDecoder().decode(AnalysisResult.self, from: data)
        } catch {
            throw PersistentError.parseError(error.localizedDescription)
        }
    }

    private func failAllPending(_ error: Error) {
        let conts = pending
        pending.removeAll()
        for (_, cont) in conts {
            cont.resume(throwing: error)
        }
    }
}

/// Accumulates stdout bytes and emits complete newline-delimited lines, in order.
/// Touched only from a single FileHandle.readabilityHandler (serial), so it needs
/// no internal locking.
private final class LineBuffer {
    private var data = Data()

    func feed(_ chunk: Data) -> [Data] {
        data.append(chunk)
        var lines: [Data] = []
        while let nl = data.firstIndex(of: 0x0A) {
            lines.append(data.subdata(in: data.startIndex..<nl))
            data.removeSubrange(data.startIndex...nl)
        }
        return lines
    }
}
