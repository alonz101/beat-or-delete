from core.checks.flags import compute_flags
from core.config import LUFS_CLUB_MIN, LUFS_CLUB_MAX

BLOCKING = {"FAKE_LOSSLESS", "FAKE_320", "CLIPPING", "OVER_COMPRESSED"}
MARGINAL = {
    "SUSPECT_LOSSLESS", "LOW_QUALITY_MP3", "UPSAMPLED", "MINOR_CLIPPING",
    "LOW_DYNAMIC_RANGE", "HIGH_NOISE_FLOOR", "LAME_CONFIRMED", "FAKE_24BIT",
    "VINYL_RIP", "WOW_FLUTTER", "HUM",
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
    elif loudness["loudness_lufs"] < LUFS_CLUB_MIN or loudness["loudness_lufs"] > LUFS_CLUB_MAX:
        verdict = "CASUAL OK"
        reasons.append(f"loudness {loudness['loudness_lufs']} LUFS — may need gain adjustment")
    else:
        verdict = "CLUB READY"

    return {"verdict": verdict, "flags": flags, "reasons": reasons}
