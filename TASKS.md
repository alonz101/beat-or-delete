# Task Ledger

Persistent execution state — survives context resets. Re-read this before doing anything after a compaction or restart.

## Active features

### sqlite-cache · branch: `feat/sqlite-cache` · worktree: `.claude/worktrees/sqlite-cache`
SPEC: `docs/specs/sqlite-cache/SPEC.md` · PLAN: `docs/specs/sqlite-cache/PLAN.md`

| # | Wave | File | Status |
|---|------|------|--------|
| T-1 | W1 | `core/config_hash.py` (new) — CONFIG_HASH via introspection of UPPERCASE consts | DONE |
| T-2 | W1 | `core/reverdict.py` (new) — reverdict_from_raw(raw) → verdict dict | DONE |
| T-3 | W2 | `core/cache.py` (new) — schema, get_or_analyze(), invalidate() | DONE |
| T-4 | W3 | `core/analyzer.py` — add analyze_raw(); CLI block calls get_or_analyze | DONE |
| T-5 | W3 | `batch.py:46` — swap analyze → get_or_analyze | DONE |

**Decisions locked:**
- Q1: add `analyze_raw(path) -> (raw_components, assembled_result)`; `analyze()` delegates to it
- Q2: hash all UPPERCASE constants; FFT param change requires manual cache.db deletion
- Q3: WAL mode + sidecars OK

**Status:** merged to main + pushed. Hotfix `0ff46ec`: cache.py json.dumps needed numpy_to_native (crashed on real float32 — tests used fake dicts so missed it).

### persistent-analyzer · branch: `feat/persistent-analyzer` · worktree: `.claude/worktrees/persistent-analyzer`
SPEC: `docs/specs/persistent-analyzer/SPEC.md` · PLAN: `docs/specs/persistent-analyzer/PLAN.md`

| # | Wave | File | Status |
|---|------|------|--------|
| T-1 | W1 | `core/analyzer.py` — `--serve` mode: fd-redirect + read-eval loop → get_or_analyze | DONE |
| T-2 | W1 | `build/analyzer.spec` — verify frozen binary supports `--serve` (read-only) | DONE (frozen --serve verified: 2 clean responses, no noise leak, fd-redirect survives PyInstaller; Q2 resolved) |
| T-3 | W2 | `PersistentAnalyzer.swift` (new) — actor, Process+pipes, id-correlation, crash supervisor | DONE (review r2 APPROVE; shutdown-race orphan bug caught+fixed) |
| T-4 | W3 | `AnalyzerService.swift` — route analyze → persistent, `spectrogram: false` | DONE |
| T-5 | W3 | `AppViewModel.swift` — warm process on addURLs | DONE |
| T-6 | W3 | `DJAnalyzerApp.swift` — shutdown hook (AppDelegate) | DONE (review caught @MainActor deadlock → Task.detached) |
| T-7 | W3 | `ReportCardView.swift` — lazy thumbnail on card appear, cached in @State | DONE (D-2 logged: re-spawn on scroll, no concurrency cap) |

**Decisions locked:**
- Q1: `PersistentAnalyzer.shared` singleton; AnalyzerService statics = thin wrappers
- Q2: verify fd mapping in W1 (responses on stdout, noise on stderr)
- Q3: lazy thumbnail — analyze runs `spectrogram:false`; card renders on-demand (AC-10)
- Q4: AppDelegate via NSApplicationDelegateAdaptor for shutdown
- Q5: sequential Swift dispatch (one request in flight, matches sequential server)
- Tests MUST use real audio (tiny generated WAV + 1 real-file smoke) — NOT monkeypatched analyze

## Fixes

### lazy-imports · branch: `feat/persistent-analyzer` · worktree: `.claude/worktrees/persistent-analyzer`
Goal: cache HIT / reverdict must NOT load librosa/matplotlib → fast per-track startup (~7.5s floor today is pure import). Heavy libs load only on cache MISS (real analysis). Preserves two-layer cache (raw by file, verdict by config_hash → threshold change = reverdict w/o re-FFT).

| # | File | What | Status |
|---|------|------|--------|
| L-1 | `tests/test_lazy_import.py` (new) | RED: importing core.cache stays light; cache hit & reverdict don't load librosa/matplotlib; miss still works+loads | DONE |
| L-2 | `core/analyzer.py`, `core/cache.py` | GREEN: heavy imports moved into functions; lazy delegators keep test_wireup monkeypatch working | DONE (review APPROVE) |

**VALIDATED on frozen binary:** startup floor 7.47s→0.13s; cache hit 7.67s→**0.13s**; cold miss ~14.6s→~2.4s. (First-ever analysis ~55s once = numba JIT, then cached to disk.) Memory unchanged (per-track + cap=3).

## Log
<!-- newest first -->
