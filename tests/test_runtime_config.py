"""RED tests for T-1: core/runtime_config.py (does not exist yet).

Contract under test:
    _overrides_path() -> Path           # monkeypatchable
    load_overrides() -> dict            # flat {NAME: value}, coerced, filtered, never raises
    active() -> SimpleNamespace         # cached defaults overlaid with overrides
    set_overrides(d: dict) -> None      # test hook: inject in-process, busts cache
    reset() -> None                     # test hook: clear cache → next active() re-reads file

These tests are expected to FAIL right now with ModuleNotFoundError /
AttributeError because core/runtime_config.py has not been written.
"""

import importlib
import json

import pytest

import core.config as config


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def rc(monkeypatch, tmp_path):
    """Import core.runtime_config, point its overrides path at a tmp file with
    NO file present, and guarantee the process-lifetime cache is reset both
    before and after the test so state never leaks between tests."""
    import core.runtime_config as rc_mod
    rc_mod = importlib.reload(rc_mod)
    overrides_file = tmp_path / "thresholds.json"
    monkeypatch.setattr(rc_mod, "_overrides_path", lambda: overrides_file)
    rc_mod.reset()
    yield rc_mod
    rc_mod.reset()


def _write(path_file, obj):
    """Write a JSON object (or raw string) to the overrides file."""
    if isinstance(obj, str):
        path_file.write_text(obj)
    else:
        path_file.write_text(json.dumps(obj))


# --------------------------------------------------------------------------- #
# Public API surface
# --------------------------------------------------------------------------- #

def test_public_api_exists(rc):
    assert callable(rc.load_overrides)
    assert callable(rc.active)
    assert callable(rc.set_overrides)
    assert callable(rc.reset)
    assert callable(rc._overrides_path)


# --------------------------------------------------------------------------- #
# 1. No file present → empty overrides → active() == defaults exactly
# --------------------------------------------------------------------------- #

def test_no_file_load_overrides_empty(rc):
    assert not rc._overrides_path().exists()
    assert rc.load_overrides() == {}


def test_no_file_active_equals_defaults(rc):
    snap = rc.active()
    # Every UPPERCASE primitive constant in core.config must match on the snapshot.
    for k, v in vars(config).items():
        if k != k.upper() or k.startswith("_"):
            continue
        if not isinstance(v, (int, float, str, bool)):
            continue
        assert getattr(snap, k) == v, k


def test_no_file_specific_defaults(rc):
    snap = rc.active()
    assert snap.DYNAMIC_RANGE_BLOCKING_DB == config.DYNAMIC_RANGE_BLOCKING_DB
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS
    assert snap.LUFS_CLUB_MIN == config.LUFS_CLUB_MIN
    assert snap.SPECTRAL_FAKE_LOSSLESS_RATIO == config.SPECTRAL_FAKE_LOSSLESS_RATIO


# --------------------------------------------------------------------------- #
# 2. File with one override → applied; other attrs unchanged
# --------------------------------------------------------------------------- #

