import numpy as np
import librosa

from core.config import (
    SPECTRAL_ANALYSIS_DURATION,
    SPECTRAL_FFT_SIZE,
    SPECTRAL_ACTIVE_BIN_FLOOR_DB,
    SPECTRAL_FAKE_LOSSLESS_RATIO,
    SPECTRAL_SUSPECT_RATIO,
    SPECTRAL_MP3_128_CUTOFF_HZ,
    SPECTRAL_MP3_192_CUTOFF_HZ,
    SPECTRAL_MP3_320_CUTOFF_HZ,
)


def check_spectral(path: str, analysis_duration: float = SPECTRAL_ANALYSIS_DURATION) -> dict:
    y, sr = librosa.load(path, sr=None, mono=True, duration=analysis_duration)

    fft = np.abs(librosa.stft(y, n_fft=SPECTRAL_FFT_SIZE))
    fft_db = librosa.amplitude_to_db(fft, ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=SPECTRAL_FFT_SIZE)

    avg_per_bin = fft_db.mean(axis=1)
    active_bins = np.where(avg_per_bin > SPECTRAL_ACTIVE_BIN_FLOOR_DB)[0]

    nyquist = sr / 2
    if len(active_bins) == 0:
        top_freq = 0.0
        ratio = 0.0
    else:
        top_freq = float(freqs[active_bins[-1]])
        ratio = top_freq / nyquist

    if ratio < SPECTRAL_FAKE_LOSSLESS_RATIO:
        verdict = "FAKE_LOSSLESS"
    elif ratio < SPECTRAL_SUSPECT_RATIO:
        verdict = "SUSPECT"
    else:
        verdict = "GENUINE"

    suspected_source = _classify_cutoff(top_freq)

    return {
        "nyquist_hz": nyquist,
        "top_freq_hz": round(top_freq, 0),
        "coverage_ratio": round(ratio, 4),
        "spectral_verdict": verdict,
        "suspected_origin": suspected_source,
    }


def _classify_cutoff(freq_hz: float) -> str:
    if freq_hz < SPECTRAL_MP3_128_CUTOFF_HZ:
        return "MP3 <=128kbps"
    if freq_hz < SPECTRAL_MP3_192_CUTOFF_HZ:
        return "MP3 192kbps"
    if freq_hz < SPECTRAL_MP3_320_CUTOFF_HZ:
        return "MP3 320kbps"
    return "likely genuine lossless"
