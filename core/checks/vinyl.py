import numpy as np
from scipy.fft import rfft, rfftfreq

from core.config import (
    VINYL_NOISE_GATE_DBFS,
    VINYL_ELEVATED_NOISE_DBFS,
    VINYL_MIN_SCORE,
    VINYL_CLICK_MANY,
    VINYL_CLICK_FEW,
    VINYL_HUM_SCORE,
    VINYL_WOW_FLUTTER_FLAG,
    VINYL_GRADE_NOISE_POOR_DBFS,
    VINYL_GRADE_NOISE_ACCEPTABLE_DBFS,
    VINYL_GRADE_CLICK_POOR,
)


def check_vinyl(
    data: np.ndarray,
    sr: int,
    noise_floor_dbfs: float,
    click_count: int,
) -> dict:
    mono = data.mean(axis=1) if data.ndim > 1 else data

    hum_hz = _detect_hum(mono, sr)
    wow_flutter = _estimate_wow_flutter(mono, sr)
    is_vinyl = _is_likely_vinyl(noise_floor_dbfs, click_count, hum_hz)

    if not is_vinyl:
        return {"vinyl_rip": False, "wow_flutter_wrms": None, "hum_hz": None, "vinyl_grade": None}

    grade = _grade_vinyl(noise_floor_dbfs, click_count, hum_hz)

    return {
        "vinyl_rip": True,
        "wow_flutter_wrms": round(wow_flutter, 4),
        "hum_hz": hum_hz,
        "vinyl_grade": grade,
    }


def _detect_hum(mono: np.ndarray, sr: int) -> float | None:
    chunk = mono[:sr * 10]
    fft = np.abs(rfft(chunk))
    freqs = rfftfreq(len(chunk), 1 / sr)

    for target in [50.0, 60.0]:
        mask = (freqs >= target - 2) & (freqs <= target + 2)
        local = (freqs >= target - 20) & (freqs <= target + 20) & ~mask
        if mask.any() and local.any():
            peak = fft[mask].max()
            baseline = np.percentile(fft[local], 75)
            if baseline > 0 and (peak / baseline) > 10:
                return float(target)
    return None


def _estimate_wow_flutter(mono: np.ndarray, sr: int, block_size: float = 0.05) -> float:
    block = int(sr * block_size)
    zcr_vals = []
    for i in range(0, len(mono) - block, block):
        seg = mono[i:i + block]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms < 0.001:
            continue
        zc = np.sum(np.diff(np.sign(seg)) != 0)
        zcr_vals.append(zc / block)

    if len(zcr_vals) < 10:
        return 0.0

    zcr = np.array(zcr_vals)
    mean_zcr = np.mean(zcr)
    if mean_zcr == 0:
        return 0.0

    deviation = (zcr - mean_zcr) / mean_zcr
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(deviation, size=20)
    wrms = float(np.sqrt(np.mean(smoothed ** 2)))
    return min(wrms, 1.0)


def _is_likely_vinyl(
    noise_floor: float,
    click_count: int,
    hum_hz: float | None,
) -> bool:
    has_elevated_noise = noise_floor != -120.0 and noise_floor > VINYL_NOISE_GATE_DBFS
    has_clicks = click_count is not None and click_count >= VINYL_CLICK_FEW
    has_hum = hum_hz is not None

    if not has_elevated_noise and not has_clicks and not has_hum:
        return False

    score = 0
    if has_elevated_noise:
        score += 2
    if click_count is not None:
        if click_count >= VINYL_CLICK_MANY:
            score += 2
        elif click_count >= VINYL_CLICK_FEW:
            score += 1
    if has_hum:
        score += VINYL_HUM_SCORE

    return score >= VINYL_MIN_SCORE


def _grade_vinyl(
    noise_floor: float,
    click_count: int,
    hum_hz: float | None,
) -> str:
    issues = 0
    if noise_floor != -120.0 and noise_floor > VINYL_GRADE_NOISE_POOR_DBFS:
        issues += 2
    elif noise_floor != -120.0 and noise_floor > VINYL_GRADE_NOISE_ACCEPTABLE_DBFS:
        issues += 1
    if click_count > VINYL_GRADE_CLICK_POOR:
        issues += 2
    elif click_count > 0:
        issues += 1
    if hum_hz is not None:
        issues += 1

    if issues == 0:
        return "EXCELLENT"
    if issues <= 1:
        return "GOOD"
    if issues <= 3:
        return "ACCEPTABLE"
    return "POOR"
