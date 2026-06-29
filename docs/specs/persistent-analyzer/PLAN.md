# PLAN: Persistent Analyzer Process

## Overview
Replace per-file process spawning (each pays ~7–8s of librosa/numba/scipy/matplotlib import) with ONE long-lived `dj-analyze --serve` process. Heavy imports happen once at startup; thereafter the app pushes `{id, path, spectrogram}` requests over stdin and reads `{id, result|error}` responses over a dedicated, library-noise-free fd. The Python serve loop routes every request through `core.cache.get_or_analyze` (cache hit → ms, cold → ~3s). The Swift `AnalyzerService` actor owns the persistent process: lazy start, id-correlated request/response map, single-retry crash supervisor, and clean shutdown on app exit. One-shot CLI and batch.py are untouched. No new pip deps; same frozen binary, new flag.

## Waves
Wave 1 — Python serve protocol: Add `--serve` mode to `core/analyzer.py` (fd redirect + read-eval loop) and confirm the frozen binary still builds. Fully testable end-to-end by piping JSON Lines into the process stdin and reading the response fd — no Swift required. Ships the contract everything else codes against (AC-1,2,3,4,5).

Wave 2 — Swift persistent transport: Add a long-lived process runner (`PersistentAnalyzer`) with id-correlation + crash supervisor, separate from the one-shot `ProcessRunner` (AC-7,9). Codes against Wave-1's frozen protocol, not against Wave-3 callers.

Wave 3 — Swift wiring & lifecycle: Switch `AnalyzerService.analyze` to use the persistent transport, warm on queue interaction in `AppViewModel.addURLs`, shut down on app exit in `DJAnalyzerApp` (AC-6,8). Depends on Wave 2's transport API.

Each wave is independently testable: Wave 1 via piped stdin/stdout, Wave 2 via a Python protocol-echo harness, Wave 3 via manual GUI verification.

## Tasks
| # | Wave | File | What | Touches AC |
|---|------|------|------|------------|
| T-1 | 1 | `core/analyzer.py` | Add `--serve` branch in `__main__`: redirect fds, then read-eval loop over stdin calling `core.cache.get_or_analyze`, write compact JSON responses to the saved fd, flush each. Per-request try/except so one bad file can't kill the loop. `{"cmd":"shutdown"}` breaks. One-shot path unchanged. | AC-1,2,3,4,5 |
| T-2 | 1 | `build/analyzer.spec` (verify only — read-only check, no edit expected) | Confirm `--serve` rides the existing frozen binary; spec lists no entry-point change needed. Flag if a `hiddenimports`/`runtime_hook` change is actually required. | AC-5 (constraint: same binary) |
| T-3 | 2 | `DJAnalyzer/Sources/DJAnalyzer/Services/PersistentAnalyzer.swift` (NEW) | `actor`/class holding `Process`, request `Pipe`, response `Pipe`; monotonic id counter; `[id: CheckedContinuation]` map; background line-reader splitting on `\n`, JSON-parsing, resuming matching continuation; skips non-JSON/unknown-id lines. `request(path:spectrogram:) async throws -> Data` (returns the raw `result` object). `start()`, `shutdown()`. Crash supervisor: on process death restart once + re-send the lost in-flight request; 2nd failure throws. | AC-7,9 (clean-channel defense for AC-1) |
| T-4 | 3 | `DJAnalyzer/Sources/DJAnalyzer/Services/AnalyzerService.swift` | `analyze(fileURL:)` calls the shared `PersistentAnalyzer` with `spectrogram: false`, unwraps `{id,result}` → decodes `AnalysisResult`. Add `warm()` (lazy start) and `shutdown()` passthroughs. Leave `runBatch`, `findPython`, `bundled*`, one-shot helpers intact. | AC-6,8,10 |
| T-5 | 3 | `DJAnalyzer/Sources/DJAnalyzer/ViewModels/AppViewModel.swift` | At TOP of `addURLs` (after files computed, before per-item `analyzeItem` loop) call `Task { await AnalyzerService.shared.warm() }` so imports overlap with dispatch. No warm if no files added. | AC-6 |
| T-6 | 3 | `DJAnalyzer/Sources/DJAnalyzer/DJAnalyzerApp.swift` | Wire app-termination hook (`NSApplicationDelegateAdaptor` + `applicationWillTerminate`) to call `AnalyzerService.shared.shutdown()` → sends `{"cmd":"shutdown"}` and/or terminates the process. No orphans. | AC-8 |
| T-7 | 3 | `DJAnalyzer/Sources/DJAnalyzer/Views/ReportCardView.swift` | Lazy thumbnail: card no longer reads `result.spectrogramPath` directly. On `.task`/`.onAppear`, call `SpectrogramService` (the existing on-demand `dj-spectrogram` path) to render the thumbnail once, store the `NSImage` in `@State`, and show a placeholder/spinner until ready. Render once per card (guard against re-render on redraw). Disjoint from T-4/5/6. | AC-10 |

