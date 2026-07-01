"""RED tests for T-1: core/history.py (does not exist yet).

Public contract (from docs/specs/history-tab/PLAN.md, "T-1"):
    search_history(query: str = "", limit: int = 10) -> list[dict]

Behaviour driven here:
  * Reads `measurements` via core.cache._connect() (schema/WAL/FK on cold DB →
    empty cache returns [] with no error, DB auto-created).
  * Filters + ranks on the *basename* of abs_path, case-insensitive:
      - empty query      -> no filter, order by created DESC (most-recent first)
      - non-empty query  -> keep basenames CONTAINING the query (anywhere);
                            sort key (0 if startswith else 1, -created) so
                            prefix matches rank above mid-substring, ties broken
                            by newer created.
  * Caps at `limit`.
  * Collapses to the MOST-RECENT measurements row per abs_path (Q1 locked).
  * Resolves the verdict under the CURRENT core.config_hash.CONFIG_HASH,
    replicating get_or_analyze's verdict-miss branch: reverdict_from_raw on miss
    and INSERT a `verdicts` row ONLY — NEVER touches `measurements` (AC-5).
  * Returns core.cache._assemble(abs_path, raw, verdict) plus two extra keys:
      result["analyzed_at"] == that row's measurements.created
      result["file_exists"] == os.path.exists(abs_path)
  * Must not import librosa/matplotlib/soundfile/numpy/scipy (search stays light).

Every test is expected to FAIL right now with
``ModuleNotFoundError: No module named 'core.history'`` — that's correct RED.

Design contract these tests rely on (mirrors tests/test_cache.py):
  * DB path resolved via core.cache._db_path(); tests point it at a tmp file.
  * cache references collaborators through their modules so they're monkeypatchable:
        core.analyzer.analyze_raw
        core.reverdict.reverdict_from_raw
        core.config_hash.CONFIG_HASH  (read at call time)
  * raw blobs carry numpy scalar types (np.float32 / np.int64) exactly as the
    real pipeline produces — pure-Python primitives would mask a json.dumps bug
    on the reverdict-persist path (per [[tests-use-realistic-numpy-data]]).
"""

import ast
import inspect
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pytest


# --------------------------------------------------------------------------- #
# Realistic raw/result fixtures — numpy dtypes are LOAD-BEARING.
# Mirrors core/analyzer.analyze_raw shape (see tests/test_cache.py::_make_raw).
# --------------------------------------------------------------------------- #

_FORMAT = {
    "container": "flac", "codec": "flac", "sample_rate": 44100,
    "bit_depth": 16, "bitrate": 1_000_000, "duration": 312.5, "channels": 2,
}
_AUTHENTICITY = {
    "lame_header": False, "spectral_coverage_ratio": 0.989, "top_freq_hz": 21800.0,
    "nyquist_hz": 22050.0, "spectral_verdict": "GENUINE",
    "suspected_origin": "likely genuine lossless", "rolloff_shape": "gradual",
    "lsb_zero_ratio": 0.10,
}
_PLAYABILITY = {
    "clip_events_L": 0, "clip_events_R": 0, "clip_max_ms": 0.0, "peak_dbfs": -1.10,
    "loudness_lufs": -9.8, "true_peak_L_dbfs": -1.20, "true_peak_R_dbfs": -1.05,
    "dynamic_range_db": 11.5, "noise_floor_dbfs": -72.0,
    "dc_offset_L": 0.0001, "dc_offset_R": 0.0001,
}


