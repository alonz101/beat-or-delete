"""SQLite-backed analysis cache (T-3).

Public API:
    get_or_analyze(path, with_spectrogram=False) -> dict
    invalidate(path) -> None

Collaborators are referenced through their modules so tests can monkeypatch:
    core.analyzer.analyze
    core.reverdict.reverdict_from_raw
    core.spectrogram.generate_spectrogram
    core.config_hash.CONFIG_HASH (read at call time)
"""

import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import core.analyzer
import core.config_hash
import core.reverdict
from core.utils import numpy_to_native

_SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
  id        INTEGER PRIMARY KEY,
  abs_path  TEXT    NOT NULL,
  mtime_ns  INTEGER NOT NULL,
  size      INTEGER NOT NULL,
  raw_json  TEXT    NOT NULL,
  created   REAL    NOT NULL,
  UNIQUE(abs_path, mtime_ns, size)
);
CREATE TABLE IF NOT EXISTS verdicts (
  measurement_id INTEGER NOT NULL,
  config_hash    TEXT    NOT NULL,
  verdict_json   TEXT    NOT NULL,
  created        REAL    NOT NULL,
  PRIMARY KEY (measurement_id, config_hash),
  FOREIGN KEY (measurement_id) REFERENCES measurements(id) ON DELETE CASCADE
);
"""

_RAW_KEYS = ("meta", "spectral", "integrity", "loudness", "vinyl",
             "click_count", "clip_times_sec")
_VERDICT_KEYS = ("verdict", "flags", "reasons", "info_reasons")


def _db_path() -> Path:
    """DB location. Monkeypatched by tests; real default below."""
    return Path.home() / "Library" / "Application Support" / "BeatOrDelete" / "cache.db"


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    # busy_timeout must be first — WAL switch can itself hit SQLITE_BUSY on cold start
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    for attempt in range(3):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            break
        except sqlite3.OperationalError:
            if attempt == 2:
                raise
            time.sleep(0.05)
    return conn


def _assemble(path: str, raw: dict, verdict: dict) -> dict:
    """Reconstruct the analyze() result shape from raw + verdict blobs."""
    p = Path(path)
    meta = raw["meta"]
    spectral = raw["spectral"]
    integrity = raw["integrity"]
    loudness = raw["loudness"]
    return {
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
        "vinyl": raw["vinyl"],
        "click_count": raw["click_count"],
        "clip_times_sec": raw["clip_times_sec"],
        "flags": verdict["flags"],
        "verdict": verdict["verdict"],
        "verdict_reasons": verdict["reasons"],
        "info_reasons": verdict["info_reasons"],
        "spectrogram_path": None,
    }


def get_or_analyze(path: str, with_spectrogram: bool = False) -> dict:
    p = Path(path)
    st = p.stat()
    abs_path = str(p.resolve())
    mtime_ns = st.st_mtime_ns
    size = st.st_size
    config_hash = core.config_hash.CONFIG_HASH

    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, raw_json FROM measurements "
            "WHERE abs_path=? AND mtime_ns=? AND size=?",
            (abs_path, mtime_ns, size),
        ).fetchone()

        if row is None:
            # MISS: analyze, persist. analyze_raw returns the raw components
            # directly (no need to reconstruct them from the assembled dict).
            raw, assembled = core.analyzer.analyze_raw(path)
            verdict = {
                "verdict": assembled["verdict"],
                "flags": assembled["flags"],
                "reasons": assembled["verdict_reasons"],
                "info_reasons": assembled["info_reasons"],
            }
            now = time.time()
            conn.execute(
                "INSERT OR IGNORE INTO measurements "
                "(abs_path, mtime_ns, size, raw_json, created) VALUES (?,?,?,?,?)",
                (abs_path, mtime_ns, size, json.dumps(raw, default=numpy_to_native), now),
            )
            conn.commit()
            mrow = conn.execute(
                "SELECT id FROM measurements "
                "WHERE abs_path=? AND mtime_ns=? AND size=?",
                (abs_path, mtime_ns, size),
            ).fetchone()
            mid = mrow[0]
            conn.execute(
                "INSERT OR REPLACE INTO verdicts "
                "(measurement_id, config_hash, verdict_json, created) VALUES (?,?,?,?)",
                (mid, config_hash, json.dumps(verdict, default=numpy_to_native), now),
            )
            conn.commit()
        else:
            mid, raw_json = row[0], row[1]
            raw = json.loads(raw_json)
            vrow = conn.execute(
                "SELECT verdict_json FROM verdicts "
                "WHERE measurement_id=? AND config_hash=?",
                (mid, config_hash),
            ).fetchone()
            if vrow is not None:
                verdict = json.loads(vrow[0])
            else:
                verdict = core.reverdict.reverdict_from_raw(raw)
                conn.execute(
                    "INSERT OR REPLACE INTO verdicts "
                    "(measurement_id, config_hash, verdict_json, created) "
                    "VALUES (?,?,?,?)",
                    (mid, config_hash, json.dumps(verdict, default=numpy_to_native), time.time()),
                )
                conn.commit()

    result = _assemble(path, raw, verdict)
    result["spectrogram_path"] = None
    if with_spectrogram:
        from core.spectrogram import generate_spectrogram
        result["spectrogram_path"] = generate_spectrogram(path)
    return result


def invalidate(path: str) -> None:
    abs_path = str(Path(path).resolve())
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM measurements WHERE abs_path=?", (abs_path,))
        conn.commit()
