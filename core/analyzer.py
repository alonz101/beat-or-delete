#!/usr/bin/env python3
import sys
import json
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.checks.metadata import get_metadata
from core.checks.spectral import check_spectral
from core.checks.integrity import check_integrity
from core.checks.loudness import check_loudness
from core.checks.vinyl import check_vinyl
from core.checks.clicks import count_clicks
from core.verdict import compute_verdict
from core.spectrogram import generate_spectrogram
from core.utils import numpy_to_native


def analyze(path: str, with_spectrogram: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}

    # Load audio once — all float32 checks share this
    data, sr = sf.read(str(p), dtype="float32")

    meta = get_metadata(path)
    spectral = check_spectral(path)
    integrity = check_integrity(data, sr, path)
    loudness = check_loudness(data, sr)
    click_count = count_clicks(data, sr)
    vinyl = check_vinyl(data, sr, integrity["noise_floor_dbfs"], click_count)

    verdict = compute_verdict(meta, spectral, integrity, loudness, vinyl)

    result = {
        "filename": p.name,
        "file_path": str(p.resolve()),
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
            "clip_events_L": integrity["clip_events_L"],
            "clip_events_R": integrity["clip_events_R"],
            "clip_max_ms": integrity["clip_max_ms"],
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
        "info_reasons": verdict["info_reasons"],
        "spectrogram_path": None,
    }

    if with_spectrogram:
        try:
            result["spectrogram_path"] = generate_spectrogram(path)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <audio_file> [--spectrogram]", file=sys.stderr)
        sys.exit(1)

    with_spec = "--spectrogram" in sys.argv
    result = analyze(sys.argv[1], with_spectrogram=with_spec)
    print(json.dumps(result, indent=2, default=numpy_to_native))
