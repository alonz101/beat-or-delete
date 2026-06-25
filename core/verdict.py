from core.checks.flags import compute_flags

BLOCKING = {"FAKE_LOSSLESS", "CLIPPING", "OVER_COMPRESSED", "LOW_QUALITY_MP3"}
REVIEW = {
    "FAKE_320", "SUSPECT_LOSSLESS", "MINOR_CLIPPING",
    "LOW_DYNAMIC_RANGE", "HIGH_NOISE_FLOOR", "LAME_CONFIRMED", "HUM",
}


def compute_verdict(
    meta: dict,
    spectral: dict,
    integrity: dict,
    loudness: dict,
    vinyl: dict | None = None,
) -> dict:
    flags, verdict_reasons, info_reasons = compute_flags(meta, spectral, integrity, loudness, vinyl)
    flag_set = set(flags)

    if flag_set & BLOCKING:
        verdict = "DO NOT PLAY"
    elif flag_set & REVIEW:
        verdict = "REVIEW"
    else:
        verdict = "CLUB READY"

    return {"verdict": verdict, "flags": flags, "reasons": verdict_reasons, "info_reasons": info_reasons}
