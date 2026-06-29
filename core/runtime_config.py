"""Runtime config overlay: thresholds.json over core.config defaults (T-1)."""

import json
from pathlib import Path
from types import SimpleNamespace

import core.config as _config

_CACHE: SimpleNamespace | None = None   # process-lifetime snapshot
_injected: dict | None = None           # in-process overrides (test hook)


def _overrides_path() -> Path:          # monkeypatched by tests
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "BeatOrDelete"
        / "thresholds.json"
    )


def _defaults() -> dict:                 # UPPERCASE primitive constants only
    return {
        k: v
        for k, v in vars(_config).items()
        if k == k.upper()
        and not k.startswith("_")
        and isinstance(v, (int, float, str, bool))
    }


def _coerce(overrides: dict) -> dict:
    """Keep only known keys; coerce each value to type(default) for repr stability."""
    defaults = _defaults()
    out = {}
    for k, v in overrides.items():
        if k not in defaults:
            continue
        try:
            out[k] = type(defaults[k])(v)
        except (ValueError, TypeError):
            continue
    return out


def load_overrides() -> dict:
    """Read overrides file → coerced/filtered {NAME: value}. Never raises. Not cached."""
    try:
        raw = _overrides_path().read_text()
        data = json.loads(raw)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _coerce(data)


def active() -> SimpleNamespace:
    """Cached snapshot: defaults overlaid with overrides (injected or file)."""
    global _CACHE
    if _CACHE is None:
        merged = _defaults()
        if _injected is not None:
            merged.update(_injected)
        else:
            merged.update(load_overrides())
        _CACHE = SimpleNamespace(**merged)
    return _CACHE


def set_overrides(d: dict) -> None:
    """Test hook: inject overrides in-process without touching disk; busts cache."""
    global _injected, _CACHE
    _injected = _coerce(d)
    _CACHE = None


def reset() -> None:
    """Test hook: clear injection + cache → next active() re-reads file."""
    global _injected, _CACHE
    _injected = None
    _CACHE = None
