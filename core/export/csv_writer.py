import csv
from pathlib import Path


HEADERS = [
    "filename", "verdict", "flags",
    "container", "codec", "sample_rate", "bit_depth", "bitrate_kbps", "duration_s", "channels",
    "lame_header", "spectral_coverage_ratio", "top_freq_hz", "spectral_verdict", "suspected_origin",
    "clipped_samples_L", "clipped_samples_R", "peak_dbfs",
    "loudness_lufs", "true_peak_L_dbfs", "true_peak_R_dbfs",
    "dynamic_range_db", "noise_floor_dbfs", "dc_offset_L", "dc_offset_R",
    "verdict_reasons",
]


def write_csv(results: list[dict], output_path: str) -> str:
    out = Path(output_path)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            if "error" in r:
                writer.writerow({"filename": r.get("filename", "?"), "verdict": "ERROR", "flags": r["error"]})
                continue
            row = {
                "filename": r["filename"],
                "verdict": r["verdict"],
                "flags": " | ".join(r["flags"]),
                "verdict_reasons": " | ".join(r["verdict_reasons"]),
                **r["format"],
                "bitrate_kbps": round(r["format"]["bitrate"] / 1000, 1),
                **r["authenticity"],
                **r["playability"],
            }
            writer.writerow(row)
    return str(out)
