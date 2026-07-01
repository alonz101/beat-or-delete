"""History query path (T-1): search cached measurements by filename substring.

Read + reverdict over `measurements` — reuses core.cache internals, never
writes `measurements`. Collaborators referenced through their modules so tests
can monkeypatch:
    core.config_hash.CONFIG_HASH (read at call time)
    core.reverdict.reverdict_from_raw
"""

import json
import os
import time
from contextlib import closing

import core.cache
import core.config_hash
import core.reverdict
from core.utils import numpy_to_native


def search_history(query: str = "", limit: int = 10) -> list[dict]:
    q = query.lower()
    config_hash = core.config_hash.CONFIG_HASH

    with closing(core.cache._connect()) as conn:
        rows = conn.execute(
            "SELECT id, abs_path, mtime_ns, size, raw_json, created FROM measurements"
        ).fetchall()

        # Collapse to the most-recent row per abs_path (Q1 locked).
        newest: dict[str, tuple] = {}
        for row in rows:
            abs_path = row[1]
            created = row[5]
            prev = newest.get(abs_path)
            if prev is None or created > prev[5]:
                newest[abs_path] = row

        candidates = []
        for row in newest.values():
            basename = os.path.basename(row[1]).lower()
            if q and q not in basename:
                continue
            candidates.append(row)

        if q:
            def sort_key(row):
                basename = os.path.basename(row[1]).lower()
                return (0 if basename.startswith(q) else 1, -row[5])
            candidates.sort(key=sort_key)
        else:
            candidates.sort(key=lambda row: row[5], reverse=True)

        candidates = candidates[:limit]

        results = []
        for row in candidates:
            mid, abs_path, created = row[0], row[1], row[5]
            raw = json.loads(row[4])

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
                    (mid, config_hash,
                     json.dumps(verdict, default=numpy_to_native), time.time()),
                )
                conn.commit()

            result = core.cache._assemble(abs_path, raw, verdict)
            result["analyzed_at"] = created
            result["file_exists"] = os.path.exists(abs_path)
            results.append(result)

        return results
