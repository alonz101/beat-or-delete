# Beat or Delete — Improvements & Roadmap

## Next Version

1. **LUFS verdict fix** — tracks slightly under -18 LUFS should be CLUB READY with a loudness warning flag, not CASUAL OK. DJ can handle gain staging on the mixer.

2. **Vinyl rip detection** — too many false positives. Legit digital files (especially trance/electronic with wide pitch range) triggering VINYL_RIP. Needs recalibration.

3. **Drag and drop not working** — fix file/folder drop into the app.

4. **Analysis cache (SQLite)** — save results to a local SQLite DB so previously analyzed files don't need re-analyzing.

5. **History tab** — new tab with a search bar to look up any previously analyzed track.

6. **Threshold recalibration** — legit Beatport/Bandcamp files getting MARGINAL+. All parameter thresholds are too strict and need rethinking based on real-world DJ use.

7. **Config/settings tab** — let the user manually adjust thresholds per parameter (LUFS floor, clipping limit, DR range, spectral coverage, etc.).

8. **Spectrogram overhaul** — open full-size in a new window. Highlight problem areas directly on the image: red vertical lines at clipping positions, horizontal band at 50/60Hz for hum. Static PNG — no interactive hover.

---

## Future Vision

- **Remaster feature** — suggested as a premium offering. Phase 1: integrate with a VST library to apply corrections. Phase 2: embed natively. Needs more thought — conflicts with the app's "read-only truth teller" identity, and VST hosting on macOS is non-trivial. Business model angle (Premium tier) is interesting.
