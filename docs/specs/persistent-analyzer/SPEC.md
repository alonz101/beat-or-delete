# SPEC: Persistent Analyzer Process

## Problem
The app launches a brand-new `dj-analyze` process for every file
(`AnalyzerService.analyze` → `ProcessRunner.run(bin, [path, "--spectrogram"])`).
Each launch re-imports librosa/numba/scipy/matplotlib from scratch — a fixed
~7–8s cost paid **per file**, regardless of work done. This dwarfs the actual
analysis (~3s) and makes the SQLite cache nearly worthless in the GUI: a cache
hit still pays ~8s of import startup before returning. The cache eliminates
analysis time; it cannot eliminate per-process import time.

## What it does
Run ONE long-lived analyzer process for the app's lifetime. Heavy imports happen
once at startup; thereafter the app sends file paths to the process and reads
results back over a stdin/stdout line protocol. A cache hit then returns in
milliseconds instead of ~8s; a cold analysis returns in ~3s instead of ~11s.

The Python entry point gains a "serve" mode (a read-eval loop over stdin) on top
of its existing one-shot CLI mode. The Swift `AnalyzerService` keeps a persistent
`Process`, writes requests, and reads framed responses.

## Protocol (JSON Lines over a dedicated response fd)
- Request: one compact JSON object per line on the process's stdin:
  `{"id": <int>, "path": "<abs path>", "spectrogram": <bool>}`
- Response: one compact JSON object per line on a DEDICATED response channel
  (see "Clean response channel" below):
  `{"id": <int>, "result": {<analyze result>}}` or
  `{"id": <int>, "error": "<message>"}`
- `id` is echoed so responses can be correlated to requests.
- Responses are compact (no embedded newlines) so one line == one message.
- A `{"cmd": "shutdown"}` line tells the process to exit cleanly.

## Clean response channel (resolves Q3)
The result channel must NOT be polluted by library output. During testing,
`"Matplotlib is building the font cache"` and numba warnings were observed
writing to stdout — these would inject junk lines and desync a naive protocol.
Fix at serve startup, before any heavy import is first exercised:
1. Duplicate the real stdout (fd 1) to a private fd; this private fd is the ONLY
   thing responses are written to (and flushed after every response).
2. Redirect `sys.stdout` / fd 1 to stderr, so every stray `print()`, matplotlib
   message, and numba warning lands on stderr (Swift treats stderr as logs).
3. Swift defensively skips any response line that does not parse as JSON with an
   expected `id`. A stray byte can never wedge the reader.
With a clean dedicated channel, line-delimited compact JSON is safe; no
length-prefix framing in v1.

## Acceptance criteria
- AC-1: `python core/analyzer.py --serve` enters a loop, reads JSON-Lines
  requests from stdin, writes JSON-Lines responses to stdout, one per request.
- AC-2: Serve mode routes every request through `core.cache.get_or_analyze`
  (same cache as one-shot CLI and batch).
- AC-3: Import cost (librosa/numba/etc.) is paid once: the 2nd … Nth request in a
  serve session does not re-import. Measured: 2nd cache-hit request returns in
  < 200 ms (vs ~8s for a fresh process).
- AC-4: One file's analysis raising an exception returns an `error` response for
  that `id` and the process keeps serving subsequent requests (no crash).
- AC-5: One-shot CLI mode (`python core/analyzer.py <file> [--spectrogram]`) and
  batch mode are unchanged and still work.
- AC-6: `AnalyzerService` starts the persistent process lazily and reuses it for
  subsequent files. It is warmed on queue interaction (when files are added to
  the queue), not only on the first analyze — so the import cost overlaps with
  the user reviewing the queue. Opening and closing the app without adding files
  starts no process.
- AC-7: Responses are correlated by `id` — concurrent Swift callers each get their
  own result even if multiple requests are in flight.
- AC-8: The process is told to shut down (or is terminated) when the app exits;
  no orphaned `dj-analyze` processes remain.
- AC-9: Crash policy (supervisor): if the process dies, restart it ONCE and
  re-send the in-flight request whose `id` was lost. If that retry also fails,
  surface the error to the user. The single-retry cap prevents restart loops.
  A transient death (OS kill, broken pipe) recovers silently; a deterministic
  death (a file that always crashes analysis) surfaces after the one retry.
- AC-10: Lazy thumbnail. `analyze` requests use `spectrogram: false`, so a
  cache-hit file returns in ms with no PNG render. The report card renders its
  thumbnail spectrogram on-demand when the card appears (reusing the existing
  on-demand spectrogram path), caching the rendered image in the item's view
  state so it is not re-rendered on every redraw. No thumbnail render happens for
  files the user never scrolls to.

## Constraints
- No new pip dependencies (json + sys stdin loop are stdlib).
- The frozen PyInstaller bundle must support `--serve` (same binary, new flag) —
  no second executable.
- Serve mode must flush stdout after each response or Swift will block waiting.
- Backpressure / ordering: the server processes requests sequentially in v1
  (one worker). `id` correlation still required so Swift logic is order-independent.
- Spectrogram generation is never cached (unchanged from AC-6 of sqlite-cache).
  Per the lazy-thumbnail decision below, `analyze` requests run with
  `spectrogram: false`; thumbnails are rendered on-demand by the card view.

## Out of scope
- Parallel analysis inside the serve loop (thread pool in the server). v1 is
  sequential; batch.py keeps its own ThreadPoolExecutor for bulk runs.
- Switching batch.py to the persistent process (batch already amortizes startup
  across a folder in one process; leave it as-is).
- A socket/IPC transport (stdin/stdout pipes are sufficient and simplest).
- Progress streaming for a single file's analysis.

## Resolved decisions
- Q1 (lifecycle): lazy + warm on queue interaction. No process until files are
  added; import overlaps with queue review. See AC-6.
- Q2 (crash policy): restart once, re-send the lost in-flight request, surface on
  second failure. See AC-9.
- Q3 (framing): dedicated response fd + line-delimited compact JSON; redirect all
  library output to stderr; Swift skips non-JSON lines. See "Clean response
  channel". No length-prefix in v1.
- Q4 (thumbnail): lazy — analyze runs with `spectrogram: false`; the card renders
  its thumbnail on-demand and caches the image in view state. See AC-10. This is
  what makes cache hits feel near-instant instead of render-bound.
