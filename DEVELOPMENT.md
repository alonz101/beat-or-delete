# DJ Audio Analyzer — Development Log

## What This App Does
Mac desktop app for DJs to analyze audio file quality. Fully deterministic — no LLM calls. Drop files or a folder, get a verdict on each file. Detects fake lossless, fake 320kbps MP3s, clipping, over-compression, vinyl rip quality, and more.

## Stack
- **Python backend**: librosa, soundfile, mutagen, pyloudnorm, scipy, matplotlib, ffprobe
- **Swift frontend**: SwiftUI macOS app (Swift Package Manager, no Xcode project needed)
- **Communication**: SwiftUI shells out to Python via `Process()`, reads stdout JSON

## Repo Location
```
/Users/alonzigerman/personal/analyzer/
```

## Project Structure
```
analyzer/
  core/
    analyzer.py              # entry point: python analyzer.py <file> [--spectrogram]
    verdict.py               # rule engine → verdict + flags
    spectrogram.py           # generates dark-mode PNG via librosa/matplotlib
    checks/
      metadata.py            # ffprobe + LAME header detection
      spectral.py            # FFT ceiling / fake lossless detection
      integrity.py           # clipping, noise floor, DR, DC offset
      loudness.py            # LUFS, true peak
      vinyl.py               # vinyl rip detection (hum, clicks, wow/flutter)
  batch.py                   # python batch.py <folder> [--output stem]
  core/export/
    csv_writer.py
    pdf_writer.py            # uses reportlab
  DJAnalyzer/                # SwiftUI app
    Package.swift
    Sources/DJAnalyzer/
      DJAnalyzerApp.swift
      Models/AnalysisResult.swift
      Services/AnalyzerService.swift   # Python subprocess wrapper
      Views/
        ContentView.swift              # layout + AppViewModel
        DropZoneView.swift             # drag-and-drop + file picker button
        FileQueueView.swift            # file list rows
        ReportCardView.swift           # per-file detail card + spectrogram
        SummaryBarView.swift           # progress bar + verdict counts + export
        VerdictBadge.swift             # colored verdict pill
  dj-audio-quality-research.md        # research notes (spectral analysis, thresholds)
```

## How to Run

### Python CLI (single file)
```bash
cd /Users/alonzigerman/personal/analyzer
python3 core/analyzer.py "file.aiff" --spectrogram
```

### Python CLI (batch folder)
```bash
python3 batch.py /path/to/folder --output /path/to/report
# produces report.csv + report.pdf
```

### SwiftUI App
```bash
cd /Users/alonzigerman/personal/analyzer/DJAnalyzer
swift build
.build/debug/DJAnalyzer &
# or open Package.swift in Xcode and press ▶
```

## Python Dependencies
Installed under pyenv 3.11.9:
```
librosa, soundfile, mutagen, pyloudnorm, scipy, numpy, matplotlib, reportlab, ffprobe (system)
```

The Swift app auto-discovers the correct Python by walking `~/.pyenv/versions/` and finding the one with `librosa` installed.

---

## Verdict Logic

### Verdict Tiers
| Verdict | Meaning |
|---|---|
| CLUB READY | Passes all thresholds |
| CASUAL OK | Fine for home listening, minor issues (e.g. low loudness) |
| MARGINAL | Noticeable issues at club volume |
| DO NOT PLAY | Blocking issue detected |

### Blocking Flags (→ DO NOT PLAY)
- `FAKE_LOSSLESS` — lossless container (FLAC/WAV/AIFF) with lossy spectral signature
- `FAKE_320` — declared 320kbps MP3 but spectral ceiling matches 192kbps or lower
- `CLIPPING` — >10 clipped samples
- `OVER_COMPRESSED` — dynamic range <4dB

### Marginal Flags (→ MARGINAL)
- `SUSPECT_LOSSLESS` — spectral coverage 85–92% of Nyquist
- `LOW_QUALITY_MP3` — spectral below declared bitrate (non-320)
- `UPSAMPLED` — lossless container, suspect spectral
- `LAME_CONFIRMED` — LAME header found in lossless container
- `FAKE_24BIT` — declared 24-bit but LSBs all zero
- `MINOR_CLIPPING` — 1–10 clipped samples
- `LOW_DYNAMIC_RANGE` — DR 4–6dB
- `HIGH_NOISE_FLOOR` — noise floor above -45dBFS
- `TRUE_PEAK_HOT` — true peak near 0dBFS
- `VINYL_RIP` — detected as vinyl rip
- `WOW_FLUTTER` — pitch instability detected
- `HUM` — 50/60Hz hum spike

