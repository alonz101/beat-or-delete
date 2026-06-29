"""RED tests for L-1: heavy audio libs must load ONLY on a real cache MISS.

`dj-analyze` loads librosa + numba + matplotlib (~7.5s frozen) at startup even
for a cache HIT, because core/analyzer.py and core/cache.py import the heavy
analysis modules (spectral->librosa, spectrogram->librosa+matplotlib) at module
top level. The refactor will make those load lazily — only when real analysis
runs (a MISS). These tests lock that in.

We do NOT measure time (flaky). Instead each run happens in a clean subprocess
interpreter and we assert on `sys.modules`: did librosa / matplotlib get loaded?
HOME points at a tmp dir so the sqlite cache (~/Library/Application Support/
BeatOrDelete/cache.db) is hermetic and persists across the steps that need it.

Real audio (a 2s sine WAV) goes through the REAL pipeline — same approach as
tests/test_serve.py — so a genuine MISS actually loads librosa.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# worktree root = parent of tests/
REPO = Path(__file__).resolve().parent.parent


def run_py(snippet: str, home: Path):
    """Run a snippet in a fresh interpreter with HOME redirected; cwd=repo root."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(snippet)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=120,
    )


def _write_sine(path: Path) -> Path:
    """Write a real ~2s 440Hz sine WAV — genuine numpy float32 through pipeline."""
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    sf.write(str(path), sig, sr)
    return path


@pytest.fixture
def wav_file(tmp_path):
    return _write_sine(tmp_path / "tone.wav")


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def _last_line(stdout: str) -> str:
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# ---------------------------------------------------------------------------
# 1. Merely importing core.cache must not drag in librosa/matplotlib.
# ---------------------------------------------------------------------------
def test_importing_cache_is_light(home):
    proc = run_py(
        """
        import sys
        import core.cache  # noqa: F401
        print('librosa' in sys.modules, 'matplotlib' in sys.modules)
        """,
        home,
    )
    assert proc.returncode == 0, f"import failed; stderr:\n{proc.stderr[-1500:]}"
    assert _last_line(proc.stdout) == "False False", (
        f"importing core.cache loaded heavy libs. stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr[-800:]}"
    )


# ---------------------------------------------------------------------------
# 2a. Sanity: a real MISS DOES load librosa (analysis genuinely runs).
# ---------------------------------------------------------------------------
def test_cache_miss_loads_librosa(home, wav_file):
    proc = run_py(
        f"""
        import sys
        import core.cache as c
        r = c.get_or_analyze({str(wav_file)!r})
        print(bool(r.get('verdict')), 'librosa' in sys.modules)
        """,
        home,
    )
    assert proc.returncode == 0, f"miss run failed; stderr:\n{proc.stderr[-1500:]}"
    assert _last_line(proc.stdout) == "True True", (
        f"expected MISS to produce a verdict AND load librosa. "
        f"stdout: {proc.stdout!r} stderr: {proc.stderr[-800:]}"
    )


# ---------------------------------------------------------------------------
# 2b. A cache HIT must return the cached verdict WITHOUT loading librosa.
# ---------------------------------------------------------------------------
def test_cache_hit_does_not_load_librosa(home, wav_file):
    # Step A: populate (MISS) — separate process, same HOME so cache persists.
    pop = run_py(
        f"""
        import core.cache as c
        c.get_or_analyze({str(wav_file)!r})
        print('populated')
        """,
        home,
    )
    assert pop.returncode == 0, f"populate failed; stderr:\n{pop.stderr[-1500:]}"

    # Step B: HIT — fresh interpreter, same HOME. Must NOT load librosa.
    hit = run_py(
        f"""
        import sys
        import core.cache as c
        r = c.get_or_analyze({str(wav_file)!r})
        print(bool(r.get('verdict')), 'librosa' in sys.modules)
        """,
        home,
    )
    assert hit.returncode == 0, f"hit run failed; stderr:\n{hit.stderr[-1500:]}"
    assert _last_line(hit.stdout) == "True False", (
        f"cache HIT should return verdict without loading librosa. "
        f"stdout: {hit.stdout!r} stderr: {hit.stderr[-800:]}"
    )


