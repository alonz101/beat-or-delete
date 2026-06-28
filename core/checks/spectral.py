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
    SPECTRAL_MUSIC_CEILING_HZ,
    SPECTRAL_CLIFF_FLOOR_HZ,
    SPECTRAL_CLIFF_HARD_PP,
)


def check_spectral(path: str, analysis_duration: float = SPECTRAL_ANALYSIS_DURATION) -> dict:
    y, sr = librosa.load(path, sr=None, mono=True, duration=analysis_duration)

    fft = np.abs(librosa.stft(y, n_fft=SPECTRAL_FFT_SIZE))
    fft_db = librosa.amplitude_to_db(fft, ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=SPECTRAL_FFT_SIZE)

    avg_per_bin = fft_db.mean(axis=1)
    active_bins = np.where(avg_per_bin > SPECTRAL_ACTIVE_BIN_FLOOR_DB)[0]

    nyquist = sr / 2
    effective_nyquist = min(nyquist, SPECTRAL_MUSIC_CEILING_HZ)
    if len(active_bins) == 0:
        top_freq = 0.0
        ratio = 0.0
    else:
        top_freq = float(freqs[active_bins[-1]])
        ratio = top_freq / effective_nyquist

    if ratio < SPECTRAL_FAKE_LOSSLESS_RATIO:
        verdict = "FAKE_LOSSLESS"
    elif ratio < SPECTRAL_SUSPECT_RATIO:
        verdict = "SUSPECT"
    else:
        verdict = "GENUINE"

    suspected_source = _classify_cutoff(top_freq)
    cliff_pp, rolloff_shape = _compute_rolloff_cliff(fft_db, freqs)

    return {
        "nyquist_hz": nyquist,
        "top_freq_hz": round(top_freq, 0),
        "coverage_ratio": round(ratio, 4),
        "spectral_verdict": verdict,
        "suspected_origin": suspected_source,
        "rolloff_cliff_pp": cliff_pp,
        "rolloff_shape": rolloff_shape,
    }


def _compute_rolloff_cliff(fft_db: np.ndarray, freqs: np.ndarray) -> tuple[float, str]:
    """
    Detects whether HF rolloff is a hard cliff (MP3 encoder cutoff) or gradual (vinyl/natural).
    Measures the largest drop in frame-occupancy (% frames with energy > -60 dB rel max)
    across any 1kHz window above SPECTRAL_CLIFF_FLOOR_HZ.
    Hard MP3 cutoff → >15pp drop; gradual organic rolloff → <15pp.
    """
    occupancy = (fft_db > -60).sum(axis=1) / fft_db.shape[1] * 100
    start = np.searchsorted(freqs, SPECTRAL_CLIFF_FLOOR_HZ)
    max_drop = 0.0
    for i in range(start, len(freqs) - 1):
        j = np.searchsorted(freqs, freqs[i] + 1000)
        if j >= len(freqs):
            break
        drop = float(occupancy[i] - occupancy[j])
        if drop > max_drop:
            max_drop = drop
    shape = "cliff" if max_drop >= SPECTRAL_CLIFF_HARD_PP else "gradual"
    return round(max_drop, 1), shape


def _classify_cutoff(freq_hz: float) -> str:
    if freq_hz < SPECTRAL_MP3_128_CUTOFF_HZ:
        return "MP3 ~128kbps or lower"
    if freq_hz < SPECTRAL_MP3_192_CUTOFF_HZ:
        return "MP3 ~192kbps"
    if freq_hz < SPECTRAL_MP3_320_CUTOFF_HZ:
        return "MP3 ~256–320kbps"
    return "likely genuine lossless"
