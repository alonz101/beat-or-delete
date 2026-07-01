"""Global test isolation.

Every test must be immune to the real user overrides file at
``~/Library/Application Support/BeatOrDelete/thresholds.json``. Without this,
any test that exercises ``compute_flags`` / ``reverdict`` / ``_assemble`` (which
now read ``runtime_config.active()``) silently picks up whatever the installed
app last Saved — so the suite is green in CI but red on any dev machine that has
used the Config tab. This autouse fixture points ``_overrides_path`` at an empty
temp dir and resets the cached snapshot around each test.

Tests that need specific overrides still work: they either re-monkeypatch
``_overrides_path`` (applied after this fixture, so theirs wins) or call
``runtime_config.set_overrides(...)`` (in-process, bypasses the file entirely).
"""

import pytest

import core.runtime_config as _rc


@pytest.fixture(autouse=True)
def _isolate_runtime_config(tmp_path_factory, monkeypatch):
    empty = tmp_path_factory.mktemp("rc_isolate")
    monkeypatch.setattr(_rc, "_overrides_path", lambda: empty / "thresholds.json")
    _rc.reset()
    yield
    _rc.reset()
