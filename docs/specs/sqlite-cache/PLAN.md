# PLAN: Analysis Cache (SQLite)

## Overview
Add a `core/cache.py` wrapper layer that memoizes analysis in a local SQLite DB at
`~/Library/Application Support/BeatOrDelete/cache.db`. Two tables: `measurements`
(raw check outputs, keyed by file identity = abs_path + mtime_ns + size_bytes) and
`verdicts` (verdict output, keyed by measurements.rowid + config_hash). `get_or_analyze()`
replaces direct `analyze()` calls in `analyzer.py`'s CLI and `batch.py`. `analyze()`
itself is untouched. Changing a file invalidates its measurements (full re-analysis);
changing a `config.py` threshold invalidates only verdicts (recompute from cached raw
data, no FFT). `spectrogram_path` is never persisted — always `None` in the cached dict,
populated by the caller. No new pip deps (sqlite3 + hashlib are stdlib).

## Waves
Wave 1 — Pure helpers (no I/O): `config_hash` derivation + a re-verdict shim that
recomputes a verdict from a cached raw blob without touching audio. Independently unit-
testable, zero dependencies on DB. Unblocks the cache logic in Wave 2.

Wave 2 — Cache engine: `core/cache.py` with schema, connection handling, and the two
public functions. Depends on Wave 1 helpers. Fully testable in isolation via temp DB.

Wave 3 — Wire-up: swap `analyze` → `get_or_analyze` at the two call sites (CLI entry in
`analyzer.py`, ThreadPoolExecutor in `batch.py`). Solo wave — touches existing public
entry points and is the only place threading meets the cache.

## Tasks
| # | Wave | File | What | Touches AC |
|---|------|------|------|------------|
| T-1 | 1 | `core/config_hash.py` (new) | Introspect all UPPERCASE module-level constants in `core/config.py`, build SHA-256 of their sorted `repr`. Expose `CONFIG_HASH` (computed at import) + `compute_config_hash()`. | AC-3 |
| T-2 | 1 | `core/reverdict.py` (new) | `reverdict_from_raw(raw: dict) -> dict`: given the cached raw blob (meta, spectral, integrity, loudness, vinyl), call `compute_verdict(...)` and return its `{verdict,flags,reasons,info_reasons}`. No audio load. | AC-3 |
| T-3 | 2 | `core/cache.py` (new) | DB path resolution + auto-create, schema DDL, `get_or_analyze(path, with_spectrogram)`, `invalidate(path)`, per-call connection. Uses T-1 + T-2. | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7 |
| T-4 | 3 | `core/analyzer.py` | CLI `__main__` block: call `get_or_analyze` instead of `analyze`. Keep `analyze()` definition unchanged. | AC-1, AC-6 |
| T-5 | 3 | `batch.py` | Replace `pool.submit(analyze, str(f))` (line 46) and import (line 17) with `get_or_analyze`. Verify thread-safety contract. | AC-1, AC-2, AC-4 |

## Interface contracts

### T-1 `core/config_hash.py`
```python
import core.config as config
def compute_config_hash() -> str:
    # iterate vars(config), keep names == name.upper() and not starting with "_",
    # values must be primitives (int/float/str/bool); build sorted list of
    # f"{k}={v!r}", join with "\n", return hashlib.sha256(s.encode()).hexdigest()
    ...
CONFIG_HASH: str = compute_config_hash()   # module-load-time, cached
```
Rationale for introspection over a hardcoded list: config.py has ~50 constants and
gains more over time; a hardcoded tuple would silently rot. Filtering on `k.upper()==k`
captures every threshold and ignores imports/dunders.

### T-2 `core/reverdict.py`
```python
from core.verdict import compute_verdict
def reverdict_from_raw(raw: dict) -> dict:
    return compute_verdict(
        raw["meta"], raw["spectral"], raw["integrity"],
        raw["loudness"], raw.get("vinyl"),
    )
```
The `raw` dict shape is defined by T-3 (see below) and MUST contain the five
sub-dicts exactly as `compute_verdict` expects them.

### T-3 `core/cache.py`
```python
def get_or_analyze(path: str, with_spectrogram: bool = False) -> dict
def invalidate(path: str) -> None
```
- `get_or_analyze` returns a dict identical in shape to `analyze()`'s return value.
- `spectrogram_path` is ALWAYS `None` in the cached/returned dict; when
  `with_spectrogram=True`, the function calls `generate_spectrogram(path)` itself
  AFTER assembling the result and sets the key (never cached — AC-6).

