"""RED tests for T-2: core/reverdict.py (does not exist yet).

reverdict_from_raw(raw) must rebuild a verdict purely from stored sub-dicts,
delegating to core.verdict.compute_verdict — no audio loading, no FFT.
"""

import importlib

import pytest

from core.verdict import compute_verdict


# --- Real-shaped fixture dicts (clean lossless file -> CLUB READY) ---

def _clean_raw():
    """Smallest raw dict that compute_verdict accepts: a clean FLAC."""
    return {
        "meta": {
            "lame_header": False,
            "codec": "flac",
            "bitrate": 1000000,
            "bit_depth": 16,
        },
        "spectral": {
            "spectral_verdict": "OK",
            "top_freq_hz": 21800.0,
            "suspected_origin": "likely genuine lossless",
            "coverage_ratio": 0.989,
            "rolloff_shape": "gradual",
        },
        "integrity": {
            "lsb_zero_ratio": 0.10,
            "clip_events_L": 0,
            "clip_events_R": 0,
            "clip_max_ms": 0.0,
            "dynamic_range_db": 11.5,
            "noise_floor_dbfs": -72.0,
            "dc_offset_L": 0.0001,
            "dc_offset_R": 0.0001,
        },
        "loudness": {
            "true_peak_L_dbfs": -1.20,
            "true_peak_R_dbfs": -1.05,
            "loudness_lufs": -9.8,
        },
        "vinyl": None,
    }


def _do_not_play_raw():
    """A clipped, over-compressed lossy MP3 -> DO NOT PLAY."""
    raw = _clean_raw()
    raw["meta"] = {
        "lame_header": False,
        "codec": "mp3",
        "bitrate": 320000,
        "bit_depth": 16,
    }
    raw["spectral"] = {
        "spectral_verdict": "OK",
        "top_freq_hz": 16000.0,   # below 192 cutoff -> LOW_QUALITY_MP3
        "suspected_origin": "lossy 192kbps",
        "coverage_ratio": 0.72,
        "rolloff_shape": "cliff",
    }
    raw["integrity"]["clip_events_L"] = 40
    raw["integrity"]["clip_events_R"] = 5     # >20 -> CLIPPING
    raw["integrity"]["dynamic_range_db"] = 3.0  # <4 -> OVER_COMPRESSED
    return raw


@pytest.fixture
def mod():
    import core.reverdict as reverdict
    return importlib.reload(reverdict)


def test_returns_expected_keys(mod):
    result = mod.reverdict_from_raw(_clean_raw())
    assert isinstance(result, dict)
    assert set(result.keys()) == {"verdict", "flags", "reasons", "info_reasons"}


def test_equals_compute_verdict_clean(mod):
    raw = _clean_raw()
    expected = compute_verdict(
        raw["meta"], raw["spectral"], raw["integrity"],
        raw["loudness"], raw["vinyl"],
    )
    assert mod.reverdict_from_raw(raw) == expected


def test_equals_compute_verdict_do_not_play(mod):
    raw = _do_not_play_raw()
    expected = compute_verdict(
        raw["meta"], raw["spectral"], raw["integrity"],
        raw["loudness"], raw["vinyl"],
    )
    result = mod.reverdict_from_raw(raw)
    assert result == expected
    assert result["verdict"] == "DO NOT PLAY"


def test_vinyl_none_is_valid(mod):
    raw = _clean_raw()
    raw["vinyl"] = None
    result = mod.reverdict_from_raw(raw)
    assert result["verdict"] == "CLUB READY"


def test_missing_vinyl_key_raises_keyerror(mod):
    raw = _clean_raw()
    del raw["vinyl"]
    with pytest.raises(KeyError):
        mod.reverdict_from_raw(raw)


def test_does_not_load_audio_or_fft(mod, monkeypatch):
    """Pure dict->dict: must not import/use librosa, numpy FFT, or analyzer."""
    import core.reverdict as reverdict
    src = importlib.util.find_spec("core.reverdict").origin
    with open(src) as f:
        text = f.read()
    for forbidden in ("librosa", "soundfile", "analyzer.analyze", "np.fft", "scipy"):
        assert forbidden not in text, f"reverdict.py must not reference {forbidden}"
