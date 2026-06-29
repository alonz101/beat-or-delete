"""Deterministic hash of analyzer config constants + active overrides (T-2)."""

import hashlib

import core.config as _config
import core.runtime_config as _rc


def compute_config_hash() -> str:
    values = {
        k: v
        for k, v in vars(_config).items()
        if k == k.upper()
        and not k.startswith("_")
        and isinstance(v, (int, float, str, bool))
    }
    values.update(
        {k: v for k, v in _rc.load_overrides().items() if k in values}
    )
    items = sorted(f"{k}={v!r}" for k, v in values.items())
    return hashlib.sha256("\n".join(items).encode()).hexdigest()


CONFIG_HASH: str = compute_config_hash()