### Key Detection Methods
- **Fake lossless**: FFT spectral ceiling — if content cuts off well below Nyquist, it was encoded lossy first
- **LAME header**: raw byte check — LAME tag survives MP3→FLAC conversion
- **Fake 24-bit**: LSB analysis — genuine 16-bit converted to 24-bit has all LSBs = 0x00
- **Vinyl rip**: combination of noise floor >-55dBFS, click count ≥3, 50/60Hz hum, wow/flutter >0.3%
- **Spectrogram**: 30s preview, dark-mode magma colormap, saved as temp PNG

---

## Phases Completed

### Phase 1 — Python Analyzer Core ✅
- Single file analysis via CLI
- Outputs clean JSON with format, authenticity, playability, flags, verdict

### Phase 2 — Batch + Export ✅
- `batch.py` walks folder, runs analysis in parallel (4 workers)
- Exports CSV (flat, sortable) + PDF (summary table + per-file detail cards)
- Results sorted: DO NOT PLAY first

### Phase 3 — SwiftUI Mac App ✅
- Drag-and-drop zone (files or folder)
- File queue with live status (pending → analyzing → done/error)
- Report cards per file with all stats
- Export button triggers batch.py

### Phase 4 — Polish ✅
- Spectrogram thumbnail per report card (lazy, generated by Python)
- Progress bar in summary bar while analyzing
- Right-click any file → "Reveal in Finder"
- Vinyl rip detection + grading (EXCELLENT/GOOD/ACCEPTABLE/POOR)
- Wow & flutter via ZCR proxy (aubio won't build on numpy 2.x)

### Phase 5 — Settings + Filter ✅
- `AppSettings.swift` — analyzer root + Python override stored in UserDefaults
- Preferences window (⌘,) with Browse buttons for both paths
- Filter bar in file queue: All / Do Not Play / Marginal+ / Club Ready with item count

### Phase 6 — Distributable .app ✅
- PyInstaller freezes `core/analyzer.py` → `dj-analyze` and `batch.py` → `dj-batch` (Python runtime + all deps bundled, ~108MB each)
- `ffprobe` binary embedded in the frozen executables — no system dependencies required
- Proper `.app` bundle assembled manually (`Contents/MacOS/`, `Contents/Resources/`, `Info.plist`)
- `AnalyzerService` checks `Bundle.main.resourceURL` for frozen binaries first, falls back to Python discovery in dev mode
- `build/build_app.sh` — one-command build: PyInstaller → Swift release build → .app assembly
- `build/DJAnalyzer.dmg` — 218MB distributable disk image (drag to Applications)

**To rebuild the distributable:**
```bash
cd /Users/alonzigerman/personal/analyzer
bash build/build_app.sh
# output: build/DJAnalyzer.app + build/DJAnalyzer.dmg
```

**Installation on another Mac:**
1. Open `DJAnalyzer.dmg`
2. Drag `DJAnalyzer.app` to Applications
3. First launch: right-click → Open (one-time Gatekeeper bypass — no Developer account)
4. No Python, no pyenv, no dev tools needed

---

## TODO / Remaining Work

### Medium Priority
- [ ] **App icon** — no icon set; needs `.icns` file
- [ ] **Persistent history** — currently clears on app relaunch; could save last session's results to JSON

### Low Priority / Nice to Have
- [ ] **Wow & flutter with real pitch tracking** — replace ZCR proxy with proper pitch detection once aubio fixes numpy 2.x compatibility (or use crepe/parselmouth)
- [ ] **Drag file out** — drag a file from the queue directly to Finder/Rekordbox
- [ ] **Rekordbox integration** — copy analyzed files to a watched folder with a quality tag in the filename
- [ ] **Waveform overview** — show full-track waveform alongside spectrogram
- [ ] **Dark/light mode toggle** — app currently respects system appearance but spectrogram is always dark

### Known Issues
- Wow & flutter ZCR proxy is noisy — can false-positive on music with wide pitch range; threshold set conservatively at 0.3% WRMS to reduce false positives
- Vinyl rip detection heuristics are conservative by design — better to miss a vinyl rip than falsely flag clean digital files
- `batch.py` export re-analyzes all files (runs Python again) instead of reusing already-computed in-app results — this is redundant for export; could be optimized to write from existing JSON