def _make_raw(path):
    """raw_components half of analyze_raw()'s (raw, assembled) return, with the
    numpy scalar types the real pipeline emits injected into the blob."""
    return {
        "meta": {
            "container": _FORMAT["container"], "codec": _FORMAT["codec"],
            "sample_rate": _FORMAT["sample_rate"], "bit_depth": _FORMAT["bit_depth"],
            "bitrate": _FORMAT["bitrate"], "duration": _FORMAT["duration"],
            "channels": _FORMAT["channels"], "lame_header": _AUTHENTICITY["lame_header"],
        },
        "spectral": {
            "coverage_ratio": np.float64(_AUTHENTICITY["spectral_coverage_ratio"]),
            "top_freq_hz": np.float32(_AUTHENTICITY["top_freq_hz"]),
            "nyquist_hz": _AUTHENTICITY["nyquist_hz"],
            "suspected_origin": _AUTHENTICITY["suspected_origin"],
            "rolloff_shape": _AUTHENTICITY["rolloff_shape"],
        },
        "integrity": {
            "clip_events_L": np.int64(_PLAYABILITY["clip_events_L"]),
            "clip_events_R": np.int64(_PLAYABILITY["clip_events_R"]),
            "clip_max_ms": _PLAYABILITY["clip_max_ms"],
            "peak_dbfs": np.float32(_PLAYABILITY["peak_dbfs"]),
            "dynamic_range_db": np.float32(_PLAYABILITY["dynamic_range_db"]),
            "noise_floor_dbfs": np.float32(_PLAYABILITY["noise_floor_dbfs"]),
            "dc_offset_L": _PLAYABILITY["dc_offset_L"],
            "dc_offset_R": _PLAYABILITY["dc_offset_R"],
            "lsb_zero_ratio": _AUTHENTICITY["lsb_zero_ratio"],
            "clip_times_sec": [],
        },
        "loudness": {
            "loudness_lufs": np.float32(_PLAYABILITY["loudness_lufs"]),
            "true_peak_L_dbfs": np.float32(_PLAYABILITY["true_peak_L_dbfs"]),
            "true_peak_R_dbfs": np.float32(_PLAYABILITY["true_peak_R_dbfs"]),
        },
        "vinyl": None,
        "click_count": np.int64(0),
        "clip_times_sec": [],
    }


def _make_result(path):
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


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_path(tmp_path):
    # Non-existent parent dirs on purpose → exercises auto-create in _connect().
    return tmp_path / "Application Support" / "BeatOrDelete" / "cache.db"


@pytest.fixture
def cache(monkeypatch, db_path):
    """core.cache with its DB path redirected at the tmp location. history.py
    reuses core.cache internals, so this redirects history's DB too."""
    import core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "_db_path", lambda: db_path)
    return cache_mod


@pytest.fixture
def history(cache):
    """The module under test. Import fails RED until core/history.py exists."""
    import core.history as history_mod
    return history_mod


@pytest.fixture
def analyze_calls(monkeypatch):
    """Recording fake for core.analyzer.analyze_raw — the collaborator the cache
    calls on a MISS. Returns the call list so tests can assert it stays frozen
    (the history path must NEVER re-analyze)."""
    import core.analyzer
    calls = []

    def _fake_raw(path):
        calls.append(path)
        return _make_raw(path), _make_result(path)

    monkeypatch.setattr(core.analyzer, "analyze_raw", _fake_raw)
    return calls


@pytest.fixture
def audio_dir(tmp_path):
    d = tmp_path / "audio"
    d.mkdir()
    return d


@pytest.fixture
def seed(cache, analyze_calls, audio_dir, db_path):
    """Seed one cached track through the real cache MISS path.

    Returns the resolved abs_path. `created` overrides measurements.created for
    deterministic ordering; `exists=False` deletes the file after seeding so the
    row survives but os.path.exists() is False.
    """
    def _seed(name, created=None, exists=True):
        f = audio_dir / name
        f.write_bytes(b"\x00" * 4096)
        cache.get_or_analyze(str(f))
        abs_path = str(f.resolve())
        if created is not None:
            _set_created(db_path, abs_path, created)
        if not exists:
            f.unlink()
        return abs_path
    return _seed


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


def _set_created(db_path, abs_path, created):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE measurements SET created=? WHERE abs_path=?",
                     (created, abs_path))
        conn.commit()
    finally:
        conn.close()


