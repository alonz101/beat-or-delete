import numpy as np
import soundfile as sf
import pyloudnorm as pyln


def check_loudness(path: str) -> dict:
    data, sr = sf.read(path, dtype="float32")
    meter = pyln.Meter(sr)

    loudness_lufs = round(meter.integrated_loudness(data), 2)

    # True peak per channel
    if data.ndim > 1:
        peak_L = round(20 * np.log10(np.max(np.abs(data[:, 0])) + 1e-12), 2)
        peak_R = round(20 * np.log10(np.max(np.abs(data[:, 1])) + 1e-12), 2)
    else:
        peak_L = round(20 * np.log10(np.max(np.abs(data)) + 1e-12), 2)
        peak_R = peak_L

    return {
        "loudness_lufs": loudness_lufs,
        "true_peak_L_dbfs": peak_L,
        "true_peak_R_dbfs": peak_R,
    }
