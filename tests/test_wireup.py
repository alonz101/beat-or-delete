"""RED tests for T-4 (analyzer.py wire-up) and T-5 (batch.py swap)."""
import importlib
from pathlib import Path


# ---------------------------------------------------------------------------
# T-4: analyze_raw() added to core/analyzer.py
# ---------------------------------------------------------------------------

def test_analyze_raw_exists():
    """analyze_raw must be importable from core.analyzer."""
    from core import analyzer  # noqa: F401
    assert hasattr(analyzer, "analyze_raw"), "analyze_raw not found in core.analyzer"


def test_analyze_raw_returns_tuple(monkeypatch):
    """analyze_raw(path) -> (raw_components: dict, assembled: dict)."""
    import core.analyzer as mod
    import numpy as np
    import soundfile as sf

    _meta = {
        "container": "FLAC", "codec": "flac", "sample_rate": 44100,
        "bit_depth": 16, "bitrate": 900000, "duration": 1.0,
        "channels": 2, "lame_header": False,
    }
    _spectral = {
        "coverage_ratio": 0.99, "top_freq_hz": 22000.0, "nyquist_hz": 22050,
        "spectral_verdict": "GENUINE", "suspected_origin": "lossless",
        "rolloff_shape": "gradual", "rolloff_cliff_pp": 2.0,
    }
    _integrity = {
        "clip_events_L": 0, "clip_events_R": 0, "clip_max_ms": 0.0,
        "peak_dbfs": -3.0, "dynamic_range_db": 12.0, "noise_floor_dbfs": -70.0,
        "dc_offset_L": 0.0, "dc_offset_R": 0.0, "lsb_zero_ratio": 0.1,
        "clip_times_sec": [],
    }
    _loudness = {"loudness_lufs": -14.0, "true_peak_L_dbfs": -3.0, "true_peak_R_dbfs": -3.0}
    _vinyl = {"vinyl_rip": False}
    _verdict = {"verdict": "CLUB READY", "flags": [], "reasons": [], "info_reasons": []}

    monkeypatch.setattr(mod, "get_metadata", lambda p: _meta)
    monkeypatch.setattr(mod, "check_spectral", lambda p: _spectral)
    monkeypatch.setattr(mod, "check_integrity", lambda data, sr, p: _integrity)
    monkeypatch.setattr(mod, "check_loudness", lambda data, sr: _loudness)
    monkeypatch.setattr(mod, "count_clicks", lambda data, sr: 0)
    monkeypatch.setattr(mod, "check_vinyl", lambda data, sr, nf, cc: _vinyl)
    monkeypatch.setattr(mod, "compute_verdict", lambda *a, **kw: _verdict)
    monkeypatch.setattr(sf, "read", lambda *a, **kw: (np.zeros((44100, 2), dtype="float32"), 44100))

    fake = Path("/tmp/fake_test.flac")
    fake.touch()
    try:
        result = mod.analyze_raw(str(fake))
        assert isinstance(result, tuple) and len(result) == 2
        raw, assembled = result
        assert isinstance(raw, dict)
        assert isinstance(assembled, dict)
    finally:
        fake.unlink(missing_ok=True)


def test_analyze_raw_components_shape(monkeypatch):
    """raw_components must have the 7 expected keys."""
    import core.analyzer as mod
    import numpy as np
    import soundfile as sf

    _meta = {
        "container": "FLAC", "codec": "flac", "sample_rate": 44100,
        "bit_depth": 16, "bitrate": 900000, "duration": 1.0,
        "channels": 2, "lame_header": False,
    }
    _spectral = {
        "coverage_ratio": 0.99, "top_freq_hz": 22000.0, "nyquist_hz": 22050,
        "spectral_verdict": "GENUINE", "suspected_origin": "lossless",
        "rolloff_shape": "gradual", "rolloff_cliff_pp": 2.0,
    }
    _integrity = {
        "clip_events_L": 0, "clip_events_R": 0, "clip_max_ms": 0.0,
        "peak_dbfs": -3.0, "dynamic_range_db": 12.0, "noise_floor_dbfs": -70.0,
        "dc_offset_L": 0.0, "dc_offset_R": 0.0, "lsb_zero_ratio": 0.1,
        "clip_times_sec": [],
    }
    _loudness = {"loudness_lufs": -14.0, "true_peak_L_dbfs": -3.0, "true_peak_R_dbfs": -3.0}
    _vinyl = {"vinyl_rip": False}
    _verdict = {"verdict": "CLUB READY", "flags": [], "reasons": [], "info_reasons": []}

    monkeypatch.setattr(mod, "get_metadata", lambda p: _meta)
    monkeypatch.setattr(mod, "check_spectral", lambda p: _spectral)
    monkeypatch.setattr(mod, "check_integrity", lambda data, sr, p: _integrity)
    monkeypatch.setattr(mod, "check_loudness", lambda data, sr: _loudness)
    monkeypatch.setattr(mod, "count_clicks", lambda data, sr: 0)
    monkeypatch.setattr(mod, "check_vinyl", lambda data, sr, nf, cc: _vinyl)
    monkeypatch.setattr(mod, "compute_verdict", lambda *a, **kw: _verdict)
    monkeypatch.setattr(sf, "read", lambda *a, **kw: (np.zeros((44100, 2), dtype="float32"), 44100))

    fake = Path("/tmp/fake_test2.flac")
    fake.touch()
    try:
        raw, _ = mod.analyze_raw(str(fake))
        expected_keys = {"meta", "spectral", "integrity", "loudness", "vinyl", "click_count", "clip_times_sec"}
        assert set(raw.keys()) == expected_keys, f"raw keys: {set(raw.keys())}"
    finally:
        fake.unlink(missing_ok=True)


