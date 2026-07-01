"""RED tests for T-2 — the `--history` CLI subcommand on core.analyzer.

Contract (from PLAN T-2):
- `core.analyzer.main(argv=None) -> int` exists and is unit-testable (no subprocess).
- `main(["--history", query, "--limit", N])` prints a JSON **array** to stdout
  (== core.history.search_history(query, N)), returns 0.
- `--history` with no positional → search_history("", 10) (empty query, default limit).
- Empty result → stdout parses to `[]`.
- No collision with the single-file path: `main(["some.flac"])` routes to
  core.cache.get_or_analyze (prints a JSON **object**), history is NOT touched;
  `--spectrogram` still forwards with_spectrogram=True.
- `main([])` in analyze mode (no file) still errors/usage (non-zero), unchanged.

These tests monkeypatch collaborators — no real audio, no subprocess. They are RED
until `core.analyzer.main` exists.
"""
import json
import sys
import types

import pytest

import core.analyzer as analyzer_mod
import core.cache


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _Recorder:
    """Records positional+keyword calls, returns a fixed value."""

    def __init__(self, return_value):
        self.return_value = return_value
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_value


def _install_fake_history(monkeypatch, recorder):
    """Inject a fake `core.history` module whose search_history is `recorder`.

    The real impl does a lazy `import core.history` inside the --history branch,
    so seeding sys.modules makes that import resolve to our fake regardless of
    whether T-1 has landed yet. Keeps the RED reason = `main` missing, not an
    ImportError.
    """
    fake_mod = types.ModuleType("core.history")
    fake_mod.search_history = recorder
    monkeypatch.setitem(sys.modules, "core.history", fake_mod)
    # also expose as attribute on the `core` package for `core.history.x` access
    import core as _core_pkg
    monkeypatch.setattr(_core_pkg, "history", fake_mod, raising=False)
    return fake_mod


def _resolve_query_limit(call):
    """Normalize a recorded (args, kwargs) call → (query, limit)."""
    args, kwargs = call
    query = kwargs.get("query", args[0] if len(args) > 0 else None)
    limit = kwargs.get("limit", args[1] if len(args) > 1 else None)
    return query, limit


# a JSON-serializable fake history payload (an ARRAY of result objects)
_FAKE_HITS = [
    {
        "filename": "kick_drum.wav",
        "file_path": "/music/kick_drum.wav",
        "verdict": "CLUB READY",
        "flags": [],
        "analyzed_at": 1_700_000_000.0,
        "file_exists": True,
    },
    {
        "filename": "deep_kick.flac",
        "file_path": "/music/deep_kick.flac",
        "verdict": "REVIEW",
        "flags": ["SUSPECT_LOSSLESS"],
        "analyzed_at": 1_699_990_000.0,
        "file_exists": False,
    },
]


# ---------------------------------------------------------------------------
# T-2 tests
# ---------------------------------------------------------------------------

def test_history_query_and_limit(monkeypatch, capsys):
    """--history kick --limit 5 → JSON array == fake return; called ("kick", 5); returns 0."""
    rec = _Recorder(_FAKE_HITS)
    _install_fake_history(monkeypatch, rec)

    rc = analyzer_mod.main(["--history", "kick", "--limit", "5"])

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list), f"history path must print a JSON array, got {type(parsed)}"
    assert parsed == _FAKE_HITS

    assert len(rec.calls) == 1, f"search_history should be called once, got {rec.calls}"
    query, limit = _resolve_query_limit(rec.calls[0])
    assert query == "kick"
    assert limit == 5

    assert rc == 0


def test_history_no_query_defaults(monkeypatch, capsys):
    """--history with no positional → search_history("", 10) (empty query, default limit)."""
    rec = _Recorder(_FAKE_HITS)
    _install_fake_history(monkeypatch, rec)

    rc = analyzer_mod.main(["--history"])

    assert len(rec.calls) == 1, f"search_history should be called once, got {rec.calls}"
    query, limit = _resolve_query_limit(rec.calls[0])
    assert query == "", f"empty query expected, got {query!r}"
    assert limit == 10, f"default limit 10 expected, got {limit!r}"
    assert rc == 0


def test_history_empty_result(monkeypatch, capsys):
    """Fake returns [] → stdout parses to []."""
    rec = _Recorder([])
    _install_fake_history(monkeypatch, rec)

    rc = analyzer_mod.main(["--history", "nomatch"])

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == [], f"empty history must print [], got {out!r}"
    assert rc == 0


def test_single_file_path_no_collision(monkeypatch, capsys):
    """main(["some.flac"]) routes to get_or_analyze (JSON object), history NOT called."""
    fake_result = {
        "filename": "some.flac",
        "file_path": "/abs/some.flac",
        "verdict": "CLUB READY",
        "flags": [],
    }
    goa = _Recorder(fake_result)
    monkeypatch.setattr(core.cache, "get_or_analyze", goa)

    hist = _Recorder([{"should": "not be used"}])
    _install_fake_history(monkeypatch, hist)

    analyzer_mod.main(["some.flac"])

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, dict), f"single-file path must print a JSON object, got {type(parsed)}"

    assert len(goa.calls) == 1, "get_or_analyze must be called for the single-file path"
    assert goa.calls[0][0][0] == "some.flac", f"file arg wrong: {goa.calls[0]}"
    assert len(hist.calls) == 0, "history must NOT be called on the single-file path"


def test_single_file_spectrogram_forwarded(monkeypatch, capsys):
    """--spectrogram forwards with_spectrogram=True to get_or_analyze."""
    goa = _Recorder({"filename": "some.flac", "verdict": "CLUB READY"})
    monkeypatch.setattr(core.cache, "get_or_analyze", goa)

    analyzer_mod.main(["some.flac", "--spectrogram"])

    assert len(goa.calls) == 1
    args, kwargs = goa.calls[0]
    with_spec = kwargs.get("with_spectrogram", args[1] if len(args) > 1 else None)
    assert with_spec is True, f"with_spectrogram=True expected, got call {goa.calls[0]}"


def test_no_args_is_usage_error(monkeypatch):
    """main([]) in analyze mode (no file, no --history) → non-zero / usage error."""
    # ensure it never silently reaches a real analysis
    monkeypatch.setattr(core.cache, "get_or_analyze", _Recorder({"unexpected": True}))

    try:
        rc = analyzer_mod.main([])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        assert code != 0, "no-args usage error must exit non-zero"
    else:
        assert rc != 0, f"no-args analyze mode must return non-zero, got {rc}"
