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

### configurable-thresholds (#7) · branch: `feat/configurable-thresholds` · worktree: `.claude/worktrees/configurable-thresholds`
SPEC: `docs/specs/configurable-thresholds/SPEC.md` · PLAN: `docs/specs/configurable-thresholds/PLAN.md`

| # | Wave | File | Status |
|---|------|------|--------|
| T-1 | W1 | `core/runtime_config.py` (new) — overlay thresholds.json on defaults; active()/load_overrides()/test hooks | DONE (review r1 BLOCK: _coerce crashed on non-coercible value → per-key guard; +regression tests. 64 suite green) |
| T-2 | W2 | `core/config_hash.py` — fold active overrides into hash | DONE (review r1 APPROVE; 6 cache-invariants verified) |
| T-3 | W2 | `core/checks/spectral.py` + `flags.py` — move FAKE_LOSSLESS/SUSPECT into flags (classify_coverage), call-time cfg reads; golden regression (HIGH RISK) | DONE (review r1 APPROVE 3ccae6f; 44/44, golden byte-identical, strict <, 17 knobs via cfg) |
| T-4 | W3 | `core/analyzer.py` + `core/cache.py` — derive spectral_verdict at assembly via classify_coverage | DONE (review r1 APPROVE 89986a1; both seams identical, lazy-import intact, AC-4 genuine). Side-fix: stale "OK" fixture in test_cache → GENUINE (55535f5) |
| T-5 | W4 | `AppSettings.swift` + `ThresholdCatalog.swift` (new) — override map, catalog, thresholds.json writer | DONE (Wave-4 review APPROVE 468382c) |
| T-6 | W4 | `SettingsView.swift` + `DJAnalyzerApp.swift` + `ContentView.swift` — Config tab, validation, Reset, shared vm injection | DONE (Wave-4 review APPROVE 468382c) |
| T-7 | W4 | `AppViewModel.swift` — reverdictAll() on Save | DONE (Wave-4 review APPROVE 468382c) |

**Wave 4 review APPROVE highlights:** reverdictAll bounded by cap=3 gate (no OOM); Save writes thresholds.json (atomic) BEFORE reverdictAll; single shared vm injected both scenes; path/format match Python runtime_config; 17 const names parity-checked. Non-blocking: in-flight .analyzing items skipped on Save (self-corrects next Save). **PENDING: GUI verification on real app before declaring done (per verify-real-path lesson).**

**Decisions locked:** verdict-time thresholds only; auto re-decide on Save. Q1 keep MP3 cutoff Hz fixed v1. Q2 hardcode Swift catalog + CI parity grep. Q3 drop unused BITRATE_192. Q4 rely on golden regression for round-4 boundary. Q5 N one-shot spawns on Save OK (cap=3). Q6 AppViewModel shared instance injected into both scenes.

### history-tab (#5) · branch: `feat/history-tab` · worktree: `.claude/worktrees/history-tab`
SPEC: `docs/specs/history-tab/SPEC.md` · PLAN: `docs/specs/history-tab/PLAN.md`

| # | Wave | File | Status |
|---|------|------|--------|
| T-1 | W1 | `core/history.py` (new) + `tests/test_history.py` | DONE (review APPROVE; 2-layer invariant + call-time CONFIG_HASH + no-heavy-imports verified; 13 green) |
| T-2 | W1 | `core/analyzer.py` main(argv) + `--history` | DONE (review APPROVE; lazy import, no-collision; fixed stale test_wireup grep; 6 green, suite 144) |
| T-3 | W2 | `Models/AnalysisResult.swift` optional analyzedAt/fileExists | DONE (review APPROVE; byte-compat decode verified) |
| T-4 | W2 | `Services/HistoryService.swift` search(query:limit:) | DONE (review APPROVE; mirrors AnalyzerService resolution) |
| T-5 | W2 | `ViewModels/AppViewModel.swift` addFromHistory | DONE (review APPROVE; dedupe resolved-path, guard !=false) |
| T-6 | W3 | `Views/HistoryView.swift` (omnibox redesign) + `RootView.swift` + `DJAnalyzerApp.swift` + ReportCardView AC-8 guard | DONE (user GUI-verified 'feels amazing'; omnibox: single-col, typeahead dropdown, hover+↑↓+Enter/click, first highlighted. Review r2 BLOCK→fixed: keyDown monitor gated on isActive + onAppear restart (macOS TabView onDisappear unreliable). Merged to main.) |

**Decisions locked:** verdict live under current CONFIG_HASH (reverdict from cache, verdicts-rows-only — never measurements); missing files listed + marked, add/spectrogram disabled; search = basename substring anywhere, prefix ranks first, recency tiebreak; click → ReportCard + addFromHistory into Analyze queue; Clear-search wipes History tab only. Q1 collapse to **most-recent row per path** (remaster→new name, dupes won't happen in practice). Q2 debounce ~150ms tune in T-6. Q3 absolute short date. Q4 missing-row → disabled affordance + note. `core/cache.py` NOT edited (golden: get_or_analyze + test_cache.py stay green).

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
