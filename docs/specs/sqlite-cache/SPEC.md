# SPEC: Analysis Cache (SQLite)

## Problem
Re-analyzing the same file is slow. Running batch on a folder re-analyzes everything
even if 90% of files were already analyzed in-app. Results can also drift out of sync
between batch and in-app if the app is updated between runs.

## What it does
Cache analysis results in a local SQLite DB so analyzing the same file twice skips
the expensive Python analysis entirely. Two-layer cache: raw measurements (invalidated
by file change) and verdicts (invalidated by threshold change), so updating config
thresholds doesn't require re-running FFT.

## Acceptance criteria
- AC-1: Analyzing a file twice → second call returns instantly, no FFT runs
- AC-2: File modified on disk (mtime or size changed) → cache miss, full re-analysis
- AC-3: Thresholds changed in config.py → verdict recomputed from cached raw data only (no FFT)
- AC-4: batch.py uses the same cache as core/analyzer.py
- AC-5: DB created automatically on first run at ~/Library/Application Support/BeatOrDelete/cache.db
- AC-6: spectrogram_path is never cached (temp file, regenerated on demand)
- AC-7: No new pip dependencies (sqlite3 is stdlib)

## Constraints
- Thresholds are currently hardcoded in config.py — there is no user-configurable
  threshold UI yet (#7 is unimplemented). The settings hash must be derived from
  config.py constants only for now, but the design must not break when #7 lands
  and those values become user-settable.

## Out of scope
- Manual cache clearing UI (v1: file identity handles invalidation automatically)
- Cache size limits or eviction policy
