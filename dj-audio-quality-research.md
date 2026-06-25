# DJ Audio Quality Analyzer — Research Findings

## The Core Problem

A file's container format (WAV, FLAC, AIFF) says nothing about audio lineage. An MP3 decoded and re-encoded to FLAC is "lossless" in format only — the lossy damage is permanently baked in. Mainstream DJ tools (Rekordbox, Mixed In Key, Platinum Notes) don't detect this. It's a real gap.

---

## 1. Fake Lossless Detection (Lossy-to-Lossless Transcodes)

### Spectral Frequency Cutoff — The Most Reliable Tell

Every lossy encoder has a hard frequency ceiling. In a spectrogram, fake lossless files show a perfectly horizontal dark line where content abruptly stops. True lossless has a gradual natural rolloff.

| Source Format | Frequency Cutoff |
|---|---|
| MP3 128kbps | ~16kHz |
| MP3 192kbps | ~18–19kHz |
| MP3 320kbps | ~20–20.5kHz |
| AAC 256kbps | ~20kHz (different rolloff shape) |
| True lossless 44.1kHz | content to 22.05kHz (Nyquist) |
| True lossless 48kHz | content to 24kHz |
| True hi-res 96kHz | content to 48kHz |

**Coverage ratio heuristic:**
- `>95%` of Nyquist → likely genuine lossless
- `85–95%` → suspect
- `<85%` → fake lossless

### LAME Header — Definitive Proof

The LAME encoder embeds a header tag in MP3 files that **survives conversion to FLAC/WAV**. Checking for this with `mutagen` gives definitive proof of MP3 origin regardless of container format.

### Other Spectral Signatures

- **Noise floor**: True lossless has flat broadband noise across all frequencies. Fake lossless has no noise above the cutoff (manufactured silence, not captured silence).
- **Spectral holes**: LAME Huffman coding creates narrow zero-energy bands at specific frequencies (e.g., ~11kHz in low-bitrate MP3s).
- **MDCT pre-echo**: MP3's filterbank introduces energy slightly *before* sharp transients (snare, hi-hat). Visible in a spectrogram as pre-ringing. Impossible in true lossless.
- **Joint stereo artifacts**: MP3 joint stereo creates abnormal inter-channel correlation in the 16–22kHz range, detectable even after lossless re-encoding.
- **AAC zebra stripes**: AAC encoding leaves distinct parallel artifact patterns in high frequencies on spectrograms.

### Bit Depth Verification

A genuine 16-bit file converted to 24-bit has the bottom 8 bits (LSBs) of every sample as `0x00`. Mathematically detectable — if LSBs are always zero, the declared 24-bit depth is fake.

---

## 2. Technical Specs to Analyze Per File

| Parameter | What to Check |
|---|---|
| Container format | WAV / FLAC / AIFF / MP3 / AAC |
| Declared sample rate | 44.1 / 48 / 96kHz etc. |
| Declared bit depth | 16 / 24 / 32-bit |
| Bitrate (lossy) | CBR vs VBR; 320kbps minimum for club |
| LAME header | Present in a .flac/.wav = was MP3 |
| Frequency ceiling | FFT — does it match Nyquist for declared SR? |
| True peak | ITU-R BS.1770; should be ≤ -0.1dBTP |
| Clipping | Samples at full scale (flat-topping) |
| Dynamic range | DR score; DR6+ acceptable, DR8+ preferred |
| Noise floor | Avg dBFS in silent passages |
| DC offset | Mean sample value; should be ~0 |
| Phase / mono compatibility | Mono sum check; bass cancellation = phase issue |

---

## 3. Vinyl Rip Quality — Club Acceptability

Vinyl rips are a special case. A good rip from a quality pressing can be club-grade even with some surface noise. Key thresholds:

### Noise Floor (between musical phrases)
| Level | Assessment |
|---|---|
| Below -65dBFS | Excellent |
| -55 to -65dBFS | Acceptable |
| -45 to -55dBFS | Marginal (hiss audible at high volume) |
| Above -45dBFS | Unacceptable for club |

### Clicks & Pops
- Detection: samples >20dB above local RMS average lasting <5ms
- **<1 click/min** → acceptable
- **1–5 clicks/min** → marginal (audible in quiet passages)
- **>5 clicks/min** or any click >-10dBFS → unacceptable

