# Debt Ledger

Append-only. Each row is a shortcut taken under time pressure.
Pay down by adding a task in TASKS.md, implementing, and marking PAID here.

| ID | Status | Description | File | Created |
|----|--------|-------------|------|---------|
| D-1 | PAID | cache.py called analyze() then _split() to reconstruct raw — now uses analyze_raw() directly; _split deleted (~50 lines, fragile assembled→raw duplication). | core/cache.py | 2026-06-28 |
| D-2 | PAID | Lazy thumbnail spawned dj-spectrogram per card (generateFull, ~300MB–1GB each), unbounded → 34GB OOM + hard reset. PAID by removing card thumbnails entirely; full spectrogram is on-demand (one window) only. | ReportCardView.swift | 2026-06-28 |
| D-3 | OPEN | reverdictAll() on threshold Save spawns one dj-analyze process per loaded track (cap=3 gated). Bounded/safe (each 0.134s cache-hit, no re-FFT, no OOM) but not instant at scale: ~22s/500, ~2.2min/3000 loaded tracks. Fix: single in-process batch reverdict (e.g. `dj-analyze --reverdict-all`) opening the DB once → ~1-2s for 3000. | AppViewModel.swift (reverdictAll) + core (new batch reverdict entrypoint) | 2026-07-01 |
