import numpy as np
import soundfile as sf

from core.config import CLIP_SAMPLE_THRESHOLD, CLIP_MIN_RUN


def _clip_events(channel: np.ndarray, sr: int) -> tuple[int, float, list[float]]:
    # Avoid a full-length np.abs copy; symmetric threshold → OR of the two bounds.
    at_max = (channel >= CLIP_SAMPLE_THRESHOLD) | (channel <= -CLIP_SAMPLE_THRESHOLD)
    if not at_max.any():
        return 0, 0.0, []
    padded = np.concatenate([[False], at_max, [False]])
    changes = np.diff(padded.astype(np.int8))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    lengths = ends - starts
    valid_mask = lengths >= CLIP_MIN_RUN
    events = lengths[valid_mask]
    if len(events) == 0:
        return 0, 0.0, []
    valid_starts = starts[valid_mask]
    times_sec = [round(float(s / sr), 3) for s in valid_starts]
    return int(len(events)), float(events.max()) / sr * 1000, times_sec


def check_integrity(data: np.ndarray, sr: int, path: str) -> dict:
    mono = data.mean(axis=1) if data.ndim > 1 else data

    # Per-channel clipping events (contiguous runs of >= CLIP_MIN_RUN samples at ceiling)
    if data.ndim > 1:
        events_L, max_ms_L, times_L = _clip_events(data[:, 0], sr)
        events_R, max_ms_R, times_R = _clip_events(data[:, 1], sr)
    else:
        events_L, max_ms_L, times_L = _clip_events(data, sr)
        events_R, max_ms_R, times_R = events_L, max_ms_L, times_L
    clip_max_ms = round(max(max_ms_L, max_ms_R), 2)
    # Merge L+R clip times, deduplicate within 0.1s window, sort
    clip_times_sec = sorted(set(round(t, 1) for t in times_L + times_R))

    # Peak — scalar reductions, no full-length np.abs copy
    peak = max(abs(float(data.max())), abs(float(data.min())))
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

    # Dynamic range: crest factor over loud sections (excludes quiet intros/outros)
    block3 = 3 * sr
    rms_lin, peak_lin = [], []
    for i in range(0, len(mono) - block3, block3):
        seg = mono[i:i + block3]
        r = float(np.sqrt(np.mean(seg ** 2)))
        p = float(np.max(np.abs(seg)))
        if r > 1e-6:
            rms_lin.append(r)
            peak_lin.append(p)
    if len(rms_lin) > 1:
        cutoff = float(np.percentile(rms_lin, 25))
        loud_r = [r for r in rms_lin if r >= cutoff]
        loud_p = [p for r, p in zip(rms_lin, peak_lin) if r >= cutoff]
        rms_avg = float(np.sqrt(np.mean(np.array(loud_r) ** 2)))
        peak_avg = float(np.mean(loud_p))
        dynamic_range = round(20 * np.log10(peak_avg / (rms_avg + 1e-12)), 1)
    else:
        dynamic_range = 0.0

    # Fake 24-bit: needs int32 read — can't derive from float32. Stream in blocks
    # so we never hold a second full-length copy of the file (~342MB → ~8MB window).
    zeros = 0
    total = 0
    for blk in sf.blocks(path, blocksize=1 << 20, dtype="int32"):
        lsb = blk & 0xFF
        zeros += int(np.count_nonzero(lsb == 0))
        total += lsb.size
    lsb_zero_ratio = round(zeros / total, 4) if total else 0.0

    return {
        "clip_events_L": events_L,
        "clip_events_R": events_R,
        "clip_max_ms": clip_max_ms,
        "clip_times_sec": clip_times_sec,
        "peak_dbfs": peak_dbfs,
        "dc_offset_L": dc_L,
        "dc_offset_R": dc_R,
        "noise_floor_dbfs": noise_floor,
        "dynamic_range_db": dynamic_range,
        "lsb_zero_ratio": lsb_zero_ratio,
    }
