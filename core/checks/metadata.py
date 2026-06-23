import json
import subprocess
from pathlib import Path


def run_ffprobe(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def check_lame_header(path: str) -> bool:
    with open(path, "rb") as f:
        raw = f.read(500)
    return b"LAME" in raw or b"Info" in raw


def get_metadata(path: str) -> dict:
    probe = run_ffprobe(path)
    audio = next((s for s in probe["streams"] if s["codec_type"] == "audio"), {})
    fmt = probe.get("format", {})

    container = fmt.get("format_name", "unknown")
    codec = audio.get("codec_name", "unknown")
    sample_rate = int(audio.get("sample_rate", 0))
    bit_depth = int(audio.get("bits_per_sample") or audio.get("bits_per_raw_sample") or 0)
    bitrate = int(audio.get("bit_rate") or fmt.get("bit_rate") or 0)
    duration = float(fmt.get("duration") or audio.get("duration") or 0)
    channels = int(audio.get("channels", 2))
    tags = fmt.get("tags", {})

    # Normalize bit depth for PCM codecs
    if bit_depth == 0:
        if "s16" in codec:
            bit_depth = 16
        elif "s24" in codec or "s32" in codec:
            bit_depth = 24

    lame = check_lame_header(path)

    return {
        "container": container,
        "codec": codec,
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "bitrate": bitrate,
        "duration": round(duration, 2),
        "channels": channels,
        "tags": tags,
        "lame_header": lame,
    }
