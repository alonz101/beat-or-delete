# Beat or Delete — Session Summary

## What Was Built

**Beat or Delete** is a macOS desktop app for DJs to analyze audio file quality before a set.
Fully deterministic — no AI/LLM. Drop files or a folder, get a verdict on each file.

---

## App Distribution

- **Name:** Beat or Delete
- **Bundle ID:** `com.alonzigerman.beatordelete`
- **Icon:** Judge's gavel striking a vinyl record (generated via PIL)
- **Format:** `.app` bundle + `.dmg` for distribution
- **Location:** `build/BeatOrDelete.dmg` (251MB)
- **Architecture:** ARM64 (Apple Silicon only)

### Installing on another Mac
1. Open `BeatOrDelete.dmg`
2. Drag `BeatOrDelete.app` to Applications
3. First launch: right-click → Open (Gatekeeper bypass, one-time)
4. If "damaged or incomplete" error appears, run in Terminal:
   ```
   xattr -dr com.apple.quarantine /Applications/BeatOrDelete.app
   ```

### No Python needed
The app bundles frozen Python executables (`dj-analyze`, `dj-batch`) built with PyInstaller in onedir mode. `ffprobe` is also bundled. Zero external dependencies on the target machine.

---

## Build Process

```bash
cd /Users/alonzigerman/personal/analyzer
bash build/build_app.sh
# produces build/BeatOrDelete.app + run hdiutil to create DMG
```

The build script:
1. Freezes Python with PyInstaller (onedir mode — no extraction delay at runtime)
2. Builds Swift binary with `swift build -c release`
3. Assembles `.app` bundle manually (no Xcode required)
4. Embeds frozen executables in `Contents/Resources/dj-analyze/` and `Contents/Resources/dj-batch/`

---

## Verdict Tiers

| Verdict | Meaning |
|---|---|
| **CLUB READY** | Passes all thresholds |
| **REVIEW** | Something worth a listen before the set |
| **DO NOT PLAY** | Blocking issue detected |

---

## Classification Rules & Thresholds

### Blocking Flags → DO NOT PLAY
| Flag | Condition |
|---|---|
| `FAKE_LOSSLESS` | Lossless container (FLAC/WAV/AIFF) but spectral coverage < 85% of Nyquist |
| `LOW_QUALITY_MP3` | Any lossy file with spectral ceiling < 19kHz (≤192kbps quality) |
| `CLIPPING` | > 20 clip events or longest > 100ms |
| `OVER_COMPRESSED` | Dynamic range < 4 dB |

### Review Flags → REVIEW
| Flag | Condition |
|---|---|
| `FAKE_320` | Declares 320kbps but spectral ceiling in 256kbps range (19–20.5kHz) |
| `SUSPECT_LOSSLESS` | Spectral coverage 85–92% of Nyquist |
| `LAME_CONFIRMED` | LAME header found in lossless container |
| `MINOR_CLIPPING` | 3–20 clip events |
| `LOW_DYNAMIC_RANGE` | Dynamic range 4–6 dB |
| `HIGH_NOISE_FLOOR` | Noise floor > -45 dBFS |
| `HUM` | 50/60Hz hum spike detected (only when vinyl confirmed) |

### Informational Flags (shown but don't affect verdict)
| Flag | Condition |
|---|---|
| `FAKE_24BIT` | Declared 24-bit but LSB zero ratio > 95% |
| `WOW_FLUTTER` | Wow & flutter > 0.15% (vinyl only) |
| `PEAK_HOT` | Sample peak > -0.03 dBFS |
| `LOUDNESS_LOW` | Loudness < -18 LUFS |
| `LOUDNESS_HOT` | Loudness > -6 LUFS |

---

## Spectral Analysis Thresholds

Spectral coverage = top active frequency / Nyquist frequency

| Coverage | Verdict |
|---|---|
| < 85% | `FAKE_LOSSLESS` / `FAKE_320` |
| 85–92% | `SUSPECT_LOSSLESS` |
| > 92% | GENUINE |

### Known MP3 spectral cutoffs (for `suspected_origin` label)
| Cutoff | Likely source |
|---|---|
| < 17,000 Hz | MP3 ≤128kbps |
| 17,000–19,000 Hz | MP3 192kbps |
| 19,000–20,500 Hz | MP3 320kbps |
| > 20,500 Hz | Likely genuine lossless |

---

## Vinyl Rip Detection Rules

### Hard Gate (must pass before any scoring)
At least one of the following must be present:
- **Elevated noise floor** > -58 dBFS (audible hiss — real vinyl noise floor)
- **Actual clicks** ≥ 1 detected

Hum alone does NOT open the gate — it false-positives on bass-heavy digital files.