# ---------------------------------------------------------------------------
# 3. A cache HIT must not load matplotlib either.
# ---------------------------------------------------------------------------
def test_cache_hit_does_not_load_matplotlib(home, wav_file):
    pop = run_py(
        f"""
        import core.cache as c
        c.get_or_analyze({str(wav_file)!r})
        print('populated')
        """,
        home,
    )
    assert pop.returncode == 0, f"populate failed; stderr:\n{pop.stderr[-1500:]}"

    hit = run_py(
        f"""
        import sys
        import core.cache as c
        r = c.get_or_analyze({str(wav_file)!r})
        print(bool(r.get('verdict')), 'matplotlib' in sys.modules)
        """,
        home,
    )
    assert hit.returncode == 0, f"hit run failed; stderr:\n{hit.stderr[-1500:]}"
    assert _last_line(hit.stdout) == "True False", (
        f"cache HIT should return verdict without loading matplotlib. "
        f"stdout: {hit.stdout!r} stderr: {hit.stderr[-800:]}"
    )


# ---------------------------------------------------------------------------
# 4. Reverdict path (config changed, measurement still valid): re-decide from
#    cached raw — no audio libs. This is the feature the user cares about:
#    changing thresholds re-classifies instantly without re-reading audio.
# ---------------------------------------------------------------------------
def test_reverdict_does_not_load_librosa(home, wav_file):
    # Populate with the real config hash.
    pop = run_py(
        f"""
        import core.cache as c
        c.get_or_analyze({str(wav_file)!r})
        print('populated')
        """,
        home,
    )
    assert pop.returncode == 0, f"populate failed; stderr:\n{pop.stderr[-1500:]}"

    # Force a config change so the verdict layer MISSES but measurements HIT
    # -> reverdict_from_raw path. Must not touch librosa.
    rev = run_py(
        f"""
        import sys
        import core.config_hash
        core.config_hash.CONFIG_HASH = "DIFFERENT_HASH_FORCES_REVERDICT"
        import core.cache as c
        r = c.get_or_analyze({str(wav_file)!r})
        print(bool(r.get('verdict')), 'librosa' in sys.modules)
        """,
        home,
    )
    assert rev.returncode == 0, f"reverdict run failed; stderr:\n{rev.stderr[-1500:]}"
    assert _last_line(rev.stdout) == "True False", (
        f"reverdict (config changed) should re-decide from cached raw without "
        f"loading librosa. stdout: {rev.stdout!r} stderr: {rev.stderr[-800:]}"
    )


# ---------------------------------------------------------------------------
# 5. Guard: a MISS on an empty cache still produces a full valid result dict
#    AND loads librosa (analysis genuinely happened). Integration over a real
#    file — catches a refactor that breaks analysis to satisfy the above.
# ---------------------------------------------------------------------------
def test_cache_miss_still_works_and_loads_librosa(home, wav_file):
    proc = run_py(
        f"""
        import sys, json
        import core.cache as c
        from core.utils import numpy_to_native
        r = c.get_or_analyze({str(wav_file)!r})
        keys = {{"verdict", "flags", "format", "authenticity", "playability"}}
        ok = keys.issubset(r.keys())
        print(json.dumps({{
            "ok": ok,
            "missing": sorted(keys - set(r.keys())),
            "librosa": 'librosa' in sys.modules,
        }}, default=numpy_to_native))
        """,
        home,
    )
    assert proc.returncode == 0, f"miss run failed; stderr:\n{proc.stderr[-1500:]}"
    import json
    payload = json.loads(_last_line(proc.stdout))
    assert payload["ok"], f"result missing keys {payload['missing']}"
    assert payload["librosa"] is True, "empty-cache MISS must load librosa (real analysis)"
