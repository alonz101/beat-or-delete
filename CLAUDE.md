# Beat or Delete — Codebase Guide

## What This Is

macOS desktop app for DJs to analyze audio file quality before a set. Fully deterministic signal analysis — no AI/LLM. Drop files or a folder, get a verdict on each file.

## Stack

- **Backend:** Python (analysis engine)
- **Frontend:** SwiftUI (macOS app, binary named `BeatOrDelete`)
- **Build:** PyInstaller (freezes Python) + Swift build + manual `.app` assembly — no Xcode required
- **Distribution:** `.dmg` with bundled `ffprobe`, zero deps on target machine

## Project Structure

```
analyzer/
  core/
    analyzer.py         # CLI entry point: python analyzer.py <file> [--spectrogram]
    verdict.py          # rule engine → verdict + flags
    spectrogram.py      # dark-mode magma PNG via librosa/matplotlib
    checks/
      metadata.py       # ffprobe + LAME header detection
      spectral.py       # FFT ceiling / fake lossless detection
      integrity.py      # clipping, noise floor, DR, DC offset
      loudness.py       # LUFS, sample peak
      vinyl.py          # vinyl rip detection (hum, clicks, wow/flutter)
    export/
      csv_writer.py
      pdf_writer.py
  batch.py              # batch folder analysis + CSV/PDF export
  DJAnalyzer/           # SwiftUI app
    Package.swift
    Sources/DJAnalyzer/
      DJAnalyzerApp.swift
      Models/
        AnalysisResult.swift
        AppSettings.swift
      Services/
        AnalyzerService.swift   # shells out to dj-analyze binary
      Views/
        ContentView.swift
        DropZoneView.swift
        FileQueueView.swift     # filter bar: All / Do Not Play / Marginal+ / Club Ready
        ReportCardView.swift    # per-file card + spectrogram
        SummaryBarView.swift
        VerdictBadge.swift
        SettingsView.swift
  build/
    build_app.sh        # one-command full build → BeatOrDelete.app + DMG
    analyzer.spec       # PyInstaller spec for dj-analyze
    batch.spec          # PyInstaller spec for dj-batch
    hook_runtime.py     # PyInstaller runtime hook: adds _MEIPASS to PATH
    make_icon.py        # generates AppIcon.icns via PIL
    AppIcon.icns
```

## Running the Analyzer (CLI)

```bash
python core/analyzer.py <audio-file>            # analyze single file
python core/analyzer.py <audio-file> --spectrogram  # also generate spectrogram PNG
python batch.py <folder>                        # batch analyze folder → CSV + PDF
```

Output is JSON printed to stdout.

## Building the App

```bash
bash build/build_app.sh
# produces build/BeatOrDelete.app
# then run hdiutil to create DMG (see build_app.sh)
```

- ARM64 (Apple Silicon) only
- Requires: Python 3.11+, Swift toolchain, pip deps from `requirements.txt`

## Verdict Tiers

| Verdict | Meaning |
|---|---|
| CLUB READY | Passes all thresholds |
| REVIEW | Something worth a listen before the set |
| DO NOT PLAY | Blocking issue detected |

## Classification Rules

### Blocking → DO NOT PLAY
| Flag | Condition |
|---|---|
| `FAKE_LOSSLESS` | Lossless container but spectral coverage < 85% of Nyquist |
| `LOW_QUALITY_MP3` | Any lossy file with spectral ceiling < 19kHz (≤192kbps quality) |
| `CLIPPING` | > 20 clip events or longest > 100ms |
| `OVER_COMPRESSED` | Dynamic range < 4 dB |

### Review → REVIEW
| Flag | Condition |
|---|---|
| `FAKE_320` | Declares 320kbps but spectral ceiling in 256kbps range (19–20.5kHz) |
| `SUSPECT_LOSSLESS` | Spectral coverage 85–92% of Nyquist |
| `LAME_CONFIRMED` | LAME header in lossless container |
| `MINOR_CLIPPING` | 3–20 clip events |
| `LOW_DYNAMIC_RANGE` | Dynamic range 4–6 dB |
| `HIGH_NOISE_FLOOR` | Noise floor > -45 dBFS |
| `HUM` | 50/60Hz hum spike (vinyl only) |

### Informational (no verdict impact)
| Flag | Condition |
|---|---|
| `FAKE_24BIT` | Declared 24-bit but LSB zero ratio > 95% |
| `WOW_FLUTTER` | Wow & flutter > 0.15% (vinyl only) |
| `PEAK_HOT` | Sample peak > -0.03 dBFS |
| `LOUDNESS_LOW` | Loudness < -18 LUFS |
| `LOUDNESS_HOT` | Loudness > -6 LUFS |

## Key Thresholds

| Parameter | Value |
|---|---|
| Spectral: FAKE_LOSSLESS | < 85% of Nyquist |
| Spectral: SUSPECT_LOSSLESS | 85–92% of Nyquist |
| Clipping: blocking | > 20 events or longest > 100ms |
| Clipping: review | 3–20 events |
| Dynamic range: blocking | < 4 dB |
| Dynamic range: review | 4–6 dB |
| Loudness: CLUB READY range | -18 to -6 LUFS |
| Noise floor: review | > -45 dBFS |
| Wow & flutter: informational | > 0.15% |

## Vinyl Rip Detection

Hard gate (must pass first): noise floor > -58 dBFS OR ≥1 click detected.

Scoring (≥3 confirms vinyl):
- Noise floor > -55 dBFS: +2
- 1–2 clicks: +1 / ≥3 clicks: +2
- 50/60Hz hum spike: +3
- Wow & flutter > 0.3% WRMS + hard indicator: +1

## Known Limitations

- **Wow & flutter** uses ZCR proxy — false positives on music with wide pitch range
- **True peak** is sample peak, not inter-sample (no oversampling)
- **OVER_COMPRESSED** threshold (<4 dB) can misfire on legit techno/peak-time EDM
- **Vinyl detection** can false-positive on digital files with hum from studio gear
- **Batch export** re-analyzes files instead of reusing in-app results

## Planned Improvements (v2)

See `IMPROVEMENTS.md` for the full list.
