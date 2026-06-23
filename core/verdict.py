def compute_verdict(meta: dict, spectral: dict, integrity: dict, loudness: dict, vinyl: dict | None = None) -> dict:
    flags = []
    reasons = []

    # --- Authenticity flags ---
    if meta["lame_header"]:
        flags.append("LAME_CONFIRMED")

    sv = spectral["spectral_verdict"]
    is_lossy = meta["codec"] in ("mp3", "aac", "vorbis", "opus")
    bitrate = meta["bitrate"]

    if is_lossy:
        # For declared lossy files, check if bitrate claim matches spectral reality
        if sv in ("FAKE_LOSSLESS", "SUSPECT"):
            if bitrate >= 310000:  # claims 320kbps
                flags.append("FAKE_320")
                reasons.append(
                    f"declared 320kbps but spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                    f"— actual quality matches {spectral['suspected_origin']}"
                )
            elif bitrate >= 190000:  # claims ~192kbps but looks lower
                flags.append("LOW_QUALITY_MP3")
                reasons.append(
                    f"spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                    f"({spectral['coverage_ratio']*100:.1f}% of Nyquist) — "
                    f"quality below declared bitrate"
                )
    else:
        # Lossless container — spectral cutoff means it was transcoded from lossy
        if sv == "FAKE_LOSSLESS":
            flags.append("FAKE_LOSSLESS")
            reasons.append(
                f"lossless container but spectral ceiling at {spectral['top_freq_hz']:.0f}Hz "
                f"({spectral['coverage_ratio']*100:.1f}% of Nyquist) — "
                f"transcoded from: {spectral['suspected_origin']}"
            )
        elif sv == "SUSPECT":
            flags.append("SUSPECT_LOSSLESS")
            reasons.append(
                f"spectral coverage only {spectral['coverage_ratio']*100:.1f}% of Nyquist — "
                f"possible lossy transcode"
            )
        if sv in ("FAKE_LOSSLESS", "SUSPECT"):
            flags.append("UPSAMPLED")

    # Fake 24-bit
    if meta["bit_depth"] == 24 and integrity["lsb_zero_ratio"] > 0.95:
        flags.append("FAKE_24BIT")
        reasons.append("declared 24-bit but LSBs are all zero — likely upsampled from 16-bit")

    # --- Playability flags ---
    total_clips = integrity["clipped_samples_L"] + integrity["clipped_samples_R"]
    if total_clips > 10:
        flags.append("CLIPPING")
        reasons.append(f"{total_clips} clipped samples detected")
    elif total_clips > 3:
        flags.append("MINOR_CLIPPING")

    if integrity["dynamic_range_db"] > 0:
        if integrity["dynamic_range_db"] < 4:
            flags.append("OVER_COMPRESSED")
            reasons.append(f"dynamic range {integrity['dynamic_range_db']}dB — severely over-compressed")
        elif integrity["dynamic_range_db"] < 6:
            flags.append("LOW_DYNAMIC_RANGE")

    if integrity["noise_floor_dbfs"] > -45:
        flags.append("HIGH_NOISE_FLOOR")
        reasons.append(f"noise floor at {integrity['noise_floor_dbfs']}dBFS — audible hiss at club volume")

    dc_threshold = 0.005
    if abs(integrity["dc_offset_L"]) > dc_threshold or abs(integrity["dc_offset_R"]) > dc_threshold:
        flags.append("DC_OFFSET")

    # --- Vinyl flags ---
    if vinyl and vinyl.get("vinyl_rip"):
        flags.append("VINYL_RIP")
        grade = vinyl.get("vinyl_grade", "")
        wf = vinyl.get("wow_flutter_wrms")
        hum = vinyl.get("hum_hz")
        if wf and wf > 0.15:
            flags.append("WOW_FLUTTER")
            reasons.append(f"wow & flutter {wf:.3f}% WRMS — pitch instability")
        if hum:
            flags.append("HUM")
            reasons.append(f"{hum:.0f}Hz hum detected — grounding issue during rip")
        if grade == "POOR":
            reasons.append("vinyl rip quality: POOR — multiple issues detected")
        elif grade == "ACCEPTABLE":
            reasons.append("vinyl rip: acceptable quality with minor issues")

    if loudness["true_peak_L_dbfs"] > -0.03 or loudness["true_peak_R_dbfs"] > -0.03:
        flags.append("PEAK_HOT")
        reasons.append("sample peak at 0dBFS — gain headroom is gone")

    # --- Determine verdict tier ---
    blocking = {"FAKE_LOSSLESS", "FAKE_320", "CLIPPING", "OVER_COMPRESSED"}
    marginal = {"SUSPECT_LOSSLESS", "LOW_QUALITY_MP3", "UPSAMPLED", "MINOR_CLIPPING", "LOW_DYNAMIC_RANGE", "HIGH_NOISE_FLOOR", "LAME_CONFIRMED", "FAKE_24BIT", "VINYL_RIP", "WOW_FLUTTER", "HUM"}

    flag_set = set(flags)

    if flag_set & blocking:
        verdict = "DO NOT PLAY"
    elif flag_set & marginal:
        verdict = "MARGINAL"
    elif loudness["loudness_lufs"] < -18 or loudness["loudness_lufs"] > -6:
        verdict = "CASUAL OK"
        reasons.append(f"loudness {loudness['loudness_lufs']} LUFS — may need gain adjustment")
    else:
        verdict = "CLUB READY"

    return {
        "verdict": verdict,
        "flags": flags,
        "reasons": reasons,
    }