### Scoring (need ≥ 3 to confirm vinyl)
| Indicator | Score |
|---|---|
| Noise floor > -55 dBFS | +2 |
| 1–2 clicks | +1 |
| ≥ 3 clicks | +2 |
| 50/60Hz hum spike | +3 |
| Wow & flutter > 0.3% WRMS **AND** hard indicator present | +1 |

### Wow & Flutter Rule
Wow/flutter only adds to the score when at least one hard indicator (elevated noise OR hum OR clicks) is already present. Prevents ZCR proxy false-positives on clean digital files with wide pitch variation.

### Vinyl Grade
| Grade | Issues score |
|---|---|
| EXCELLENT | 0 |
| GOOD | 1 |
| ACCEPTABLE | 2–3 |
| POOR | 4+ |

Issues scoring: noise floor > -45 (+2), noise floor > -55 (+1), clicks > 5 (+2), clicks > 0 (+1), wow/flutter > 0.15% (+2), wow/flutter > 0.05% (+1), hum present (+1).

---

## Loudness & Peak Thresholds

| Parameter | Threshold | Note |
|---|---|---|
| LUFS floor for CLUB READY | -18 LUFS | Below = CASUAL OK |
| LUFS ceiling for CLUB READY | -6 LUFS | Above = CASUAL OK |
| PEAK_HOT flag | > -0.03 dBFS | Informational only — normal for Beatport masters |
| CLIPPING (blocking) | > 10 samples | |
| MINOR_CLIPPING (marginal) | 4–10 samples | 1–3 samples = inaudible, ignored |

---

## Dynamic Range Thresholds

Measured as RMS spread across 3-second blocks (not DR meter standard).

| Range | Flag |
|---|---|
| < 4 dB | `OVER_COMPRESSED` → DO NOT PLAY |
| 4–6 dB | `LOW_DYNAMIC_RANGE` → MARGINAL |
| > 6 dB | OK |

Typical electronic/club music: 6–10 dB. Techno can legitimately be 3–4 dB.

---

## Noise Floor Threshold

| Level | Flag |
|---|---|
| > -45 dBFS | `HIGH_NOISE_FLOOR` → MARGINAL (audible hiss at club volume) |

---

## Known Limitations

- **Wow & flutter** uses ZCR (zero-crossing rate) as a pitch proxy — noisy on music with wide pitch range. Real measurement requires proper pitch tracking (aubio, crepe) which doesn't build on numpy 2.x.
- **True peak** is measured as sample peak, not inter-sample peak (no oversampling meter). `PEAK_HOT` label reflects this.
- **FAKE_24BIT** uses LSB analysis — checks if bottom 8 bits are all zero, which is true for genuine 16-bit audio saved as 24-bit.
- **Vinyl hum** detects 50/60Hz via FFT spike > 10x local baseline. Can false-positive on bass-heavy music — mitigated by the hard gate.
- **Batch export** re-analyzes all files via Python instead of reusing in-app results.

---

## File Structure

```
analyzer/
  core/
    analyzer.py              # entry point: python analyzer.py <file> [--spectrogram]
    verdict.py               # rule engine → verdict + flags
    spectrogram.py           # dark-mode magma PNG via librosa/matplotlib
    checks/
      metadata.py            # ffprobe + LAME header detection
      spectral.py            # FFT ceiling / fake lossless detection
      integrity.py           # clipping, noise floor, DR, DC offset
      loudness.py            # LUFS, sample peak
      vinyl.py               # vinyl rip detection (hum, clicks, wow/flutter)
  batch.py                   # batch folder analysis + CSV/PDF export
  core/export/
    csv_writer.py
    pdf_writer.py
  DJAnalyzer/                # SwiftUI app (binary named BeatOrDelete)
    Package.swift
    Sources/DJAnalyzer/
      DJAnalyzerApp.swift
      Models/AnalysisResult.swift  AppSettings.swift
      Services/AnalyzerService.swift
      Views/
        ContentView.swift
        DropZoneView.swift
        FileQueueView.swift        # filter bar: All / Do Not Play / Marginal+ / Club Ready
        ReportCardView.swift       # per-file card + spectrogram
        SummaryBarView.swift
        VerdictBadge.swift
        SettingsView.swift         # ⌘, preferences window
  build/
    build_app.sh             # one-command full build
    analyzer.spec            # PyInstaller spec for dj-analyze
    batch.spec               # PyInstaller spec for dj-batch
    hook_runtime.py          # PyInstaller runtime hook: adds _MEIPASS to PATH
    make_icon.py             # generates AppIcon.icns via PIL
    AppIcon.icns
    BeatOrDelete.app
    BeatOrDelete.dmg
```
