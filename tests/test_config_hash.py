"""RED tests for T-1: core/config_hash.py (does not exist yet)."""

import hashlib
import importlib
import re

import pytest

import core.config as config


@pytest.fixture
def mod():
    """Import (or re-import) the config_hash module under test."""
    import core.config_hash as config_hash
    return importlib.reload(config_hash)


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
