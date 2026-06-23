import numpy as np
import soundfile as sf

from core.config import CLIP_SAMPLE_THRESHOLD, CLIP_MIN_RUN


def _clip_events(channel: np.ndarray, sr: int) -> tuple[int, float]:
    at_max = np.abs(channel) >= CLIP_SAMPLE_THRESHOLD
    if not at_max.any():
        return 0, 0.0
    padded = np.concatenate([[False], at_max, [False]])
    changes = np.diff(padded.astype(np.int8))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    lengths = ends - starts
    events = lengths[lengths >= CLIP_MIN_RUN]
    if len(events) == 0:
        return 0, 0.0
    return int(len(events)), float(events.max()) / sr * 1000


def check_integrity(data: np.ndarray, sr: int, path: str) -> dict:
    mono = data.mean(axis=1) if data.ndim > 1 else data

    # Per-channel clipping events (contiguous runs of >= CLIP_MIN_RUN samples at ceiling)
    if data.ndim > 1:
        events_L, max_ms_L = _clip_events(data[:, 0], sr)
        events_R, max_ms_R = _clip_events(data[:, 1], sr)
    else:
        events_L, max_ms_L = _clip_events(data, sr)
        events_R, max_ms_R = events_L, max_ms_L
    clip_max_ms = round(max(max_ms_L, max_ms_R), 2)

    # Peak
    peak = float(np.max(np.abs(data)))
    peak_dbfs = round(20 * np.log10(peak + 1e-12), 2)

    # DC offset per channel
    if data.ndim > 1:
        dc_L = round(float(np.mean(data[:, 0])), 6)
        dc_R = round(float(np.mean(data[:, 1])), 6)
    else:
        dc_L = round(float(np.mean(data)), 6)
        dc_R = dc_L

    # Noise floor: only from blocks that are >35dB below the loudest block
    block = sr // 2
    rms_blocks_raw = []
    for i in range(0, len(mono) - block, block):
        seg = mono[i:i + block]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms > 1e-9:
            rms_blocks_raw.append(20 * np.log10(rms))

    if rms_blocks_raw:
        peak_rms = max(rms_blocks_raw)
        silent_blocks = [v for v in rms_blocks_raw if v < peak_rms - 35]
        noise_floor = round(float(np.mean(silent_blocks)), 2) if silent_blocks else -120.0
    else:
        noise_floor = -120.0

    # Dynamic range (spread of 3s RMS blocks)
    block3 = 3 * sr
    rms3 = []
    for i in range(0, len(mono) - block3, block3):
        seg = mono[i:i + block3]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms > 1e-6:
            rms3.append(20 * np.log10(rms))
    dynamic_range = round(max(rms3) - min(rms3), 1) if len(rms3) > 1 else 0.0

    # Fake 24-bit: needs int32 read — can't derive from float32
    data_int, _ = sf.read(path, dtype="int32")
    lsb_mask = data_int & 0xFF
    lsb_zero_ratio = round(float(np.sum(lsb_mask == 0) / lsb_mask.size), 4)

    return {
        "clip_events_L": events_L,
        "clip_events_R": events_R,
        "clip_max_ms": clip_max_ms,
        "peak_dbfs": peak_dbfs,
        "dc_offset_L": dc_L,
        "dc_offset_R": dc_R,
        "noise_floor_dbfs": noise_floor,
        "dynamic_range_db": dynamic_range,
        "lsb_zero_ratio": lsb_zero_ratio,
    }