### Wow & Flutter (pitch instability)
- Wow: <6Hz variation (off-center pressing, turntable speed)
- Flutter: 6–100Hz (belt wear)
- Measured as WRMS (weighted RMS)
  - **<0.05% WRMS** → acceptable
  - **0.05–0.15% WRMS** → marginal (wobbly bass in mono)
  - **>0.15% WRMS** → unacceptable

### Other Vinyl Issues
- **RIAA EQ problems**: incorrect cartridge loading → HF rolloff or resonance peaks. Expected: flat ±2dB from 20Hz–20kHz.
- **60Hz hum**: grounding issue during rip. Detectable as strong narrowband spike at 50 or 60Hz.
- **Stereo imbalance**: >3dB channel difference = capture problem.

### Club-Quality Vinyl Rip Checklist
- [ ] 24-bit/44.1kHz or 48kHz capture
- [ ] Noise floor below -60dBFS between phrases
- [ ] No unrepaired clicks above -20dBFS, <1/min
- [ ] Wow & flutter <0.1% WRMS
- [ ] Frequency response to ≥18kHz
- [ ] No 50/60Hz hum spike
- [ ] Stereo image stable

---

## 4. DJ / Club PA Thresholds

Club systems at 96–110dB SPL expose everything. What becomes audible:

| Quality Issue | Audibility at Club Volume |
|---|---|
| Hard clipping | High — harsh distortion |
| 128kbps MP3 artifacts | High — easily audible in cymbals/reverb |
| 192kbps MP3 artifacts | Marginal |
| 320kbps MP3 artifacts | Low — subtle on very high-end systems |
| Over-compression DR<4 | High — pumping/breathing |
| Quantization noise | Medium — graininess in reverb tails |
| DC offset | Low (but causes click at track start/end) |
| Wow & flutter | Medium — pitch instability in bass |
| Intersample clipping | Medium — digital distortion after D/A |

### Minimum Acceptable for Club
- **Lossy**: MP3 320kbps CBR (not VBR — CDJ compatibility), or AAC 256kbps
- **Lossless**: FLAC/WAV 16-bit/44.1kHz — reject fake 24-bit upsamples
- **Dynamic range**: DR6 minimum
- **True peak**: ≤ -1dBTP (headroom for analog chain)
- **No clipping**: zero intersample peaks

---

## 5. Common Issues Taxonomy

| Issue | Detection | Club Audibility |
|---|---|---|
| Hard clipping | Peak sample scan, flat-top waveform | High |
| Intersample clipping | True peak meter BS.1770 | Medium |
| Fake lossless (lossy transcode) | Spectral cutoff, LAME header | Medium |
| Over-compression | DR meter | High |
| DC offset | Mean sample value | Low |
| Phase inversion | Mono sum check | Medium (bass cancel) |
| Wow & flutter | Autocorrelation pitch analysis | Medium |
| Vinyl hiss | Noise floor FFT | Low-Medium |
| Clicks/pops | Short impulse detection | High |
| Glitches/dropouts | Short-term RMS deviation | High |
| 50/60Hz hum | Narrowband FFT spike | Medium |

---

## 6. Programmatic Analysis — Tools & Libraries

### CLI Tools (wrap these in the app)

```bash
# Container metadata, codec, declared specs
ffprobe -v quiet -print_format json -show_streams -show_format file.flac

# Clipping, RMS, DC offset, dynamic range stats
sox file.wav -n stat
sox file.wav -n stats

# Spectrogram PNG
sox file.wav -n spectrogram -o out.png

# Detailed codec params, LAME/AAC headers
mediainfo --Output=JSON file.flac

# DR score
dr14_tmeter file.flac
```

### Python Libraries

| Library | Use |
|---|---|
| `librosa` | FFT, spectral rolloff, zero crossing, MFCCs |
| `soundfile` | Format-agnostic audio loading, exposes bit depth / SR |
| `mutagen` | Metadata + LAME header detection |
| `pyloudnorm` | ITU-R BS.1770 loudness + true peak |
| `numpy` / `scipy` | Custom FFT, LSB analysis, autocorrelation |
| `essentia` | Full MIR suite — most powerful; MTG Barcelona |
| `aubio` | Onset detection, tempo, pitch (wow/flutter) |

### Key Detection Snippets

