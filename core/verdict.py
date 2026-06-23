from core.checks.flags import compute_flags

BLOCKING = {"FAKE_LOSSLESS", "FAKE_320", "CLIPPING", "OVER_COMPRESSED"}
MARGINAL = {
    "SUSPECT_LOSSLESS", "LOW_QUALITY_MP3", "MINOR_CLIPPING",
    "LOW_DYNAMIC_RANGE", "HIGH_NOISE_FLOOR", "LAME_CONFIRMED",
    "VINYL_RIP", "HUM",
}


def compute_verdict(
    meta: dict,
    spectral: dict,
    integrity: dict,
    loudness: dict,
    vinyl: dict | None = None,
) -> dict:
    flags, reasons = compute_flags(meta, spectral, integrity, loudness, vinyl)
    flag_set = set(flags)

    if flag_set & BLOCKING:
        verdict = "DO NOT PLAY"
    elif flag_set & MARGINAL:
        verdict = "MARGINAL"
    else:
        verdict = "CLUB READY"

    return {"verdict": verdict, "flags": flags, "reasons": reasons}