def test_analyze_still_works(monkeypatch):
    """analyze() public shape is unchanged after refactor."""
    import core.analyzer as mod
    import numpy as np

    _meta = {
        "container": "FLAC", "codec": "flac", "sample_rate": 44100,
        "bit_depth": 16, "bitrate": 900000, "duration": 1.0,
        "channels": 2, "lame_header": False,
    }
    _spectral = {
        "coverage_ratio": 0.99, "top_freq_hz": 22000.0, "nyquist_hz": 22050,
        "spectral_verdict": "GENUINE", "suspected_origin": "lossless",
        "rolloff_shape": "gradual", "rolloff_cliff_pp": 2.0,
    }
    _integrity = {
        "clip_events_L": 0, "clip_events_R": 0, "clip_max_ms": 0.0,
        "peak_dbfs": -3.0, "dynamic_range_db": 12.0, "noise_floor_dbfs": -70.0,
        "dc_offset_L": 0.0, "dc_offset_R": 0.0, "lsb_zero_ratio": 0.1,
        "clip_times_sec": [],
    }
    _loudness = {"loudness_lufs": -14.0, "true_peak_L_dbfs": -3.0, "true_peak_R_dbfs": -3.0}
    _vinyl = {"vinyl_rip": False}
    _verdict = {"verdict": "CLUB READY", "flags": [], "reasons": [], "info_reasons": []}

    # Patch at the core.analyzer module level (uses `from X import Y` bindings)
    import core.analyzer
    monkeypatch.setattr(core.analyzer, "get_metadata", lambda p: _meta)
    monkeypatch.setattr(core.analyzer, "check_spectral", lambda p: _spectral)
    monkeypatch.setattr(core.analyzer, "check_integrity", lambda data, sr, p: _integrity)
    monkeypatch.setattr(core.analyzer, "check_loudness", lambda data, sr: _loudness)
    monkeypatch.setattr(core.analyzer, "count_clicks", lambda data, sr: 0)
    monkeypatch.setattr(core.analyzer, "check_vinyl", lambda data, sr, nf, cc: _vinyl)
    monkeypatch.setattr(core.analyzer, "compute_verdict", lambda *a, **kw: _verdict)
    import soundfile as sf
    monkeypatch.setattr(sf, "read", lambda *a, **kw: (np.zeros((44100, 2), dtype="float32"), 44100))

    fake = Path("/tmp/fake_test3.flac")
    fake.touch()
    try:
        result = mod.analyze(str(fake))
        expected_keys = {
            "filename", "file_path", "format", "authenticity", "playability",
            "vinyl", "click_count", "clip_times_sec", "flags", "verdict",
            "verdict_reasons", "info_reasons", "spectrogram_path",
        }
        assert set(result.keys()) == expected_keys, f"analyze() shape changed: {set(result.keys())}"
    finally:
        fake.unlink(missing_ok=True)


def test_analyzer_main_uses_cache():
    """CLI entry delegates to main(), which must route through get_or_analyze, not analyze."""
    src = Path(__file__).parent.parent / "core" / "analyzer.py"
    text = src.read_text()
    guard_idx = text.index("if __name__")
    # The __main__ guard must delegate to main(), not do the work inline.
    main_guard = text[guard_idx:]
    assert "main(" in main_guard, "__main__ block must delegate to main()"
    # main()'s body (from its def up to the guard) must use the cache.
    main_body = text[text.index("def main("):guard_idx]
    assert "get_or_analyze" in main_body, "main() still calls analyze(), not get_or_analyze"


# ---------------------------------------------------------------------------
# T-5: batch.py import and pool.submit swap
# ---------------------------------------------------------------------------

def test_batch_imports_get_or_analyze():
    """batch.py must import get_or_analyze from core.cache."""
    src = Path(__file__).parent.parent / "batch.py"
    text = src.read_text()
    assert "from core.cache import get_or_analyze" in text, \
        "batch.py still imports analyze from core.analyzer"


def test_batch_uses_get_or_analyze():
    """batch.py pool.submit must use get_or_analyze, not analyze."""
    src = Path(__file__).parent.parent / "batch.py"
    text = src.read_text()
    assert "pool.submit(get_or_analyze" in text, \
        "batch.py pool.submit still uses analyze instead of get_or_analyze"