**File identity** (cache key for measurements):
```python
st = os.stat(abs_path)
key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
```

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS measurements (
  id        INTEGER PRIMARY KEY,
  abs_path  TEXT    NOT NULL,
  mtime_ns  INTEGER NOT NULL,
  size      INTEGER NOT NULL,
  raw_json  TEXT    NOT NULL,   -- JSON: {meta, spectral, integrity, loudness, vinyl, click_count, clip_times_sec}
  created   REAL    NOT NULL,
  UNIQUE(abs_path, mtime_ns, size)
);
CREATE TABLE IF NOT EXISTS verdicts (
  measurement_id INTEGER NOT NULL,
  config_hash    TEXT    NOT NULL,
  verdict_json   TEXT    NOT NULL,   -- JSON: {verdict, flags, reasons, info_reasons}
  created        REAL    NOT NULL,
  PRIMARY KEY (measurement_id, config_hash),
  FOREIGN KEY (measurement_id) REFERENCES measurements(id) ON DELETE CASCADE
);
```

**Control flow of `get_or_analyze`:**
1. Resolve identity key. Look up `measurements` row.
2. **Measurements MISS** → run `analyze()` once, split its return into a `raw` blob
   (the five sub-dicts + click_count + clip_times_sec) and persist; persist verdict too.
3. **Measurements HIT, verdicts HIT** (config_hash matches) → load both, assemble dict,
   NO FFT. (AC-1)
4. **Measurements HIT, verdicts MISS** (config changed) → load raw, call
   `reverdict_from_raw(raw)`, persist new verdict row, assemble. NO FFT. (AC-3)
5. Set `spectrogram_path=None`; if `with_spectrogram`, generate + set.

**The raw/assembled split is the key design risk:** `analyze()` does NOT currently
return the five sub-dicts as discrete objects — it inlines them into nested
`format`/`authenticity`/`playability` dicts (analyzer.py lines 38–81). The cache cannot
reconstruct `meta`/`spectral`/`integrity`/`loudness` from the assembled result. See
Open Question 1 — this dictates whether T-3 re-runs the check modules from raw arrays
(impossible without audio) or whether `analyze()` must expose the raw sub-dicts.

**Connection / thread-safety:** open a fresh `sqlite3.connect(db_path)` per
`get_or_analyze` call inside a `with closing(...)` block; enable
`PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=WAL` (WAL allows concurrent readers +
one writer, suited to the ThreadPoolExecutor in batch.py). Do NOT keep a module-level
connection. Wrap each writer in a short transaction; use `INSERT OR IGNORE` /
`INSERT OR REPLACE` to tolerate concurrent first-time inserts of the same file.

**DB path (AC-5):**
```python
Path.home() / "Library/Application Support/BeatOrDelete/cache.db"
# mkdir(parents=True, exist_ok=True) before connect
```

## Test plan
Bugsy verifies, per AC:
- **AC-1**: Analyze a fixture twice via `get_or_analyze`. Assert 2nd call does no FFT —
  monkeypatch `core.analyzer.analyze` (or `check_spectral`) with a counter; expect call
  count 1 after two `get_or_analyze` calls. Returned dicts equal (minus spectrogram).
- **AC-2**: Analyze, then bump file mtime (`os.utime`) or append a byte. Assert the
  analyze-counter increments again (cache miss → re-analysis).
- **AC-3**: Analyze, then monkeypatch a `config.py` constant so `CONFIG_HASH` differs
  (or call `get_or_analyze` with a patched config_hash). Assert verdict recomputed
  (verdicts table gains a row for new hash) but `analyze`/FFT counter does NOT increment.
- **AC-4**: Run `batch.run_batch` on a folder, then `get_or_analyze` on one file in it;
  assert it's a hit (shared DB, counter unchanged). Confirm both import the same module.
- **AC-5**: Delete the DB, call `get_or_analyze`, assert
  `~/Library/Application Support/BeatOrDelete/cache.db` exists afterward. (Use a
  monkeypatched temp HOME so tests don't touch the real path.)
- **AC-6**: `get_or_analyze(path, with_spectrogram=True)` then again; assert
  `spectrogram_path` is a fresh value each call (regenerated, not the cached string),
  and that no `spectrogram_path` appears in `raw_json` / `verdict_json` columns.
- **AC-7**: `grep` the new modules — only stdlib imports (`sqlite3`, `hashlib`, `json`,
  `os`, `pathlib`, `contextlib`). `requirements.txt` unchanged.
- **Concurrency**: hammer `get_or_analyze` on the same new file from N threads; assert no
  `sqlite3.OperationalError`, exactly one measurements row, result dicts consistent.
- **invalidate**: after caching, `invalidate(path)` removes measurements + (cascade)
  verdict rows; next call is a miss.

## Open questions
1. **Raw blob source — the central decision.** `analyze()` (analyzer.py:38–81) discards
   the discrete `meta/spectral/integrity/loudness` dicts into a reshaped result, so the
   cache can't recover them for `reverdict_from_raw`. Options:
   (a) Refactor `analyze()` to also return the raw sub-dicts (e.g. add a `"_raw"` key or
   split into `analyze_raw()` + `assemble()`), keeping the public dict shape intact —
   cleanest, but edits `analyzer.py` beyond the SPEC's "don't change analyze" rule.
   (b) Have `cache.py` re-derive the five sub-dicts from the assembled result (lossy /
   fragile — field names differ and some inputs like `meta` are partly dropped).
   Recommend (a): add a thin `analyze_raw(path) -> (raw, assembled_without_spec)` used by
   both `analyze` and `cache`. Confirm this is acceptable, since SPEC says don't make
   `analyze` *use the cache* — refactoring its internals to expose raw is a different change.
2. `config_hash` over **all** UPPERCASE constants includes non-threshold tuning like
   `SPECTRAL_FFT_SIZE` and `SPECTRAL_ANALYSIS_DURATION` — changing those genuinely
   invalidates measurements, not just verdicts, yet they'd only bust the verdict layer.
   Should FFT-affecting constants instead be folded into the *measurements* key (or a
   second `analysis_hash`)? For v1, simplest is: any config change busts verdicts only,
   accept that changing FFT size requires a manual file-touch to fully re-measure. Confirm
   acceptable, or split into `analysis_hash` (in measurements key) + `verdict_hash`.
3. WAL mode leaves `-wal`/`-shm` sidecar files next to `cache.db`. Acceptable in the
   Application Support dir? (Standard, but flagging.)
