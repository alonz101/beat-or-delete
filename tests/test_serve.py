"""RED tests for T-1: `--serve` mode in core/analyzer.py.

These drive the SOURCE via subprocess: `python core/analyzer.py --serve`.
They run REAL audio through the REAL pipeline (real core.cache.get_or_analyze ->
real librosa/FFT -> real numpy float32). No monkeypatching of analyze().
This is deliberate: the sqlite float32 bug escaped because tests fed hand-written
Python dicts; here genuine numpy scalars reach json.dumps.
"""
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# worktree root = parent of tests/
ROOT = Path(__file__).resolve().parent.parent
ANALYZER = ROOT / "core" / "analyzer.py"

# first response pays import cost (matplotlib/numba/librosa) — be generous
FIRST_TIMEOUT = 60.0
NEXT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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
def hermetic_home(tmp_path):
    """Redirect HOME so the sqlite cache lives in a throwaway dir (cache uses Path.home())."""
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env["HOME"] = str(home)
    return env


class ServeClient:
    """Launches `analyzer.py --serve` and does line-based request/response over pipes.

    Responses are read from the process's stdout (the saved fd in serve mode).
    A background reader thread + queue lets us enforce per-read timeouts so a
    hung / non-responding process fails the test fast instead of blocking.
    """

    def __init__(self, env):
        self.proc = subprocess.Popen(
            [sys.executable, str(ANALYZER), "--serve"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._q = queue.Queue()
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()

    def _reader(self):
        for line in self.proc.stdout:
            self._q.put(line)
        self._q.put(None)  # EOF sentinel

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout):
        try:
            line = self._q.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(
                f"no response within {timeout}s (serve mode likely missing). "
                f"stderr tail: {self._stderr_tail()}"
            )
        if line is None:
            raise AssertionError(
                f"process closed stdout without responding. "
                f"stderr tail: {self._stderr_tail()}"
            )
        return json.loads(line)

    def _stderr_tail(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            return (self.proc.stderr.read() or "")[-800:]
        except Exception:
            return "<unavailable>"

    def close(self):
        try:
            self.send({"cmd": "shutdown"})
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        finally:
            for s in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    s.close()
                except Exception:
                    pass


@pytest.fixture
def serve(hermetic_home):
    clients = []

    def _make():
        c = ServeClient(hermetic_home)
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.close()


ANALYZE_SHAPE_KEYS = {
    "filename", "format", "authenticity", "playability",
    "verdict", "flags", "spectrogram_path",
}


# ---------------------------------------------------------------------------
# AC-1: serve loop / JSON Lines
# ---------------------------------------------------------------------------
def test_ac1_two_requests_two_responses(serve, wav_file):
    c = serve()
    c.send({"id": 1, "path": str(wav_file), "spectrogram": False})
    r1 = c.recv(FIRST_TIMEOUT)
    c.send({"id": 2, "path": str(wav_file), "spectrogram": False})
    r2 = c.recv(NEXT_TIMEOUT)

    assert r1["id"] == 1
    assert r2["id"] == 2
    assert "result" in r1 and "result" in r2
    assert ANALYZE_SHAPE_KEYS.issubset(r1["result"].keys())
    assert ANALYZE_SHAPE_KEYS.issubset(r2["result"].keys())


# ---------------------------------------------------------------------------
# AC-2: routes through cache (matches direct get_or_analyze on same file)
# ---------------------------------------------------------------------------
def test_ac2_result_matches_direct_cache_call(serve, wav_file, hermetic_home):
    c = serve()
    c.send({"id": 7, "path": str(wav_file), "spectrogram": False})
    resp = c.recv(FIRST_TIMEOUT)
    served = resp["result"]

    # Direct call to the real cache layer for the same file, in-process.
    # Use the same HOME so both point at the same cache db (proves same path).
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = hermetic_home["HOME"]
    try:
        import core.cache
        direct = core.cache.get_or_analyze(str(wav_file), with_spectrogram=False)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home

    # Round-trip the direct result through json so types match the served (parsed) one.
    from core.utils import numpy_to_native
    direct = json.loads(json.dumps(direct, default=numpy_to_native))

    assert served["verdict"] == direct["verdict"]
    assert served["flags"] == direct["flags"]
    assert served["format"] == direct["format"]
    assert served["authenticity"] == direct["authenticity"]
    assert served["playability"] == direct["playability"]


# ---------------------------------------------------------------------------
# AC-3: imports paid once — second request is a fast cache hit (not ~8s)
# ---------------------------------------------------------------------------
def test_ac3_second_request_is_fast(serve, wav_file):
    import time

    c = serve()
    c.send({"id": 1, "path": str(wav_file), "spectrogram": False})
    c.recv(FIRST_TIMEOUT)  # warm imports + populate cache

    c.send({"id": 2, "path": str(wav_file), "spectrogram": False})
    start = time.perf_counter()
    r2 = c.recv(NEXT_TIMEOUT)
    elapsed = time.perf_counter() - start

    assert r2["id"] == 2 and "result" in r2
    assert elapsed < 1.0, f"second request took {elapsed:.2f}s — imports not amortized / no cache hit"


# ---------------------------------------------------------------------------
# AC-4: bad file doesn't kill the loop
# ---------------------------------------------------------------------------
def test_ac4_bad_file_then_valid(serve, wav_file, tmp_path):
    c = serve()
    missing = tmp_path / "does_not_exist.wav"
    c.send({"id": 1, "path": str(missing), "spectrogram": False})
    bad = c.recv(FIRST_TIMEOUT)

    assert bad["id"] == 1
    # loop must respond to a bad file: either an error response or a result-with-error.
    signalled_error = ("error" in bad) or (
        isinstance(bad.get("result"), dict) and "error" in bad["result"]
    )
    assert signalled_error, f"expected error signal for missing file, got: {bad}"

    # process must still be alive and answer a valid request
    c.send({"id": 2, "path": str(wav_file), "spectrogram": False})
    good = c.recv(NEXT_TIMEOUT)
    assert good["id"] == 2
    assert "result" in good
    assert ANALYZE_SHAPE_KEYS.issubset(good["result"].keys())


# ---------------------------------------------------------------------------
# float32 regression — response serializes & numeric fields are plain JSON numbers
# ---------------------------------------------------------------------------
def test_float32_round_trips_as_plain_numbers(serve, wav_file):
    c = serve()
    c.send({"id": 1, "path": str(wav_file), "spectrogram": False})
    resp = c.recv(FIRST_TIMEOUT)  # recv already json.loads — proves it serialized

    result = resp["result"]
    peak = result["playability"]["peak_dbfs"]
    cov = result["authenticity"]["spectral_coverage_ratio"]
    # numpy float32 would have crashed json.dumps without numpy_to_native;
    # after round-trip these must be plain JSON numbers, not strings/objects.
    assert isinstance(peak, (int, float)), f"peak_dbfs not a JSON number: {peak!r}"
    assert isinstance(cov, (int, float)), f"coverage_ratio not a JSON number: {cov!r}"


# ---------------------------------------------------------------------------
# AC-5: one-shot CLI mode unchanged
# ---------------------------------------------------------------------------
def test_ac5_oneshot_still_works(wav_file, hermetic_home):
    proc = subprocess.run(
        [sys.executable, str(ANALYZER), str(wav_file)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=hermetic_home,
        timeout=FIRST_TIMEOUT,
    )
    assert proc.returncode == 0, f"one-shot exited {proc.returncode}; stderr: {proc.stderr[-800:]}"
    obj = json.loads(proc.stdout)  # single JSON object on stdout
    assert ANALYZE_SHAPE_KEYS.issubset(obj.keys())
    assert obj["filename"] == wav_file.name
