from core.config import (
    BITRATE_320_THRESHOLD,
    BITRATE_192_THRESHOLD,
    LSB_ZERO_RATIO_FAKE_24BIT,
    CLIP_BLOCKING_EVENTS,
    CLIP_MARGINAL_EVENTS,
    CLIP_BLOCKING_MS,
    CLIP_MARGINAL_MS,
    DYNAMIC_RANGE_BLOCKING_DB,
    DYNAMIC_RANGE_MARGINAL_DB,
    NOISE_FLOOR_MARGINAL_DBFS,
    DC_OFFSET_THRESHOLD,
    VINYL_WOW_FLUTTER_FLAG,
    TRUE_PEAK_HOT_DBFS,
    LUFS_CLUB_MIN,
    LUFS_CLUB_MAX,
)


def compute_flags(
    meta: dict,
    spectral: dict,
    integrity: dict,
    loudness: dict,
    vinyl: dict | None = None,
) -> tuple[list[str], list[str], list[str]]:
    flags: list[str] = []
    verdict_reasons: list[str] = []   # drive the verdict color (red)
    info_reasons: list[str] = []      # informational only (yellow)

    # --- Authenticity ---
    if meta["lame_header"]:
        flags.append("LAME_CONFIRMED")

    sv = spectral["spectral_verdict"]
    is_lossy = meta["codec"] in ("mp3", "aac", "vorbis", "opus")
    bitrate = meta["bitrate"]

    if is_lossy:
        if sv in ("FAKE_LOSSLESS", "SUSPECT"):
            if bitrate >= BITRATE_320_THRESHOLD:
                flags.append("FAKE_320")
                verdict_reasons.append(
                    f"declared 320kbps but spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                    f"— actual quality matches {spectral['suspected_origin']}"
                )
            elif bitrate >= BITRATE_192_THRESHOLD:
                flags.append("LOW_QUALITY_MP3")
                verdict_reasons.append(
                    f"spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                    f"({spectral['coverage_ratio']*100:.1f}% of Nyquist) — "
                    f"quality below declared bitrate"
                )
    else:
        if sv == "FAKE_LOSSLESS":
            flags.append("FAKE_LOSSLESS")
            if spectral["suspected_origin"] == "likely genuine lossless":
                origin_text = "possibly sample-rate converted"
            else:
                origin_text = f"transcoded from {spectral['suspected_origin']}"
            verdict_reasons.append(
                f"lossless container but spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                f"({spectral['coverage_ratio']*100:.1f}% of Nyquist) — {origin_text}"
            )
        elif sv == "SUSPECT":
            flags.append("SUSPECT_LOSSLESS")
            verdict_reasons.append(
                f"spectral coverage only {spectral['coverage_ratio']*100:.1f}% of Nyquist — "
                f"possible lossy transcode"
            )

    if meta["bit_depth"] == 24 and integrity["lsb_zero_ratio"] > LSB_ZERO_RATIO_FAKE_24BIT:
        flags.append("FAKE_24BIT")
        info_reasons.append("declared 24-bit but LSBs are all zero — likely upsampled from 16-bit")

    # --- Playability ---
    total_events = integrity["clip_events_L"] + integrity["clip_events_R"]
    max_ms = integrity["clip_max_ms"]
    if total_events > CLIP_BLOCKING_EVENTS or max_ms > CLIP_BLOCKING_MS:
        flags.append("CLIPPING")
        dur = f" — longest {max_ms:.1f}ms" if max_ms >= 1 else ""
        verdict_reasons.append(f"{total_events} clipping event{'s' if total_events != 1 else ''} detected{dur}")
    elif total_events > CLIP_MARGINAL_EVENTS or max_ms > CLIP_MARGINAL_MS:
        flags.append("MINOR_CLIPPING")
        dur = f" — longest {max_ms:.1f}ms" if max_ms >= 1 else ""
        verdict_reasons.append(f"{total_events} minor clipping event{'s' if total_events != 1 else ''}{dur}")

    if integrity["dynamic_range_db"] > 0:
        if integrity["dynamic_range_db"] < DYNAMIC_RANGE_BLOCKING_DB:
            flags.append("OVER_COMPRESSED")
            verdict_reasons.append(f"dynamic range {integrity['dynamic_range_db']}dB — severely over-compressed")
        elif integrity["dynamic_range_db"] < DYNAMIC_RANGE_MARGINAL_DB:
            flags.append("LOW_DYNAMIC_RANGE")

    if integrity["noise_floor_dbfs"] > NOISE_FLOOR_MARGINAL_DBFS:
        flags.append("HIGH_NOISE_FLOOR")
        verdict_reasons.append(f"noise floor at {integrity['noise_floor_dbfs']}dBFS — audible hiss at club volume")

    if abs(integrity["dc_offset_L"]) > DC_OFFSET_THRESHOLD or abs(integrity["dc_offset_R"]) > DC_OFFSET_THRESHOLD:
        flags.append("DC_OFFSET")

    # --- Vinyl ---
    if vinyl and vinyl.get("vinyl_rip"):
        flags.append("VINYL_RIP")
        grade = vinyl.get("vinyl_grade", "")
        wf = vinyl.get("wow_flutter_wrms")
        hum = vinyl.get("hum_hz")
        if wf and wf > VINYL_WOW_FLUTTER_FLAG:
            flags.append("WOW_FLUTTER")
            info_reasons.append(f"estimated wow & flutter {wf:.2f}% (proxy measurement — improving in future version)")
        if hum:
            flags.append("HUM")
            verdict_reasons.append(f"{hum:.0f}Hz hum detected — power line interference during rip")
        if grade == "POOR":
            info_reasons.append("vinyl rip condition: poor — multiple quality issues")

    if loudness["true_peak_L_dbfs"] > TRUE_PEAK_HOT_DBFS or loudness["true_peak_R_dbfs"] > TRUE_PEAK_HOT_DBFS:
        flags.append("PEAK_HOT")
        peak = max(loudness["true_peak_L_dbfs"], loudness["true_peak_R_dbfs"])
        info_reasons.append(f"peak at {peak:.2f} dBFS — headroom tight, ease up on gain when mixing")

    # Loudness informational flags — DJs can compensate with gain; never blocks verdict
    lufs = loudness["loudness_lufs"]
    if lufs < LUFS_CLUB_MIN:
        flags.append("LOUDNESS_LOW")
        info_reasons.append(f"loudness {lufs} LUFS — crank the gain, but watch headroom")
    elif lufs > LUFS_CLUB_MAX:
        flags.append("LOUDNESS_HOT")
        info_reasons.append(f"loudness {lufs} LUFS — louder than typical club master")

    return flags, verdict_reasons, info_reasons
