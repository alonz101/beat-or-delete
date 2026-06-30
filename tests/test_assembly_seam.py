"""RED tests for T-4 (Wave 3, solo): the assembly seam.

After T-3, `core/checks/spectral.py` no longer emits a ``spectral_verdict`` key and
`core/checks/flags.py` exposes ``classify_coverage(coverage_ratio, cfg)``. The two
places that assemble the public result dict still read the dropped key:

    core/analyzer.py  analyze_raw()  -> authenticity.spectral_verdict = spectral["spectral_verdict"]
    core/cache.py     _assemble()    -> authenticity.spectral_verdict = spectral["spectral_verdict"]

T-4's contract: both must derive the label at verdict-time via
``flags.classify_coverage(spectral["coverage_ratio"], runtime_config.active())``.

Until T-4 lands, every path that touches assembly raises ``KeyError: 'spectral_verdict'``
on a raw blob shaped like the real (post-T-3) pipeline output — that's the RED.

Fixtures/style mirror tests/test_cache.py (temp HOME via tmp db_path, reloaded
core.cache with monkeypatched _db_path, an analyze counter, numpy dtypes).
"""

import importlib
import sqlite3
from pathlib import Path

import numpy as np
import pytest

import core.analyzer
import core.config_hash
import core.reverdict
import core.verdict
import core.runtime_config as runtime_config
from core.checks.flags import classify_coverage


# --------------------------------------------------------------------------- #
# Isolation: never let injected overrides / cached active() leak across tests.
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _reset_runtime_config():
    runtime_config.reset()
    yield
    runtime_config.reset()


# --------------------------------------------------------------------------- #
# Raw blob shaped like the REAL post-T-3 pipeline: has coverage_ratio, NO
# spectral_verdict key. Numeric fields use the numpy scalar types the real
# check modules produce (the type-fidelity rule) — plain float/int would mask
# the json/sqlite round-trip the cache performs.
# --------------------------------------------------------------------------- #

def _make_raw_no_sv(path, *, coverage=0.989, dynamic_range=11.5, codec="flac"):
    """raw_components half of analyze_raw()'s return, WITHOUT spectral_verdict."""
    return {
        "meta": {
            "container": codec,
            "codec": codec,
            "sample_rate": 44100,
            "bit_depth": 16,
            "bitrate": 1_000_000,
            "duration": 312.5,
            "channels": 2,
            "lame_header": False,
        },
        "spectral": {
            # NOTE: deliberately NO "spectral_verdict" key — this is the seam.
            "coverage_ratio": np.float64(coverage),
            "top_freq_hz": np.float32(21800.0),
            "nyquist_hz": np.float32(22050.0),
            "suspected_origin": "likely genuine lossless",
            "rolloff_shape": "gradual",
        },
        "integrity": {
            "clip_events_L": np.int64(0),
            "clip_events_R": np.int64(0),
            "clip_max_ms": np.float32(0.0),
            "peak_dbfs": np.float32(-1.10),
            "dynamic_range_db": np.float32(dynamic_range),
            "noise_floor_dbfs": np.float32(-72.0),
            "dc_offset_L": np.float32(0.0001),
            "dc_offset_R": np.float32(0.0001),
            "lsb_zero_ratio": np.float64(0.10),
            "clip_times_sec": [],
        },
        "loudness": {
            "loudness_lufs": np.float32(-9.8),
            "true_peak_L_dbfs": np.float32(-1.20),
            "true_peak_R_dbfs": np.float32(-1.05),
        },
        "vinyl": None,
        "click_count": np.int64(0),
        "clip_times_sec": [],
    }


def _make_result(path):
    """A full assembled dict for the MISS path's analyze_raw stand-in."""
    p = Path(path)
    return {
        "filename": p.name,
        "file_path": str(p.resolve()),
        "format": {},
        "authenticity": {},
        "playability": {},
        "vinyl": None,
        "click_count": 0,
        "clip_times_sec": [],
        "flags": [],
        "verdict": "CLUB READY",
        "verdict_reasons": [],
        "info_reasons": [],
        "spectrogram_path": None,
    }


# --------------------------------------------------------------------------- #
# Cache fixtures — mirror tests/test_cache.py exactly.
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "Application Support" / "BeatOrDelete" / "cache.db"


@pytest.fixture
def cache(monkeypatch, db_path):
    import core.cache as cache_mod
    cache_mod = importlib.reload(cache_mod)
    monkeypatch.setattr(cache_mod, "_db_path", lambda: db_path)
    return cache_mod


@pytest.fixture
def audio_file(tmp_path):
    f = tmp_path / "track.flac"
    f.write_bytes(b"\x00" * 4096)
    return f


def _rows(db_path, table):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


@pytest.fixture
def wav_file(tmp_path):
    """A real 2s 440Hz sine WAV — genuine numpy float32 through the real pipeline."""
    import soundfile as sf
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    p = tmp_path / "tone.wav"
    sf.write(str(p), sig, sr)
    return p


