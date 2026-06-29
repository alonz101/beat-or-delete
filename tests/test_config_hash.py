"""RED tests for T-1 / T-2: core/config_hash.py."""

import hashlib
import importlib
import re

import pytest

import core.config as config
import core.runtime_config as runtime_config


@pytest.fixture(autouse=True)
def isolate_overrides(tmp_path, monkeypatch):
    """Keep the real ~/Library thresholds.json out of every test.

    Point _overrides_path() at a nonexistent file so no-override == defaults-only,
    and reset runtime_config's in-process cache/injection before and after.
    """
    missing = tmp_path / "thresholds.json"   # does not exist yet
    monkeypatch.setattr(runtime_config, "_overrides_path", lambda: missing)
    runtime_config.reset()
    yield
    runtime_config.reset()


@pytest.fixture
def apply_overrides(tmp_path):
    """Activate overrides through BOTH channels so the test is robust to however
    config_hash reads them: write the real thresholds.json that load_overrides()
    reads, AND call runtime_config.set_overrides() (the in-process test hook)."""
    path = tmp_path / "thresholds.json"   # same path isolate_overrides patches to

    def _apply(d: dict):
        import json
        path.write_text(json.dumps(d))
        runtime_config.set_overrides(d)

    return _apply


@pytest.fixture
def mod():
    """Import (or re-import) the config_hash module under test."""
    import core.config_hash as config_hash
    return importlib.reload(config_hash)


def _reference_hash():
    """Independent reference over UPPERCASE primitive defaults of core.config."""
    parts = []
    for k, v in vars(config).items():
        if k != k.upper() or k.startswith("_"):
            continue
        if not isinstance(v, (int, float, str, bool)):
            continue
        parts.append(f"{k}={v!r}")
    return hashlib.sha256("\n".join(sorted(parts)).encode()).hexdigest()


def test_returns_64_char_lowercase_hex(mod):
    h = mod.compute_config_hash()
    assert isinstance(h, str)
    assert len(h) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", h)


def test_deterministic_across_calls(mod):
    assert mod.compute_config_hash() == mod.compute_config_hash()


def test_module_constant_matches_function(mod):
    assert mod.CONFIG_HASH == mod.compute_config_hash()


def test_matches_independent_reference_computation(mod):
    # Reproduce the contract independently and compare.
    parts = []
    for k, v in vars(config).items():
        if k != k.upper() or k.startswith("_"):
            continue
        if not isinstance(v, (int, float, str, bool)):
            continue
        parts.append(f"{k}={v!r}")
    expected = hashlib.sha256("\n".join(sorted(parts)).encode()).hexdigest()
    assert mod.compute_config_hash() == expected


def test_hash_changes_when_constant_monkeypatched(mod, monkeypatch):
    # DYNAMIC_RANGE_BLOCKING_DB is a known UPPERCASE float constant
    assert hasattr(config, "DYNAMIC_RANGE_BLOCKING_DB")
    before = mod.compute_config_hash()
    monkeypatch.setattr(config, "DYNAMIC_RANGE_BLOCKING_DB",
                        config.DYNAMIC_RANGE_BLOCKING_DB + 1.0)
    after = mod.compute_config_hash()
    assert after != before


def test_non_uppercase_names_excluded(mod, monkeypatch):
    # adding a lowercase/import-style attr must not change the hash
    before = mod.compute_config_hash()
    monkeypatch.setattr(config, "some_lowercase_var", 12345, raising=False)
    monkeypatch.setattr(config, "__dunder_thing__", 999, raising=False)
    assert mod.compute_config_hash() == before


def test_non_primitive_values_excluded_without_error(mod, monkeypatch):
    # adding an UPPERCASE non-primitive must be skipped, no error, no change
    before = mod.compute_config_hash()
    monkeypatch.setattr(config, "SOME_LIST_CONST", [1, 2, 3], raising=False)
    monkeypatch.setattr(config, "SOME_DICT_CONST", {"a": 1}, raising=False)
    assert mod.compute_config_hash() == before


# --- T-2: overrides folded into the hash ---


def test_no_overrides_equals_independent_reference(mod):
    # AC-8: with no overrides active, hash must equal the defaults-only reference.
    assert runtime_config.load_overrides() == {}
    assert mod.compute_config_hash() == _reference_hash()


def test_override_changes_hash(mod, apply_overrides):
    # An active override on a real primitive const must change the hash.
    baseline = mod.compute_config_hash()
    new_val = config.DYNAMIC_RANGE_BLOCKING_DB + 1.0   # 4.0 -> 5.0
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": new_val})
    assert mod.compute_config_hash() != baseline


def test_override_equal_to_default_collapses_to_no_override(mod, apply_overrides):
    # Cache-correctness: a knob set to its default value must NOT create a new hash.
    baseline = mod.compute_config_hash()
    default_val = config.DYNAMIC_RANGE_BLOCKING_DB   # 4.0 (float)
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": default_val})
    assert mod.compute_config_hash() == baseline


def test_override_equal_to_default_int_repr_coercion(mod, apply_overrides):
    # JSON would deliver the float default as e.g. 4 (int); coercion -> 4.0 -> same repr.
    baseline = mod.compute_config_hash()
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 4})  # int, not 4.0
    assert mod.compute_config_hash() == baseline


def test_bogus_key_has_no_effect(mod, apply_overrides):
    # An override on a key that is not a known primitive default must be ignored.
    baseline = mod.compute_config_hash()
    apply_overrides({"BOGUS_NOT_A_CONST": 1})
    assert mod.compute_config_hash() == baseline


def test_two_different_override_sets_differ(mod, apply_overrides):
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    h1 = mod.compute_config_hash()
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 7.0})
    h2 = mod.compute_config_hash()
    assert h1 != h2


def test_same_override_set_is_deterministic(mod, apply_overrides):
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    h1 = mod.compute_config_hash()
    apply_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 3.0})
    h2 = mod.compute_config_hash()
    assert h1 == h2
