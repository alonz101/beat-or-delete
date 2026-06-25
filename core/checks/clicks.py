import numpy as np

_CLICK_RATIO = 50.0  # |d2| / local_rms > this → click/pop
_BLOCK_MS = 1000     # normalization window in ms


def count_clicks(data: np.ndarray, sr: int) -> int:
    mono = data.mean(axis=1) if data.ndim > 1 else data
    d2 = np.diff(mono, n=2)
    local_rms = _local_rms(d2, block_size=max(sr * _BLOCK_MS // 1000, 100))
    ratio = np.abs(d2) / local_rms
    return _count_events(ratio > _CLICK_RATIO, max_gap=max(int(sr * 0.005), 1))


def _local_rms(signal: np.ndarray, block_size: int) -> np.ndarray:
    out = np.ones(len(signal)) * 1e-10
    for i in range(0, len(signal), block_size):
        seg = signal[i:i + block_size]
        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) > 0 else 0.0
        out[i:i + block_size] = max(rms, 1e-10)
    return out


def _count_events(mask: np.ndarray, max_gap: int) -> int:
    if not mask.any():
        return 0
    above = np.where(mask)[0]
    gaps = np.diff(above)
    return int(1 + np.sum(gaps > max_gap))