# --------------------------------------------------------------------------- #
# 1. analyze_raw derives authenticity.spectral_verdict from coverage_ratio,
#    NOT from a spectral_verdict key (which no longer exists in the raw).
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("coverage,expected", [
    (0.80, "FAKE_LOSSLESS"),
    (0.88, "SUSPECT"),
    (0.95, "GENUINE"),
])
def test_analyze_raw_derives_spectral_verdict(monkeypatch, wav_file, coverage, expected):
    raw = _make_raw_no_sv(str(wav_file), coverage=coverage)

    # Sanity: input spectral has NO spectral_verdict key — assembly must NOT need it.
    assert "spectral_verdict" not in raw["spectral"]

    monkeypatch.setattr(core.analyzer, "get_metadata", lambda p: raw["meta"])
    monkeypatch.setattr(core.analyzer, "check_spectral", lambda p: raw["spectral"])
    monkeypatch.setattr(core.analyzer, "check_integrity", lambda d, sr, p: raw["integrity"])
    monkeypatch.setattr(core.analyzer, "check_loudness", lambda d, sr: raw["loudness"])
    monkeypatch.setattr(core.analyzer, "count_clicks", lambda d, sr: raw["click_count"])
    monkeypatch.setattr(core.analyzer, "check_vinyl", lambda d, sr, nf, cc: None)
    monkeypatch.setattr(core.analyzer, "compute_verdict",
                        lambda *a, **k: {"verdict": "CLUB READY", "flags": [],
                                         "reasons": [], "info_reasons": []})

    out_raw, assembled = core.analyzer.analyze_raw(str(wav_file))

    # The raw the cache will persist still carries no spectral_verdict...
    assert "spectral_verdict" not in out_raw["spectral"]
    # ...yet the assembled public dict has it, derived at verdict-time.
    label = assembled["authenticity"]["spectral_verdict"]
    assert label == expected
    assert label == classify_coverage(raw["spectral"]["coverage_ratio"],
                                       runtime_config.active())


# --------------------------------------------------------------------------- #
# 2. INTEGRATION: the REAL pipeline (librosa-backed check_spectral, which emits
#    no spectral_verdict) through analyze() on a real audio file. Catches the
#    KeyError that hand fixtures with the legacy key would hide.
# --------------------------------------------------------------------------- #

def test_analyze_real_pipeline_no_keyerror(wav_file):
    result = core.analyzer.analyze(str(wav_file))
    assert "error" not in result
    auth = result["authenticity"]
    assert auth["spectral_verdict"] == classify_coverage(
        auth["spectral_coverage_ratio"], runtime_config.active()
    )
    assert auth["spectral_verdict"] in ("FAKE_LOSSLESS", "SUSPECT", "GENUINE")


# --------------------------------------------------------------------------- #
# 3. cache._assemble derives the label on a MISS — get_or_analyze on a raw blob
#    whose spectral sub-dict has coverage_ratio but NO spectral_verdict.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("coverage,expected", [
    (0.80, "FAKE_LOSSLESS"),
    (0.88, "SUSPECT"),
    (0.95, "GENUINE"),
])
def test_cache_assemble_derives_spectral_verdict(
    cache, monkeypatch, audio_file, coverage, expected
):
    raw = _make_raw_no_sv(str(audio_file), coverage=coverage)

    def _fake_raw(path):
        return raw, _make_result(path)

    monkeypatch.setattr(core.analyzer, "analyze_raw", _fake_raw)

    result = cache.get_or_analyze(str(audio_file))

    label = result["authenticity"]["spectral_verdict"]
    assert label == expected
    assert label == classify_coverage(np.float64(coverage), runtime_config.active())


# --------------------------------------------------------------------------- #
# 4. AC-4 (CORE CACHE INVARIANT): a verdict-time threshold change → a NEW
#    verdicts row (distinct config_hash), the SAME single measurements row,
#    and NO re-analysis (no FFT). cache.py reads core.config_hash.CONFIG_HASH
#    at call time (get_or_analyze line ~134), so monkeypatching the attribute
#    before the 2nd call faithfully simulates a re-spawned process that imported
#    a different CONFIG_HASH after thresholds.json changed.
# --------------------------------------------------------------------------- #

