import numpy as np


def count_clicks(data: np.ndarray, sr: int) -> int:
    mono = data.mean(axis=1) if data.ndim > 1 else data
    max_click_samples = int(sr * 0.005)  # 5ms
    block = sr // 4
    clicks = 0
    for i in range(0, len(mono) - block, block):
        seg = mono[i:i + block]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms < 1e-4:
            continue
        threshold = rms * 50  # ~34dB above local RMS
        above = np.where(np.abs(seg) > threshold)[0]
        if len(above) == 0:
            continue
        gaps = np.diff(above)
        bursts = 1 + np.sum(gaps > max_click_samples)
        clicks += int(bursts)
    return clicks