def test_single_override_applied(rc):
    _write(rc._overrides_path(), {"DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    assert rc.load_overrides() == {"DYNAMIC_RANGE_BLOCKING_DB": 3.0}
    snap = rc.active()
    assert snap.DYNAMIC_RANGE_BLOCKING_DB == 3.0


def test_single_override_other_attrs_unchanged(rc):
    _write(rc._overrides_path(), {"DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    snap = rc.active()
    # Sampling of unrelated attributes must still equal core.config defaults.
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS
    assert snap.LUFS_CLUB_MIN == config.LUFS_CLUB_MIN
    assert snap.LUFS_CLUB_MAX == config.LUFS_CLUB_MAX
    assert snap.SPECTRAL_FAKE_LOSSLESS_RATIO == config.SPECTRAL_FAKE_LOSSLESS_RATIO
    assert snap.NOISE_FLOOR_MARGINAL_DBFS == config.NOISE_FLOOR_MARGINAL_DBFS


# --------------------------------------------------------------------------- #
# 3. Type coercion → repr stability (the config_hash invariant)
# --------------------------------------------------------------------------- #

def test_int_default_stays_int(rc):
    # CLIP_BLOCKING_EVENTS default is an int (20). JSON 25 must coerce to int.
    assert isinstance(config.CLIP_BLOCKING_EVENTS, int)
    _write(rc._overrides_path(), {"CLIP_BLOCKING_EVENTS": 25})
    overrides = rc.load_overrides()
    val = overrides["CLIP_BLOCKING_EVENTS"]
    assert isinstance(val, int)
    assert not isinstance(val, bool)
    assert val == 25
    assert repr(val) == "25"
    assert isinstance(rc.active().CLIP_BLOCKING_EVENTS, int)


def test_float_default_coerces_int_to_float(rc):
    # LUFS_CLUB_MIN default is a float (-18.0). JSON -20 (int) must coerce to float.
    assert isinstance(config.LUFS_CLUB_MIN, float)
    _write(rc._overrides_path(), {"LUFS_CLUB_MIN": -20})
    overrides = rc.load_overrides()
    val = overrides["LUFS_CLUB_MIN"]
    assert isinstance(val, float)
    assert val == -20.0
    assert repr(val) == "-20.0"
    assert isinstance(rc.active().LUFS_CLUB_MIN, float)
    assert rc.active().LUFS_CLUB_MIN == -20.0


# --------------------------------------------------------------------------- #
# 3b. Regression: valid JSON dict, NON-coercible values per key.
# Previously type(default)(value) raised ValueError/TypeError outside the
# guard and crashed load_overrides(). Source now drops bad values per-key.
# --------------------------------------------------------------------------- #

def test_non_coercible_values_dropped_not_raised(rc):
    # int default fed a non-numeric string; float default fed a list.
    _write(rc._overrides_path(),
           {"CLIP_BLOCKING_EVENTS": "abc", "LUFS_CLUB_MIN": [1, 2]})
    assert rc.load_overrides() == {}            # both bad keys dropped
    snap = rc.active()
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS
    assert snap.LUFS_CLUB_MIN == config.LUFS_CLUB_MIN


@pytest.mark.parametrize("bad_value", ["abc", [1, 2], None, {"nested": 1}])
def test_each_non_coercible_kind_dropped(rc, bad_value):
    # CLIP_BLOCKING_EVENTS is an int default; none of these coerce cleanly.
    _write(rc._overrides_path(), {"CLIP_BLOCKING_EVENTS": bad_value})
    assert rc.load_overrides() == {}
    assert rc.active().CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS


def test_bad_value_does_not_block_good_key(rc):
    # A bad key alongside a coercible one: only the good override survives.
    _write(rc._overrides_path(),
           {"CLIP_BLOCKING_EVENTS": "abc", "DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    assert rc.load_overrides() == {"DYNAMIC_RANGE_BLOCKING_DB": 3.0}
    snap = rc.active()
    assert snap.DYNAMIC_RANGE_BLOCKING_DB == 3.0
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS


# --------------------------------------------------------------------------- #
# 4. Unknown key in file is ignored
# --------------------------------------------------------------------------- #

def test_unknown_key_ignored(rc):
    _write(rc._overrides_path(), {"BOGUS": 1, "DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    overrides = rc.load_overrides()
    assert "BOGUS" not in overrides
    assert overrides == {"DYNAMIC_RANGE_BLOCKING_DB": 3.0}
    assert not hasattr(rc.active(), "BOGUS")


# --------------------------------------------------------------------------- #
# 5. Corrupt / empty / non-dict JSON → {} with no exception
# --------------------------------------------------------------------------- #

def test_corrupt_json_returns_empty(rc):
    _write(rc._overrides_path(), "{not valid json,,,")
    assert rc.load_overrides() == {}


def test_empty_file_returns_empty(rc):
    _write(rc._overrides_path(), "")
    assert rc.load_overrides() == {}


def test_non_dict_json_returns_empty(rc):
    _write(rc._overrides_path(), "[]")
    assert rc.load_overrides() == {}


def test_corrupt_json_active_equals_defaults(rc):
    _write(rc._overrides_path(), "garbage{{{")
    snap = rc.active()
    assert snap.DYNAMIC_RANGE_BLOCKING_DB == config.DYNAMIC_RANGE_BLOCKING_DB
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS


# --------------------------------------------------------------------------- #
# 6. set_overrides() injects in-process; reset() re-reads the file
# --------------------------------------------------------------------------- #

def test_set_overrides_reflected_without_disk(rc):
    assert not rc._overrides_path().exists()      # no file at all
    rc.set_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 2.5})
    assert rc.active().DYNAMIC_RANGE_BLOCKING_DB == 2.5
    # other attrs still defaults
    assert rc.active().CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS


def test_reset_re_reads_file_and_drops_injection(rc):
    # File on disk carries one value...
    _write(rc._overrides_path(), {"CLIP_BLOCKING_EVENTS": 5})
    # ...but we inject a different in-process override.
    rc.set_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 2.5})
    snap = rc.active()
    assert snap.DYNAMIC_RANGE_BLOCKING_DB == 2.5
    # injected snapshot does NOT see the disk file value
    assert snap.CLIP_BLOCKING_EVENTS == config.CLIP_BLOCKING_EVENTS

    rc.reset()
    snap2 = rc.active()
    # injection gone; disk file now applied
    assert snap2.DYNAMIC_RANGE_BLOCKING_DB == config.DYNAMIC_RANGE_BLOCKING_DB
    assert snap2.CLIP_BLOCKING_EVENTS == 5


def test_active_is_cached(rc):
    first = rc.active()
    second = rc.active()
    assert first is second            # same cached snapshot within process
    rc.reset()
    third = rc.active()
    assert third is not first          # rebuilt after reset
