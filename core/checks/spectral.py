import numpy as np
import librosa


def check_spectral(path: str, analysis_duration: float = 60.0) -> dict:
    y, sr = librosa.load(path, sr=None, mono=True, duration=analysis_duration)

    fft = np.abs(librosa.stft(y, n_fft=4096))
    fft_db = librosa.amplitude_to_db(fft, ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    avg_per_bin = fft_db.mean(axis=1)
    active_bins = np.where(avg_per_bin > -80)[0]

    nyquist = sr / 2
    if len(active_bins) == 0:
        top_freq = 0.0
        ratio = 0.0
    else:
        top_freq = float(freqs[active_bins[-1]])
        ratio = top_freq / nyquist

    if ratio < 0.85:
        verdict = "FAKE_LOSSLESS"
    elif ratio < 0.92:
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
    if freq_hz < 17000:
        return "MP3 <=128kbps"
    if freq_hz < 19000:
        return "MP3 192kbps"
    if freq_hz < 20500:
        return "MP3 320kbps"
    return "likely genuine lossless"