Note: T-4/T-5/T-6 all live in Wave 3 and touch disjoint files (Service, ViewModel, App). T-3 introduces a NEW file so it never collides with the existing one-shot `ProcessRunner.swift`. AnalyzerService is currently all-`static`; introducing a shared persistent instance (`AnalyzerService.shared` or a `PersistentAnalyzer.shared` singleton) is a small interface decision — see Open Questions Q1.

## Interface contracts

### JSON Lines protocol (compact, one object per line, no embedded newlines)
Request (written to child **stdin**):
```json
{"id": 1, "path": "/abs/path/file.flac", "spectrogram": true}
```
Shutdown request:
```json
{"cmd": "shutdown"}
```
Response (read from the child's **dedicated response fd**, NOT stdout):
```json
{"id": 1, "result": { ...full analyze() dict, same shape as one-shot... }}
```
or
```json
{"id": 1, "error": "File not found: /abs/path/file.flac"}
```
- `id` is echoed verbatim for correlation. Monotonic int from Swift.
- Responses serialized with `json.dumps(resp, default=numpy_to_native)` — **mandatory** (omitting it crashed on float32; see commit `0ff46ec`). Compact separators, then `+ "\n"`, then flush.
- `result` payload is byte-identical in shape to current one-shot output, so `AnalysisResult` decoding is unchanged after Swift unwraps the `result` key.

### Python `--serve` (in `core/analyzer.py` `__main__`)
```python
if "--serve" in sys.argv:
    import os
    # 1. Establish clean response channel BEFORE heavy imports/library noise.
    saved_fd = os.dup(1)            # private copy of real stdout
    os.dup2(2, 1)                   # fd 1 (and C-level stdout) now → stderr
    sys.stdout = sys.stderr        # stray Python print()/warnings → stderr
    resp = os.fdopen(saved_fd, "w", buffering=1)  # responses ONLY here

    import core.cache              # triggers heavy imports once
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue               # skip junk
        if req.get("cmd") == "shutdown":
            break
        rid = req.get("id")
        try:
            r = core.cache.get_or_analyze(req["path"],
                                          with_spectrogram=req.get("spectrogram", False))
            out = {"id": rid, "result": r}
        except Exception as e:
            out = {"id": rid, "error": str(e)}
        resp.write(json.dumps(out, default=numpy_to_native,
                              separators=(",", ":")) + "\n")
        resp.flush()
    sys.exit(0)
```
fd-redirection order is load-bearing: dup(1) → dup2(2,1) → reassign `sys.stdout` → open writer on the saved fd → only THEN import heavy libs. One-shot path (`sys.argv[1]` is a file) stays exactly as today.

### Swift `PersistentAnalyzer` (NEW file, Wave 2)
```swift
actor PersistentAnalyzer {
    func warm() async                                  // lazy start if not running
    func request(path: String, spectrogram: Bool) async throws -> AnalysisResult
    func shutdown()                                    // send {"cmd":"shutdown"} then terminate
}
```
- Holds `Process`, `inputPipe` (stdin write), `outputPipe` (response fd — the child's fd 1, captured as the Process's `standardOutput`; child stderr captured separately and ignored/logged). Map: `private var pending: [Int: CheckedContinuation<AnalysisResult, Error>]`. Monotonic `private var nextID = 0`.
- Background reader reads `outputPipe` `fileHandleForReading`, buffers, splits on `\n`; for each line tries `JSONDecoder`/`JSONSerialization` for `{id,result|error}`; on match resumes & removes the continuation; non-JSON / unknown id → skip (clean-channel defense, AC-1).
- Crash supervisor (AC-9): on `terminationHandler` or write/read failure, if exactly one request was in flight, `start()` once and re-`request()` it; a 2nd failure resumes that continuation `throwing`. One restart per request (cap prevents loops).
- **fd mapping note:** the child redirects responses to *its own fd 1* (`saved_fd` is the pre-redirect stdout = the pipe Swift attached as `standardOutput`). So Swift reads responses from `process.standardOutput` and reads noise from `process.standardError`. Verify this mapping holds in Wave 1 before Wave 2 builds on it (Open Question Q2).

## Test plan
Bugsy: Python serve mode is unit/integration-testable headlessly; the Swift actor largely needs manual GUI verification plus a protocol-level integration harness.

### Fixtures — MUST use REAL audio through the REAL pipeline
The sqlite-cache float32 bug (commit `0ff46ec`) escaped because tests monkeypatched
`analyze()` to return hand-written Python dicts — real numpy types never reached
`json.dumps`. Serve-mode tests MUST NOT repeat this: they run requests through the
real `core.cache.get_or_analyze` → real librosa/FFT → real numpy float32 outputs.
Two-tier fixtures:
1. **Tiny generated WAV** (pytest fixture): write a ~2s sine wave with
   `soundfile.write(tmp, numpy_signal, 44100)`. Real audio, real pipeline,
   produces genuine numpy scalars, runs in well under a second of analysis. This
   is the primary fixture for AC-1/2/3/4/7 — it exercises the float32 path that
   the previous suite missed.
2. **One real-file smoke test** against `test files/Departure.mp3` (smallest real
   file, 21 MB MP3): confirms real-world container/format/size works end-to-end
   through the frozen `dj-analyze --serve` binary (AC-5 bundle check). Keep this to
   a single test — each frozen-binary spawn pays ~8s import.
Do NOT monkeypatch `get_or_analyze` or the check modules in serve-mode tests; the
whole point is to verify the real serialization path. (A spy/counter on
`get_or_analyze` for AC-2 is fine — wrap, don't replace.)

- **AC-1 (serve loop / JSON Lines):** Spawn `python core/analyzer.py --serve`, write two request lines, assert exactly two response lines on the response fd, each valid compact JSON with matching `id`. (Headless integration test — pty/subprocess.)
- **AC-2 (routes through cache):** Monkeypatch / spy `core.cache.get_or_analyze`; assert serve calls it once per request with `(path, with_spectrogram=...)`.
- **AC-3 (imports paid once):** Time a 2nd request for an already-cached file over an already-running serve process; assert < 200 ms. Contrast with a fresh one-shot invocation (~8s) to prove the saving.
- **AC-4 (bad file doesn't kill loop):** Send a request for a missing/corrupt file → assert an `{"id","error"}` response, then send a valid request on the SAME process → assert it still answers. Process stays alive.
- **AC-5 (CLI/batch unchanged):** Run `python core/analyzer.py <file>` and `python core/analyzer.py <file> --spectrogram` → unchanged JSON on stdout; run `batch.py <folder>` → unchanged CSV/PDF. Also build the frozen binary and run `dj-analyze --serve` to confirm the bundle supports the flag (AC-5 constraint).
- **AC-6 (lazy + warm on queue):** Manual GUI: open & close app without adding files → assert no `dj-analyze --serve` process spawned (Activity Monitor / `pgrep`). Add files → assert process starts at `addURLs` time, before per-item analyze completes. Reuse: add a 2nd batch → same pid.
- **AC-7 (id correlation):** Headless: fire N concurrent requests with distinct ids/paths into one serve process; assert each response's `result.file_path` matches the path sent for that id (no cross-talk). Swift-side: unit-test the id map if extractable; otherwise cover via the Python harness.
- **AC-8 (shutdown / no orphans):** Manual GUI: quit app → assert serve process exits (no orphan via `pgrep dj-analyze`). Headless: send `{"cmd":"shutdown"}` → process exits 0.
- **AC-9 (crash supervisor):** Headless harness simulating Swift logic OR manual: kill the serve process mid-request → assert AnalyzerService restarts once and re-sends the in-flight request and returns a result. Force a 2nd failure → assert error surfaces to caller, no infinite restart loop. (This is the hardest to test without an app harness — call out as primarily manual + a focused Python-level fault-injection test of restart-once semantics.)

Testable headlessly: AC-1,2,3,4,5,7,8 (Python protocol). Needs manual GUI: AC-6,8(app side),9(app side). The Swift continuation map / crash supervisor logic should be factored to allow at least a smoke test driving `PersistentAnalyzer.request` against the real frozen binary from a tiny Swift test or CLI harness.

## Resolved decisions (was Open Questions)
1. Singleton: `PersistentAnalyzer.shared`; `AnalyzerService` statics stay thin wrappers (smallest diff). RESOLVED.
2. fd mapping: verify IN Wave 1 (T-1) that responses arrive on the child's pre-redirect fd 1 == Swift's `process.standardOutput`, and library noise on `standardError`. If PyInstaller's bootloader touches fd 1 before our redirect, fall back to an explicit fd passed via env. Verification step, not a blocker. RESOLVED (verify-in-wave).
3. Thumbnail: LAZY. `analyze` runs `spectrogram: false`; `ReportCardView` renders the thumbnail on-demand via `SpectrogramService` and caches the image in `@State` (T-7, AC-10). RESOLVED.
4. Shutdown: add a minimal `AppDelegate` via `NSApplicationDelegateAdaptor` + `applicationWillTerminate` (T-6). RESOLVED.
5. Restart-once scope: Swift dispatch is SEQUENTIAL in v1 to match the sequential server, so exactly one request is ever in flight at crash time — supervisor re-sends that one (T-3, AC-9). RESOLVED.