def test_ac4_override_new_verdict_row_shared_measurement_no_reanalysis(
    cache, monkeypatch, audio_file, db_path
):
    raw = _make_raw_no_sv(str(audio_file), coverage=0.989, dynamic_range=5.0)
    analyze_calls = []

    def _counting_raw(path):
        analyze_calls.append(path)
        # Faithful stand-in: real verdict over the raw at the ACTIVE config,
        # only librosa/soundfile skipped.
        v = core.verdict.compute_verdict(
            raw["meta"], raw["spectral"], raw["integrity"], raw["loudness"], raw["vinyl"]
        )
        assembled = {
            **_make_result(path),
            "verdict": v["verdict"], "flags": v["flags"],
            "verdict_reasons": v["reasons"], "info_reasons": v["info_reasons"],
        }
        return raw, assembled

    monkeypatch.setattr(core.analyzer, "analyze_raw", _counting_raw)
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", "baseline" * 8)

    cache.get_or_analyze(str(audio_file))          # MISS → analyze once
    assert len(analyze_calls) == 1
    assert len(_rows(db_path, "measurements")) == 1
    assert len(_rows(db_path, "verdicts")) == 1

    # Simulate a verdict-time threshold change + a fresh process' CONFIG_HASH.
    runtime_config.set_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 6.0})
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", "changed!!" * 8)

    cache.get_or_analyze(str(audio_file))          # measurement HIT, verdict MISS

    assert len(analyze_calls) == 1, "must NOT re-analyze (no re-FFT) on a verdict-only change"
    measurements = _rows(db_path, "measurements")
    verdicts = _rows(db_path, "verdicts")
    assert len(measurements) == 1, "measurement row is SHARED across config hashes"
    assert len(verdicts) == 2, "a new verdict row per distinct config_hash"
    assert len({v["config_hash"] for v in verdicts}) == 2
    assert {v["config_hash"] for v in verdicts} == {"baseline" * 8, "changed!!" * 8}


# --------------------------------------------------------------------------- #
# 5. reverdict_from_raw on a raw blob that LACKS spectral_verdict succeeds —
#    proves the reverdict path (compute_verdict → compute_flags → classify_coverage
#    on coverage_ratio) has no dependency on the dropped key. reverdict.py needs
#    no change (T-4 contract).
# --------------------------------------------------------------------------- #

def test_reverdict_from_raw_without_spectral_verdict(audio_file):
    raw = _make_raw_no_sv(str(audio_file), coverage=0.80)
    assert "spectral_verdict" not in raw["spectral"]

    verdict = core.reverdict.reverdict_from_raw(raw)  # must NOT raise KeyError

    assert set(verdict) >= {"verdict", "flags", "reasons", "info_reasons"}
    # coverage 0.80 in a lossless container → FAKE_LOSSLESS → DO NOT PLAY.
    assert "FAKE_LOSSLESS" in verdict["flags"]
    assert verdict["verdict"] == "DO NOT PLAY"


# --------------------------------------------------------------------------- #
# 6. AC-9: a REAL thresholds.json override flows through get_or_analyze and
#    flips the verdict vs the no-file baseline — exercised on the reverdict path
#    (measurement shared, verdict recomputed under the new config_hash) which is
#    exactly what CLI/batch hit after a Save. Uses a real file (no set_overrides)
#    so the override transport is genuinely tested; analyze_raw is stubbed so no
#    librosa is required.
# --------------------------------------------------------------------------- #

def test_ac9_real_thresholds_file_flips_verdict(
    cache, monkeypatch, tmp_path, audio_file
):
    # dynamic_range_db = 5.0: default DR_BLOCKING=4.0 → LOW_DYNAMIC_RANGE (REVIEW);
    # override DR_BLOCKING=6.0 → OVER_COMPRESSED (DO NOT PLAY).
    raw = _make_raw_no_sv(str(audio_file), coverage=0.989, dynamic_range=5.0)
    analyze_calls = []

    def _counting_raw(path):
        analyze_calls.append(path)
        v = core.verdict.compute_verdict(
            raw["meta"], raw["spectral"], raw["integrity"], raw["loudness"], raw["vinyl"]
        )
        assembled = {
            **_make_result(path),
            "verdict": v["verdict"], "flags": v["flags"],
            "verdict_reasons": v["reasons"], "info_reasons": v["info_reasons"],
        }
        return raw, assembled

    monkeypatch.setattr(core.analyzer, "analyze_raw", _counting_raw)

    # Point the override layer at a temp file (none yet) for both runtime_config
    # and config_hash (config_hash calls runtime_config.load_overrides).
    overrides_path = tmp_path / "thresholds.json"
    monkeypatch.setattr(runtime_config, "_overrides_path", lambda: overrides_path)

    # Baseline: no file → default config.
    runtime_config.reset()
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH",
                        core.config_hash.compute_config_hash())
    baseline = cache.get_or_analyze(str(audio_file))
    assert baseline["verdict"] == "REVIEW"

    # Save a real thresholds.json with a verdict-flipping override.
    overrides_path.write_text('{"DYNAMIC_RANGE_BLOCKING_DB": 6.0}')
    runtime_config.reset()  # next active() re-reads the file
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH",
                        core.config_hash.compute_config_hash())
    assert core.config_hash.CONFIG_HASH != "", "config hash recomputed with the file"

    overridden = cache.get_or_analyze(str(audio_file))

    assert overridden["verdict"] == "DO NOT PLAY"
    assert overridden["verdict"] != baseline["verdict"]
    assert "OVER_COMPRESSED" in overridden["flags"]
    assert len(analyze_calls) == 1, "override honored via reverdict — no re-analysis"
