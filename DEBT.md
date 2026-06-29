# Debt Ledger

Append-only. Each row is a shortcut taken under time pressure.
Pay down by adding a task in TASKS.md, implementing, and marking PAID here.

| ID | Status | Description | File | Created |
|----|--------|-------------|------|---------|
| D-1 | PAID | cache.py called analyze() then _split() to reconstruct raw — now uses analyze_raw() directly; _split deleted (~50 lines, fragile assembled→raw duplication). | core/cache.py | 2026-06-28 |
| D-2 | PAID | Lazy thumbnail spawned dj-spectrogram per card (generateFull, ~300MB–1GB each), unbounded → 34GB OOM + hard reset. PAID by removing card thumbnails entirely; full spectrogram is on-demand (one window) only. | ReportCardView.swift | 2026-06-28 |
