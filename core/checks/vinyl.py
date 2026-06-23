import numpy as np
import soundfile as sf
from scipy.signal import correlate
from scipy.fft import rfft, rfftfreq


def check_vinyl(path: str, noise_floor_dbfs: float, click_count: int) -> dict:
    """
    Heuristics to detect vinyl rips and assess their quality.
    Returns vinyl_rip flag, wow_flutter_wrms, hum_hz, and vinyl_grade.
    """
    data, sr = sf.read(path, dtype="float32")
    mono = data.mean(axis=1) if data.ndim > 1 else data

    hum_hz = _detect_hum(mono, sr)
    wow_flutter = _estimate_wow_flutter(mono, sr)
    is_vinyl = _is_likely_vinyl(noise_floor_dbfs, click_count, hum_hz, wow_flutter)

    if not is_vinyl:
        return {
            "vinyl_rip": False,
            "wow_flutter_wrms": None,
            "hum_hz": None,
            "vinyl_grade": None,
        }

    # Grade the vinyl rip
    grade = _grade_vinyl(noise_floor_dbfs, click_count, wow_flutter, hum_hz)

    return {
        "vinyl_rip": True,
        "wow_flutter_wrms": round(wow_flutter, 4),
        "hum_hz": hum_hz,
        "vinyl_grade": grade,
    }


def _detect_hum(mono: np.ndarray, sr: int) -> float | None:
    """Detect 50Hz or 60Hz hum via FFT spike detection."""
    chunk = mono[:sr * 10]  # first 10s
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
    """
    Estimate wow & flutter as WRMS of short-term pitch deviation.
    Uses zero-crossing rate as a pitch proxy — fast and dependency-free.
    """
    block = int(sr * block_size)
    zcr_vals = []
    for i in range(0, len(mono) - block, block):
        seg = mono[i:i + block]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms < 0.001:  # skip silence
            continue
        zc = np.sum(np.diff(np.sign(seg)) != 0)
        zcr_vals.append(zc / block)

    if len(zcr_vals) < 10:
        return 0.0

    zcr = np.array(zcr_vals)
    mean_zcr = np.mean(zcr)
    if mean_zcr == 0:
        return 0.0

    # WRMS of deviation from mean (normalized)
    deviation = (zcr - mean_zcr) / mean_zcr
    # Weight toward wow (low freq) by smoothing
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(deviation, size=20)
    wrms = float(np.sqrt(np.mean(smoothed ** 2)))
    return min(wrms, 1.0)  # cap at 1.0


def _is_likely_vinyl(
    noise_floor: float,
    click_count: int,
    hum_hz: float | None,
    wow_flutter: float,
) -> bool:
    """Heuristic: is this file likely a vinyl rip?"""
    # Hard gate: clean digital files have noise floors below -62 dBFS.
    # Without this, hum + ZCR flutter false-positives on Bandcamp/Beatport files.
    # Use a slightly looser threshold for the gate (-58) vs the scoring threshold (-55)
    has_elevated_noise = noise_floor != -120.0 and noise_floor > -58
    has_clicks = click_count is not None and click_count >= 1
    has_hum = hum_hz is not None

    # Gate: require physical noise hiss or actual clicks.
    # Hum alone is not enough — it can false-positive on bass content in clean digital files.
    if not has_elevated_noise and not has_clicks:
        return False

    has_hard_indicator = has_elevated_noise or has_hum or has_clicks

    score = 0
    if has_elevated_noise:
        score += 2
    if click_count is not None:
        if click_count >= 3:
            score += 2
        elif click_count >= 1:
            score += 1
    if has_hum:
        score += 3
    # Wow/flutter only counts when at least one other indicator is present
    if wow_flutter > 0.3 and has_hard_indicator:
        score += 1
    return score >= 3


def _grade_vinyl(
    noise_floor: float,
    click_count: int,
    wow_flutter: float,
    hum_hz: float | None,
) -> str:
    issues = 0
    if noise_floor != -120.0 and noise_floor > -45:
        issues += 2
    elif noise_floor != -120.0 and noise_floor > -55:
        issues += 1
    if click_count > 5:
        issues += 2
    elif click_count > 0:
        issues += 1
    if wow_flutter > 0.15:
        issues += 2
    elif wow_flutter > 0.05:
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
