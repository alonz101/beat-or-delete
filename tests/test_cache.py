"""RED tests for T-3: core/cache.py (does not exist yet).

Public contract:
    get_or_analyze(path: str, with_spectrogram: bool = False) -> dict
    invalidate(path: str) -> None

Design contract the implementation MUST honour so these tests can drive it:
  * DB path is resolved through a monkeypatchable hook ``core.cache._db_path()``
    returning a ``pathlib.Path``. Tests point it at a tmp file.
  * cache.py references its collaborators *through their modules* (so they are
    monkeypatchable):
        core.analyzer.analyze
        core.reverdict.reverdict_from_raw
        core.spectrogram.generate_spectrogram
        core.config_hash.CONFIG_HASH  (read at call time)
  * Per-call sqlite3 connection, WAL, foreign_keys ON, UNIQUE(abs_path,mtime_ns,size).
  * raw_json blob stores {meta, spectral, integrity, loudness, vinyl,
    click_count, clip_times_sec} and NEVER spectrogram_path.

All tests are expected to FAIL right now with ModuleNotFoundError because
``core/cache.py`` has not been written.
"""

import ast
import importlib
import os
import sqlite3
import threading
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# Fake analyze() result — mirrors core/analyzer.py lines 38-81 exactly.
# --------------------------------------------------------------------------- #

_FORMAT = {
    "container": "flac",
    "codec": "flac",
    "sample_rate": 44100,
    "bit_depth": 16,
    "bitrate": 1_000_000,
    "duration": 312.5,
    "channels": 2,
}
_AUTHENTICITY = {
    "lame_header": False,
    "spectral_coverage_ratio": 0.989,
    "top_freq_hz": 21800.0,
    "nyquist_hz": 22050.0,
    "spectral_verdict": "GENUINE",
    "suspected_origin": "likely genuine lossless",
    "rolloff_shape": "gradual",
    "lsb_zero_ratio": 0.10,
}
_PLAYABILITY = {
    "clip_events_L": 0,
    "clip_events_R": 0,
    "clip_max_ms": 0.0,
    "peak_dbfs": -1.10,
    "loudness_lufs": -9.8,
    "true_peak_L_dbfs": -1.20,
    "true_peak_R_dbfs": -1.05,
    "dynamic_range_db": 11.5,
    "noise_floor_dbfs": -72.0,
    "dc_offset_L": 0.0001,
    "dc_offset_R": 0.0001,
}


def _make_result(path):
    """A full, valid assembled analyze() dict for a clean FLAC → CLUB READY."""
    p = Path(path)
    return {
        "filename": p.name,
        "file_path": str(p.resolve()),
        "format": dict(_FORMAT),
        "authenticity": dict(_AUTHENTICITY),
        "playability": dict(_PLAYABILITY),
        "vinyl": None,
        "click_count": 0,
        "clip_times_sec": [],
        "flags": [],
        "verdict": "CLUB READY",
        "verdict_reasons": [],
        "info_reasons": [],
        "spectrogram_path": None,
    }


def _make_raw(path):
    """The raw_components half of analyze_raw()'s (raw, assembled) return.

    Mirrors core.analyzer.analyze_raw: each sub-dict is a check module's raw
    output (meta/spectral/integrity/loudness), plus vinyl/click_count/clip_times.
    Values are consistent with _make_result so _assemble(raw) round-trips to it.
    """
    return {
        "meta": {
            "container": _FORMAT["container"],
            "codec": _FORMAT["codec"],
            "sample_rate": _FORMAT["sample_rate"],
            "bit_depth": _FORMAT["bit_depth"],
            "bitrate": _FORMAT["bitrate"],
            "duration": _FORMAT["duration"],
            "channels": _FORMAT["channels"],
            "lame_header": _AUTHENTICITY["lame_header"],
        },
        "spectral": {
            # Real post-T-3 raw blobs no longer carry spectral_verdict — _assemble
            # DERIVES authenticity.spectral_verdict from coverage_ratio via
            # flags.classify_coverage (0.989 → "GENUINE").
            "coverage_ratio": _AUTHENTICITY["spectral_coverage_ratio"],
            "top_freq_hz": _AUTHENTICITY["top_freq_hz"],
            "nyquist_hz": _AUTHENTICITY["nyquist_hz"],
            "suspected_origin": _AUTHENTICITY["suspected_origin"],
            "rolloff_shape": _AUTHENTICITY["rolloff_shape"],
        },
        "integrity": {
            "clip_events_L": _PLAYABILITY["clip_events_L"],
            "clip_events_R": _PLAYABILITY["clip_events_R"],
            "clip_max_ms": _PLAYABILITY["clip_max_ms"],
            "peak_dbfs": _PLAYABILITY["peak_dbfs"],
            "dynamic_range_db": _PLAYABILITY["dynamic_range_db"],
            "noise_floor_dbfs": _PLAYABILITY["noise_floor_dbfs"],
            "dc_offset_L": _PLAYABILITY["dc_offset_L"],
            "dc_offset_R": _PLAYABILITY["dc_offset_R"],
            "lsb_zero_ratio": _AUTHENTICITY["lsb_zero_ratio"],
            "clip_times_sec": [],
        },
        "loudness": {
            "loudness_lufs": _PLAYABILITY["loudness_lufs"],
            "true_peak_L_dbfs": _PLAYABILITY["true_peak_L_dbfs"],
            "true_peak_R_dbfs": _PLAYABILITY["true_peak_R_dbfs"],
        },
        "vinyl": None,
        "click_count": 0,
        "clip_times_sec": [],
    }


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_path(tmp_path):
    # Deliberately includes non-existent parent dirs to exercise auto-create.
    return tmp_path / "Application Support" / "BeatOrDelete" / "cache.db"


