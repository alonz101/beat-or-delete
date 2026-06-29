# Debt Ledger

Append-only. Each row is a shortcut taken under time pressure.
Pay down by adding a task in TASKS.md, implementing, and marking PAID here.

| ID | Status | Description | File | Created |
|----|--------|-------------|------|---------|
| D-1 | OPEN | cache.py calls analyze() then _split() instead of analyze_raw() — redundant assembly+split | core/cache.py | 2026-06-28 |
| D-2 | PAID | Lazy thumbnail spawned dj-spectrogram per card (generateFull, ~300MB–1GB each), unbounded → 34GB OOM + hard reset. PAID by removing card thumbnails entirely; full spectrogram is on-demand (one window) only. | ReportCardView.swift | 2026-06-28 |