def _measurement(db_path, abs_path):
    """Return (raw_dict, verdict_dict, created) for the newest row of abs_path."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        m = conn.execute(
            "SELECT * FROM measurements WHERE abs_path=? ORDER BY created DESC LIMIT 1",
            (abs_path,),
        ).fetchone()
        v = conn.execute(
            "SELECT * FROM verdicts WHERE measurement_id=? ORDER BY created DESC LIMIT 1",
            (m["id"],),
        ).fetchone()
        return json.loads(m["raw_json"]), json.loads(v["verdict_json"]), m["created"]
    finally:
        conn.close()


def _names(results):
    return [r["filename"] for r in results]


# --------------------------------------------------------------------------- #
# 1. Signature / callable
# --------------------------------------------------------------------------- #

def test_signature_callable_returns_list(history):
    assert callable(history.search_history)
    sig = inspect.signature(history.search_history)
    params = sig.parameters
    assert params["query"].default == ""
    assert params["limit"].default == 10
    out = history.search_history(query="", limit=10)
    assert isinstance(out, list)


# --------------------------------------------------------------------------- #
# 2. Empty cache → [] (DB auto-created, no error) — AC-9 / AC-10
# --------------------------------------------------------------------------- #

def test_empty_cache_returns_empty_list(history, db_path):
    assert not db_path.exists()
    out = history.search_history()
    assert out == []
    # _connect() must have auto-created the DB on a cold path.
    assert db_path.exists()


# --------------------------------------------------------------------------- #
# 3. Empty query → up to `limit` rows, ordered by created DESC — AC-3
# --------------------------------------------------------------------------- #

def test_empty_query_orders_by_created_desc(history, seed):
    seed("alpha.flac", created=100.0)
    seed("bravo.wav", created=300.0)
    seed("charlie.aiff", created=200.0)

    out = history.search_history(query="")
    assert _names(out) == ["bravo.wav", "charlie.aiff", "alpha.flac"]


# --------------------------------------------------------------------------- #
# 4. Substring match anywhere (not just prefix) — AC-2
# --------------------------------------------------------------------------- #

def test_substring_matches_anywhere(history, seed):
    seed("deep_kick.flac", created=100.0)
    seed("kick_drum.wav", created=200.0)
    seed("bassline.aiff", created=300.0)

    out = history.search_history(query="kick")
    assert set(_names(out)) == {"deep_kick.flac", "kick_drum.wav"}
    assert "bassline.aiff" not in _names(out)


def test_substring_is_case_insensitive(history, seed):
    seed("Deep_KICK.flac", created=100.0)
    out = history.search_history(query="kick")
    assert _names(out) == ["Deep_KICK.flac"]


# --------------------------------------------------------------------------- #
# 5. Ranking: prefix beats mid-substring; tie-break newer created first
# --------------------------------------------------------------------------- #

def test_ranking_prefix_beats_mid_then_newer_first(history, seed):
    # Two prefix matches (kick_*) + one mid match (deep_kick).
    seed("kick_drum.wav", created=100.0)   # prefix, older
    seed("kick_bass.wav", created=200.0)   # prefix, newer
    seed("deep_kick.flac", created=300.0)  # mid, newest overall

    out = history.search_history(query="kick")
    # prefix group first (newer-first inside), mid group last.
    assert _names(out) == ["kick_bass.wav", "kick_drum.wav", "deep_kick.flac"]


# --------------------------------------------------------------------------- #
# 6. limit caps result count — AC-2
# --------------------------------------------------------------------------- #

def test_limit_caps_count(history, seed):
    for i in range(15):
        seed(f"track_{i:02d}.flac", created=float(i))
    out = history.search_history(query="", limit=10)
    assert len(out) == 10


# --------------------------------------------------------------------------- #
# 7. Attached fields: analyzed_at (== created) and file_exists (True/False);
#    a missing-file row STILL appears — AC-8
# --------------------------------------------------------------------------- #

def test_attaches_analyzed_at_and_file_exists(history, seed):
    present = seed("present.flac", created=111.0, exists=True)
    missing = seed("missing.flac", created=222.0, exists=False)

    out = history.search_history(query="")
    by_path = {r["file_path"]: r for r in out}

    # Both rows appear (missing file is not dropped).
    assert present in by_path and missing in by_path

    assert by_path[present]["analyzed_at"] == 111.0
    assert by_path[present]["file_exists"] is True

    assert by_path[missing]["analyzed_at"] == 222.0
    assert by_path[missing]["file_exists"] is False


# --------------------------------------------------------------------------- #
# 8. Reverdict-on-miss under current CONFIG_HASH — AC-5
#    New config hash -> reverdict_from_raw runs, a NEW verdicts row is written,
#    measurements row count UNCHANGED, analyze_raw NOT called again.
#    Second call at same hash -> verdict HIT, reverdict NOT called again.
# --------------------------------------------------------------------------- #

def test_reverdict_on_miss_writes_verdict_only_no_reanalysis(
    history, seed, cache, db_path, analyze_calls, monkeypatch
):
    import core.config_hash
    import core.reverdict

    abs_path = seed("reverdict_me.flac", created=100.0)

    analyze_count_after_seed = len(analyze_calls)          # frozen baseline
    measurements_before = len(_rows(db_path, "measurements"))
    verdicts_before = len(_rows(db_path, "verdicts"))

    # Spy on reverdict + bust the config hash so the verdict layer MISSES.
    reverdict_calls = []

    def _spy(raw):
        reverdict_calls.append(raw)
        return {"verdict": "REVIEW", "flags": ["FAKE_320"],
                "reasons": ["config changed"], "info_reasons": []}

    NEW_HASH = "deadbeef" * 8
    monkeypatch.setattr(core.reverdict, "reverdict_from_raw", _spy)
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", NEW_HASH)

    out = history.search_history(query="reverdict")
    assert len(out) == 1
    # New verdict reflected in the assembled result.
    assert out[0]["verdict"] == "REVIEW"
    assert out[0]["flags"] == ["FAKE_320"]

    # Reverdict genuinely ran on the cached raw (not a re-analysis).
    assert len(reverdict_calls) == 1
    raw = reverdict_calls[0]
    assert {"meta", "spectral", "integrity", "loudness", "vinyl"} <= set(raw)

    # measurements untouched; analyze_raw frozen; a NEW verdict row for NEW_HASH.
    assert len(analyze_calls) == analyze_count_after_seed
    assert len(_rows(db_path, "measurements")) == measurements_before
    vrows = _rows(db_path, "verdicts")
    assert len(vrows) == verdicts_before + 1
    assert NEW_HASH in {r["config_hash"] for r in vrows}

    # Second call at the SAME hash → verdict HIT, reverdict NOT called again.
    out2 = history.search_history(query="reverdict")
    assert len(reverdict_calls) == 1                       # no second reverdict
    assert out2[0]["verdict"] == "REVIEW"
    assert len(_rows(db_path, "verdicts")) == verdicts_before + 1


# --------------------------------------------------------------------------- #
# 9. Assembled shape == core.cache._assemble(abs_path, raw, verdict) + 2 keys
# --------------------------------------------------------------------------- #

def test_result_equals_assemble_plus_extra_keys(history, cache, seed, db_path):
    abs_path = seed("shape.flac", created=555.0)

    raw, verdict, created = _measurement(db_path, abs_path)
    expected = cache._assemble(abs_path, raw, verdict)

    out = history.search_history(query="shape")
    assert len(out) == 1
    result = out[0]

    # Extra keys present with the right values.
    assert result["analyzed_at"] == 555.0
    assert result["file_exists"] is True

    # Stripping the two extra keys yields exactly _assemble()'s dict.
    core_result = {k: v for k, v in result.items()
                   if k not in ("analyzed_at", "file_exists")}
    assert core_result == expected

    # Spot-checks called out in the plan.
    assert result["verdict"] == expected["verdict"]
    assert result["authenticity"] == expected["authenticity"]
    assert result["flags"] == expected["flags"]


# --------------------------------------------------------------------------- #
# Q1 (locked): collapse to the MOST-RECENT measurements row per abs_path.
# Two rows for the same path (re-analyzed → distinct mtime/size) → only newest.
# --------------------------------------------------------------------------- #

def test_collapses_to_newest_row_per_path(history, cache, audio_dir, db_path,
                                           analyze_calls):
    f = audio_dir / "dup.flac"
    f.write_bytes(b"\x00" * 4096)
    cache.get_or_analyze(str(f))                 # row 1

    # Change mtime → second distinct measurements row for the SAME abs_path.
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    cache.get_or_analyze(str(f))                 # row 2

    abs_path = str(f.resolve())
    rows = [r for r in _rows(db_path, "measurements") if r["abs_path"] == abs_path]
    assert len(rows) == 2                         # two versions really exist
    older = min(rows, key=lambda r: r["id"])
    newer = max(rows, key=lambda r: r["id"])
    # Force deterministic ordering by id → set created explicitly.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE measurements SET created=? WHERE id=?", (100.0, older["id"]))
        conn.execute("UPDATE measurements SET created=? WHERE id=?", (200.0, newer["id"]))
        conn.commit()
    finally:
        conn.close()

    out = history.search_history(query="dup")
    matches = [r for r in out if r["file_path"] == abs_path]
    assert len(matches) == 1                       # collapsed to one entry
    assert matches[0]["analyzed_at"] == 200.0      # the newest version


# --------------------------------------------------------------------------- #
# 10. No heavy imports: AST-scan core/history.py — forbidden roots absent.
#     Mirrors tests/test_cache.py::test_ac7_no_third_party_imports.
# --------------------------------------------------------------------------- #

def test_no_heavy_imports():
    import core.history
    src = Path(core.history.__file__).read_text()
    tree = ast.parse(src)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                roots.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    forbidden = {"soundfile", "librosa", "numpy", "np", "scipy", "matplotlib", "pandas"}
    assert not (roots & forbidden), \
        f"heavy import in history.py: {roots & forbidden}"


# --------------------------------------------------------------------------- #
# Integration: run REAL analysis (real numpy blobs) through the cache, then
# search_history. Catches type mismatches a hand fixture would hide — in
# particular the reverdict-persist json.dumps(default=numpy_to_native) path on
# genuine np.float32/np.int64 raw values (per [[tests-use-realistic-numpy-data]]
# and the integration-test requirement). No test-files/ audio exists in the
# worktree, so we synthesize a real WAV like tests/test_lazy_import.py.
# --------------------------------------------------------------------------- #

def test_integration_real_pipeline_reverdict_survives_numpy(
    history, cache, tmp_path, db_path, monkeypatch
):
    sf = pytest.importorskip("soundfile")
    import core.config_hash

    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    wav = tmp_path / "real_tone_kick.wav"
    sf.write(str(wav), sig, sr)

    # Real MISS → real analyze_raw → real numpy raw blob persisted.
    cache.get_or_analyze(str(wav))
    abs_path = str(wav.resolve())
    assert len(_rows(db_path, "measurements")) == 1

    # Force a config change so search_history hits the reverdict-on-miss branch
    # with REAL numpy raw values; json.dumps must not raise (numpy_to_native).
    monkeypatch.setattr(core.config_hash, "CONFIG_HASH", "REAL_REVERDICT_HASH")

    out = history.search_history(query="tone")
    assert len(out) == 1
    r = out[0]
    assert r["file_path"] == abs_path
    assert r["file_exists"] is True
    assert isinstance(r["analyzed_at"], float)
    assert r["verdict"] in {"CLUB READY", "REVIEW", "DO NOT PLAY"}
    # Full assembled shape present.
    assert {"format", "authenticity", "playability", "flags"} <= set(r)
    # Reverdict wrote a verdicts row for the new hash; measurements untouched.
    assert len(_rows(db_path, "measurements")) == 1
    assert "REAL_REVERDICT_HASH" in {v["config_hash"] for v in _rows(db_path, "verdicts")}
