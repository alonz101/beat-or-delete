"""Deterministic hash of analyzer config constants (T-1)."""

import hashlib

import core.config as _config


def compute_config_hash() -> str:
    items = sorted(
        f"{k}={v!r}"
        for k, v in vars(_config).items()
        if k == k.upper()
        and not k.startswith("_")
        and isinstance(v, (int, float, str, bool))
    )
    s = "\n".join(items)
    return hashlib.sha256(s.encode()).hexdigest()


CONFIG_HASH: str = compute_config_hash()
