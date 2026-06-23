#!/usr/bin/env python3
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.checks.metadata import get_metadata
from core.checks.spectral import check_spectral
from core.checks.integrity import check_integrity
from core.checks.loudness import check_loudness
from core.checks.vinyl import check_vinyl
from core.verdict import compute_verdict
from core.spectrogram import generate_spectrogram


def analyze(path: str, with_spectrogram: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}

    meta = get_metadata(path)
    spectral = check_spectral(path)
    integrity = check_integrity(path)
    loudness = check_loudness(path)

    # Count clicks for vinyl check (samples >20dB above local RMS, <5ms)
    click_count = _count_clicks(path)
    vinyl = check_vinyl(path, integrity["noise_floor_dbfs"], click_count)

    verdict = compute_verdict(meta, spectral, integrity, loudness, vinyl)

    result = {
        "filename": p.name,
        "format": {
            "container": meta["container"],
            "codec": meta["codec"],
            "sample_rate": meta["sample_rate"],
            "bit_depth": meta["bit_depth"],
            "bitrate": meta["bitrate"],
            "duration": meta["duration"],
            "channels": meta["channels"],
        },
        "authenticity": {
            "lame_header": meta["lame_header"],
            "spectral_coverage_ratio": spectral["coverage_ratio"],
            "top_freq_hz": spectral["top_freq_hz"],
            "nyquist_hz": spectral["nyquist_hz"],
            "spectral_verdict": spectral["spectral_verdict"],
            "suspected_origin": spectral["suspected_origin"],
            "lsb_zero_ratio": integrity["lsb_zero_ratio"],
        },
        "playability": {
            "clipped_samples_L": integrity["clipped_samples_L"],
            "clipped_samples_R": integrity["clipped_samples_R"],
            "peak_dbfs": integrity["peak_dbfs"],
            "loudness_lufs": loudness["loudness_lufs"],
            "true_peak_L_dbfs": loudness["true_peak_L_dbfs"],
            "true_peak_R_dbfs": loudness["true_peak_R_dbfs"],
            "dynamic_range_db": integrity["dynamic_range_db"],
            "noise_floor_dbfs": integrity["noise_floor_dbfs"],
            "dc_offset_L": integrity["dc_offset_L"],
            "dc_offset_R": integrity["dc_offset_R"],
        },
        "vinyl": vinyl,
        "click_count": click_count,
        "flags": verdict["flags"],
        "verdict": verdict["verdict"],
        "verdict_reasons": verdict["reasons"],
        "spectrogram_path": None,
    }

    if with_spectrogram:
        try:
            result["spectrogram_path"] = generate_spectrogram(path)
        except Exception:
            pass

    return result


def _count_clicks(path: str) -> int:
    import soundfile as sf
    import numpy as np
    data, sr = sf.read(path, dtype="float32")
    mono = data.mean(axis=1) if data.ndim > 1 else data
    max_click_samples = int(sr * 0.005)  # 5ms
    block = sr // 4
    clicks = 0
    for i in range(0, len(mono) - block, block):
        seg = mono[i:i + block]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms < 1e-4:
            continue
        threshold = rms * 50  # ~34dB above local RMS — well above musical transients
        above = np.where(np.abs(seg) > threshold)[0]
        if len(above) == 0:
            continue
        # Count isolated bursts (groups of samples close together)
        gaps = np.diff(above)
        bursts = 1 + np.sum(gaps > max_click_samples)
        clicks += int(bursts)
    return clicks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <audio_file> [--spectrogram]", file=sys.stderr)
        sys.exit(1)

    with_spec = "--spectrogram" in sys.argv
    result = analyze(sys.argv[1], with_spectrogram=with_spec)

    def to_native(obj):
        import numpy as np
        if isinstance(obj, (np.floating, np.float32, np.float64)): return float(obj)
        if isinstance(obj, (np.integer,)): return int(obj)
        return obj

    print(json.dumps(result, indent=2, default=to_native))