**Fake lossless via spectral cutoff:**
```python
import librosa, numpy as np

def detect_fake_lossless(path, threshold_db=-80):
    y, sr = librosa.load(path, sr=None, mono=True)
    fft = np.abs(librosa.stft(y))
    fft_db = librosa.amplitude_to_db(fft)
    freqs = librosa.fft_frequencies(sr=sr)
    avg_per_bin = fft_db.mean(axis=1)
    active_bins = np.where(avg_per_bin > threshold_db)[0]
    top_freq = freqs[active_bins[-1]]
    ratio = top_freq / (sr / 2)
    return {
        "top_freq_hz": top_freq,
        "coverage_ratio": ratio,
        "likely_fake": ratio < 0.92,
        "suspected_source": classify_cutoff(top_freq)
    }

def classify_cutoff(freq_hz):
    if freq_hz < 17000: return "MP3 ≤128kbps"
    if freq_hz < 19000: return "MP3 192kbps"
    if freq_hz < 20500: return "MP3 320kbps"
    return "likely genuine lossless"
```

**LAME header check (definitive MP3 origin):**
```python
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

def check_lame_header(path):
    # Even in a .flac, if it was converted from MP3, LAME tag may persist
    # Check raw bytes for 'Info' or 'LAME' marker at byte offset 36
    with open(path, 'rb') as f:
        data = f.read(200)
    return b'LAME' in data or b'Info' in data
```

**Bit depth verification (fake 24-bit):**
```python
import soundfile as sf
import numpy as np

def check_fake_24bit(path):
    data, sr = sf.read(path, dtype='int32')
    # If source was 16-bit, bottom 8 bits should all be 0
    lsb_mask = data & 0xFF
    zero_ratio = np.sum(lsb_mask == 0) / lsb_mask.size
    return zero_ratio > 0.95  # >95% zeros = likely fake 24-bit
```

---

## 7. Verdict Classification System (Proposed)

### Tier 1 — Format Assessment
- **GENUINE LOSSLESS**: spectral coverage >95% Nyquist + no LAME header + bit depth noise floor matches declared depth
- **SUSPECT LOSSLESS**: coverage 85–95% OR LAME header present in lossless container
- **FAKE LOSSLESS**: coverage <85% Nyquist OR hard cutoff shelf detected OR LAME header confirmed
- **LOSSY (declared)**: rate by bitrate + artifact score

### Tier 2 — Playability Verdict
- **CLUB READY**: passes all thresholds (DR, peak, no clipping, genuine format)
- **REVIEW**: something worth a listen before the set — noticeable issues at volume
- **DO NOT PLAY**: clipping, severe compression, major artifacts, or clearly fake/degraded

### Confidence Flags
- `VINYL_RIP` — detected based on 50/60Hz profile, noise floor shape, clicks pattern
- `LAME_CONFIRMED` — LAME header found in lossless container
- `UPSAMPLED` — declared SR doesn't match spectral ceiling
- `CLIPPING` — N samples clipped
- `OVER_COMPRESSED` — DR score below threshold

---

## 8. App Architecture Notes (Mac Desktop)

**Recommended stack:**
- **Python backend**: librosa + ffprobe + mutagen + pyloudnorm + sox
- **Mac GUI**: Swift/SwiftUI wrapping a Python subprocess, or Electron, or Tauri
- **Drag-and-drop** single file or batch folder analysis
- **Output**: per-file verdict card + exportable report

**Analysis pipeline order:**
1. `ffprobe` / `mediainfo` → declared metadata
2. `mutagen` → LAME header check
3. `soundfile` → load audio, LSB 24-bit verification
4. `librosa` FFT → spectral ceiling, coverage ratio
5. `pyloudnorm` → true peak + integrated loudness
6. Custom RMS scan → click/pop detection
7. `sox stats` → DR, DC offset, clipping count
8. Autocorrelation (aubio) → wow/flutter (vinyl rips)
9. Aggregate → verdict tier + confidence flags

**Key differentiator vs existing tools**: none of Rekordbox, Mixed In Key, or Platinum Notes do spectral fake-lossless detection, LAME header sniffing, or wow/flutter measurement. This covers real gaps.

---

## References

- ITU-R BS.1770 — loudness/true peak standard
- ITU-R BS.1534 (MUSHRA) — subjective audio quality evaluation
- Hydrogen Audio wiki — codec technical details, LAME header spec
- librosa docs — spectral feature extraction
- mutagen docs — audio metadata / tag reading
- TT Dynamic Range Meter technical documentation
- AES papers on MDCT pre-echo and joint stereo artifacts
- Essentia (MTG Barcelona) — MIR library