@pytest.fixture
def cache(monkeypatch, db_path):
    """Import core.cache and redirect its DB path at the tmp location."""
    import core.cache as cache_mod
    cache_mod = importlib.reload(cache_mod)
    monkeypatch.setattr(cache_mod, "_db_path", lambda: db_path)
    return cache_mod


@pytest.fixture
def audio_file(tmp_path):
    f = tmp_path / "track.flac"
    f.write_bytes(b"\x00" * 4096)
    return f


@pytest.fixture
def analyze_calls(monkeypatch):
    """Patch core.analyzer.analyze_raw with a recording fake (the collaborator the
    cache calls on a miss). Returns call list."""
    import core.analyzer
    calls = []

    def _fake_raw(path):
        calls.append({"path": path})
        return _make_raw(path), _make_result(path)

    monkeypatch.setattr(core.analyzer, "analyze_raw", _fake_raw)
    return calls


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _rows(db_path, table):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


def _table_names(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Public API surface
# --------------------------------------------------------------------------- #

def test_public_api_exists(cache):
    assert callable(cache.get_or_analyze)
    assert callable(cache.invalidate)


# --------------------------------------------------------------------------- #
# AC-5: DB auto-created at configured path on first run
# --------------------------------------------------------------------------- #

def test_ac5_db_autocreated_on_first_run(cache, analyze_calls, audio_file, db_path):
    assert not db_path.exists()
    cache.get_or_analyze(str(audio_file))
    assert db_path.exists()
    assert {"measurements", "verdicts"} <= _table_names(db_path)


# --------------------------------------------------------------------------- #
# AC-1: analyze() called once on repeated unchanged file; result is transparent
# --------------------------------------------------------------------------- #

def test_ac1_analyze_called_once_for_unchanged_file(cache, analyze_calls, audio_file):
    r1 = cache.get_or_analyze(str(audio_file))
    r2 = cache.get_or_analyze(str(audio_file))
    assert len(analyze_calls) == 1
    # Caching must be transparent: cached result identical to fresh result.
    assert r1 == r2


def test_ac1_one_measurement_row(cache, analyze_calls, audio_file, db_path):
    cache.get_or_analyze(str(audio_file))
    cache.get_or_analyze(str(audio_file))
    assert len(_rows(db_path, "measurements")) == 1


# --------------------------------------------------------------------------- #
# Regression: real check modules return numpy float32, which json.dumps cannot
# serialize without the numpy_to_native default. Earlier fakes used pure-Python
# floats and masked this — crashed on every real audio file.
# --------------------------------------------------------------------------- #

def test_numpy_values_are_cacheable(cache, monkeypatch, audio_file, db_path):
    import numpy as np
    import core.analyzer

    def _fake_numpy_raw(path):
        raw = _make_raw(path)
        # Inject numpy scalar types the real pipeline produces, into the raw blob
        # (that's what gets persisted + round-tripped through json/_assemble).
        raw["integrity"]["peak_dbfs"] = np.float32(-1.10)
        raw["spectral"]["top_freq_hz"] = np.float32(21800.0)
        raw["spectral"]["coverage_ratio"] = np.float64(0.989)
        raw["click_count"] = np.int64(0)
        raw["clip_times_sec"] = [np.float32(1.5), np.float32(2.5)]
        return raw, _make_result(path)

    monkeypatch.setattr(core.analyzer, "analyze_raw", _fake_numpy_raw)

    # MISS path must persist without TypeError, and HIT path must round-trip.
    r1 = cache.get_or_analyze(str(audio_file))
    r2 = cache.get_or_analyze(str(audio_file))
    assert len(_rows(db_path, "measurements")) == 1
    # Cached values come back as native floats (float32 precision tolerance).
    assert r2["playability"]["peak_dbfs"] == pytest.approx(-1.10, abs=1e-5)
    assert r2["clip_times_sec"] == pytest.approx([1.5, 2.5])


def test_cached_result_matches_analyze_shape(cache, analyze_calls, audio_file):
    expected = _make_result(str(audio_file))
    cache.get_or_analyze(str(audio_file))          # populate
    r = cache.get_or_analyze(str(audio_file))      # served from cache
    for key in ("format", "authenticity", "playability", "vinyl",
                "click_count", "clip_times_sec", "flags", "verdict",
                "verdict_reasons", "info_reasons", "filename", "file_path"):
        assert r[key] == expected[key], key
    assert r["spectrogram_path"] is None


# --------------------------------------------------------------------------- #
# AC-2: mtime / size change → cache miss → analyze() runs again
# --------------------------------------------------------------------------- #

def test_ac2_mtime_change_busts_cache(cache, analyze_calls, audio_file, db_path):
    cache.get_or_analyze(str(audio_file))
    st = audio_file.stat()
    os.utime(audio_file, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    cache.get_or_analyze(str(audio_file))
    assert len(analyze_calls) == 2
    assert len(_rows(db_path, "measurements")) == 2


def test_ac2_size_change_busts_cache(cache, analyze_calls, audio_file, db_path):
    cache.get_or_analyze(str(audio_file))
    audio_file.write_bytes(b"\x00" * 8192)   # different size
    cache.get_or_analyze(str(audio_file))
    assert len(analyze_calls) == 2
    assert len(_rows(db_path, "measurements")) == 2


# --------------------------------------------------------------------------- #
# AC-3: config_hash change → verdict recomputed from raw, analyze() NOT re-run
# --------------------------------------------------------------------------- #

def test_ac3_config_change_reverdicts_without_reanalyzing(
    cache, analyze_calls, audio_file, monkeypatch
):
    import core.config_hash
    import core.reverdict

    # Seed the cache (analyze runs once).
    cache.get_or_analyze(str(audio_file))
    assert len(analyze_calls) == 1

    # Spy on reverdict_from_raw and bust the config hash.
    reverdict_calls = []

    def _spy(raw):
        reverdict_calls.append(raw)
        return {
            "verdict": "REVIEW",
            "flags": ["FAKE_320"],
            "reasons": ["config changed"],
            "info_reasons": [],
        }

    monkeypatch.setattr(core.reverdict, "reverdict_from_raw", _spy)
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", "deadbeef" * 8)
    monkeypatch.setattr(core.config_hash, "compute_config_hash",
                        lambda: "deadbeef" * 8)

    r = cache.get_or_analyze(str(audio_file))

    assert len(analyze_calls) == 1            # NO re-analysis (no FFT)
    assert len(reverdict_calls) == 1          # recomputed from stored raw
    # raw passed to reverdict has the stored sub-dict shape.
    raw = reverdict_calls[0]
    assert {"meta", "spectral", "integrity", "loudness", "vinyl"} <= set(raw)
    # New verdict is reflected in the returned assembled result.
    assert r["verdict"] == "REVIEW"
    assert r["flags"] == ["FAKE_320"]
    assert r["verdict_reasons"] == ["config changed"]


def test_ac3_two_verdict_rows_after_config_change(
    cache, analyze_calls, audio_file, db_path, monkeypatch
):
    import core.config_hash
    import core.reverdict

    cache.get_or_analyze(str(audio_file))
    assert len(_rows(db_path, "verdicts")) == 1

    monkeypatch.setattr(core.reverdict, "reverdict_from_raw",
                        lambda raw: {"verdict": "REVIEW", "flags": [],
                                     "reasons": [], "info_reasons": []})
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", "f00dface" * 8)
    monkeypatch.setattr(core.config_hash, "compute_config_hash",
                        lambda: "f00dface" * 8)

    cache.get_or_analyze(str(audio_file))
    rows = _rows(db_path, "verdicts")
    assert len(rows) == 2
    assert len({row["config_hash"] for row in rows}) == 2
    # measurements untouched — only one analysis ever happened.
    assert len(_rows(db_path, "measurements")) == 1


# --------------------------------------------------------------------------- #
# AC-6: spectrogram never persisted; with_spectrogram=True always regenerates
# --------------------------------------------------------------------------- #

def test_ac6_spectrogram_path_never_stored(cache, analyze_calls, audio_file, db_path):
    cache.get_or_analyze(str(audio_file))
    for row in _rows(db_path, "measurements"):
        assert "spectrogram_path" not in row["raw_json"]
    for row in _rows(db_path, "verdicts"):
        assert "spectrogram_path" not in row["verdict_json"]


def test_ac6_with_spectrogram_regenerates_each_call(
    cache, analyze_calls, audio_file, db_path, monkeypatch
):
    import core.spectrogram
    spec_calls = []

    def _fake_spec(path):
        spec_calls.append(path)
        return "/tmp/generated_spectrogram.png"

    monkeypatch.setattr(core.spectrogram, "generate_spectrogram", _fake_spec)

    r1 = cache.get_or_analyze(str(audio_file), with_spectrogram=True)   # miss
    r2 = cache.get_or_analyze(str(audio_file), with_spectrogram=True)   # hit

    assert r1["spectrogram_path"] == "/tmp/generated_spectrogram.png"
    assert r2["spectrogram_path"] == "/tmp/generated_spectrogram.png"
    # FFT analysis only once, but spectrogram regenerated on every call.
    assert len(analyze_calls) == 1
    assert len(spec_calls) == 2
    # Still never persisted.
    for row in _rows(db_path, "measurements"):
        assert "spectrogram_path" not in row["raw_json"]
        assert "/tmp/generated_spectrogram.png" not in row["raw_json"]


# --------------------------------------------------------------------------- #
# AC-4: batch.py and analyzer.py share the same DB (single source of truth)
# --------------------------------------------------------------------------- #

def test_ac4_single_shared_db(cache, analyze_calls, audio_file, db_path):
    # get_or_analyze and invalidate must both resolve through _db_path().
    assert cache._db_path() == db_path
    cache.get_or_analyze(str(audio_file))
    # Any other importer (batch / analyzer) opening the same path sees the row.
    assert len(_rows(db_path, "measurements")) == 1
    # A second call (different "caller") is a hit on the shared DB.
    cache.get_or_analyze(str(audio_file))
    assert len(analyze_calls) == 1


# --------------------------------------------------------------------------- #
# AC-7: cache.py imports only stdlib + first-party core — no third-party
# --------------------------------------------------------------------------- #

def test_ac7_no_third_party_imports(cache):
    src = Path(cache.__file__).read_text()
    tree = ast.parse(src)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                roots.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    forbidden = {"soundfile", "librosa", "numpy", "np", "scipy",
                 "matplotlib", "pandas"}
    assert not (roots & forbidden), f"third-party import in cache.py: {roots & forbidden}"
    assert "sqlite3" in roots


# --------------------------------------------------------------------------- #
# Concurrency: N threads on a fresh file → no OperationalError, one row
# --------------------------------------------------------------------------- #

def test_concurrent_first_run_single_row(cache, audio_file, db_path, monkeypatch):
    import time as _time
    import core.analyzer
    calls = []

    def _slow(path):
        calls.append(path)
        _time.sleep(0.02)          # widen the race window
        return _make_raw(path), _make_result(path)

    monkeypatch.setattr(core.analyzer, "analyze_raw", _slow)

    errors = []
    barrier = threading.Barrier(8)

    def _worker():
        try:
            barrier.wait()
            cache.get_or_analyze(str(audio_file))
        except Exception as exc:   # incl. sqlite3.OperationalError
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"concurrency errors: {errors}"
    assert len(_rows(db_path, "measurements")) == 1


# --------------------------------------------------------------------------- #
# invalidate(): removes rows; next get_or_analyze is a miss
# --------------------------------------------------------------------------- #

def test_invalidate_removes_rows_and_forces_miss(
    cache, analyze_calls, audio_file, db_path
):
    cache.get_or_analyze(str(audio_file))
    assert len(_rows(db_path, "measurements")) == 1
    assert len(_rows(db_path, "verdicts")) == 1

    cache.invalidate(str(audio_file))

    assert _rows(db_path, "measurements") == []
    assert _rows(db_path, "verdicts") == []        # FK cascade

    cache.get_or_analyze(str(audio_file))          # miss again
    assert len(analyze_calls) == 2
    assert len(_rows(db_path, "measurements")) == 1
