#!/usr/bin/env python3
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.checks.flags
import core.runtime_config
from core.utils import numpy_to_native


# Module-level lazy delegators. These exist as attributes at import time (so
# tests can monkeypatch them) but pull their heavy-lib-backed implementations
# only when actually called — i.e. only on a real cache MISS, never on import.
def get_metadata(path):
    from core.checks.metadata import get_metadata as _f
    return _f(path)


def check_spectral(path):
    from core.checks.spectral import check_spectral as _f
    return _f(path)


def check_integrity(data, sr, path):
    from core.checks.integrity import check_integrity as _f
    return _f(data, sr, path)


def check_loudness(data, sr):
    from core.checks.loudness import check_loudness as _f
    return _f(data, sr)


def check_vinyl(data, sr, noise_floor_dbfs, click_count):
    from core.checks.vinyl import check_vinyl as _f
    return _f(data, sr, noise_floor_dbfs, click_count)


def count_clicks(data, sr):
    from core.checks.clicks import count_clicks as _f
    return _f(data, sr)


def compute_verdict(*args, **kwargs):
    from core.verdict import compute_verdict as _f
    return _f(*args, **kwargs)


def analyze_raw(path: str) -> tuple[dict, dict]:
    """Run all checks and return (raw_components, assembled_result).

    raw_components shape matches what core.cache stores in raw_json:
      {meta, spectral, integrity, loudness, vinyl, click_count, clip_times_sec}
    assembled_result is the full public dict (same shape as analyze()).

    Heavy audio libs (librosa/scipy/pyloudnorm/soundfile) are imported lazily
    via the module-level delegators above + the local soundfile import, so they
    load only when real analysis runs — never on import.
    """
    import soundfile as sf

    p = Path(path)
    if not p.exists():
        assembled = {"error": f"File not found: {path}"}
        return {}, assembled

    data, sr = sf.read(str(p), dtype="float32")

    meta = get_metadata(path)
    spectral = check_spectral(path)
    integrity = check_integrity(data, sr, path)
    loudness = check_loudness(data, sr)
    click_count = count_clicks(data, sr)
    vinyl = check_vinyl(data, sr, integrity["noise_floor_dbfs"], click_count)
    verdict = compute_verdict(meta, spectral, integrity, loudness, vinyl)

    raw = {
        "meta": meta,
        "spectral": spectral,
        "integrity": integrity,
        "loudness": loudness,
        "vinyl": vinyl,
        "click_count": click_count,
        "clip_times_sec": integrity["clip_times_sec"],
    }

    assembled = {
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
            "spectral_verdict": core.checks.flags.classify_coverage(spectral["coverage_ratio"], core.runtime_config.active()),
            "suspected_origin": spectral["suspected_origin"],
            "rolloff_shape": spectral["rolloff_shape"],
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
        "clip_times_sec": integrity["clip_times_sec"],
        "flags": verdict["flags"],
        "verdict": verdict["verdict"],
        "verdict_reasons": verdict["reasons"],
        "info_reasons": verdict["info_reasons"],
        "spectrogram_path": None,
    }

    return raw, assembled


def analyze(path: str, with_spectrogram: bool = False) -> dict:
    _, result = analyze_raw(path)

    if with_spectrogram and "error" not in result:
        try:
            from core.spectrogram import generate_spectrogram
            result["spectrogram_path"] = generate_spectrogram(path)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    import core.cache

    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <audio_file> [--spectrogram]", file=sys.stderr)
        sys.exit(1)

    with_spec = "--spectrogram" in sys.argv
    result = core.cache.get_or_analyze(sys.argv[1], with_spectrogram=with_spec)
    print(json.dumps(result, indent=2, default=numpy_to_native))
