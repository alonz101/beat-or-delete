# SPEC: User-Configurable Thresholds (#7)

## Problem
All classification cutoffs are hardcoded in `core/config.py`. DJs can't tune them to
their own taste or genre — e.g. the `OVER_COMPRESSED` < 4 dB rule misfires on legit
peak-time techno, and the LUFS club window is opinionated. There's no way to adjust a
threshold without editing source and rebuilding.

## What it does
Adds a **Config tab** in the app to adjust **verdict-time** thresholds (the cutoffs
applied in `core/checks/flags.py` to already-measured numbers). On Save, every file
already loaded in the session is **re-decided instantly from the cache** (reverdict from
cached raw — no re-FFT, no re-decode). Overrides persist across launches and are honored
by the CLI and batch paths too.

Only verdict-time thresholds are exposed. They reverdict from cached raw data, so a
change is cheap and memory-safe — it never triggers the expensive analysis path. As part
of this, the spectral-coverage decision (FAKE_LOSSLESS / SUSPECT) is refactored out of
`spectral.py` (measurement-time) into `flags.py` (verdict-time) so spectral coverage
becomes adjustable without re-analysis. Measurement-time thresholds (FFT size, clip
sensitivity, vinyl scoring) stay fixed in v1.

## Threshold transport
Swift writes overrides to `~/Library/Application Support/BeatOrDelete/thresholds.json`
(a flat `{CONST_NAME: value}` map of only the changed keys). A new runtime config layer
in Python loads that file at startup and overlays it on the `core/config.py` defaults.
`config_hash` folds in the active overrides, so a changed threshold produces a distinct
`verdicts` row keyed to that config — measurements are untouched and shared. On Save the
app re-runs analysis for each loaded file; the cache hits on the measurement and misses
on the verdict, so it reverdicts (light path) and returns immediately.

## Acceptance criteria
- AC-1: Config tab lists the configurable verdict-time thresholds grouped by category, each showing current value + its default.
- AC-2: Edit a threshold + Save → persisted to `thresholds.json`; survives app restart.
- AC-3: On Save, all files loaded in the queue are re-decided from cache (no FFT/decode runs); verdict badges + reasons update in place.
- AC-4: A verdict-time threshold change changes `config_hash` → a new `verdicts` row is written; the file's `measurements` row is unchanged (proves no re-analysis).
- AC-5: "Reset to Defaults" restores `core/config.py` values and reverdicts loaded files.
- AC-6: Invalid input (non-numeric, or min ≥ max for paired bounds) is rejected inline and not saved.
- AC-7: Spectral coverage (FAKE_LOSSLESS / SUSPECT ratios) is adjustable and reverdict-able; with default values, every existing spectral/flags test produces byte-identical output to today.
- AC-8: With no `thresholds.json` present, behavior is identical to current defaults.
- AC-9: CLI (`core/analyzer.py`) and `batch.py` honor the same `thresholds.json`.
- AC-10: No new pip dependencies (json + hashlib + sqlite3 are stdlib).

## Constraints
- The two-layer cache invariant must hold: a verdict-time threshold change invalidates **verdicts only**, never measurements.
- Refactoring the spectral-coverage decision into `flags.py` must preserve identical default verdicts — golden-output regression required (AC-7).
- The reverdict path must not import librosa/matplotlib/soundfile (keeps Save fast + memory-safe; per [[threshold-verdict-vs-measurement-time]]).
- Tests must use realistic numpy dtypes for raw blobs, not pure-Python stand-ins (per [[tests-use-realistic-numpy-data]]).
- Verify the real GUI Save→reverdict path end-to-end before declaring done; don't substitute an isolated binary test (per [[verify-real-path-before-claiming-done]]).

## Out of scope
- Measurement-time thresholds (FFT size/duration, CLIP_SAMPLE_THRESHOLD, CLIP_MIN_RUN, vinyl detection scoring/grade) — fixed in v1; exposing them would force full re-analysis.
- Per-genre / per-file threshold profiles or saved presets; import/export of configs.
- Changing how raw measurements are computed.
