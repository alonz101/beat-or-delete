#!/usr/bin/env python3
"""CLI entry point for on-demand full-size annotated spectrogram generation.
Usage: python spectrogram_cli.py <path> [--hum-hz 50.0] [--clip-times 1.2,3.4,5.6]
Output (stdout): {"spectrogram_path": "/tmp/...png"}
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.spectrogram import generate_full


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate full-size annotated spectrogram")
    parser.add_argument("path", help="Audio file path")
    parser.add_argument("--hum-hz", type=float, default=None, help="Hum frequency to annotate (50 or 60)")
    parser.add_argument("--clip-times", type=str, default=None, help="Comma-separated clip timestamps in seconds")
    args = parser.parse_args()

    clip_times = (
        [float(x) for x in args.clip_times.split(",") if x.strip()]
        if args.clip_times else []
    )

    path = generate_full(args.path, hum_hz=args.hum_hz, clip_times_sec=clip_times)
    print(json.dumps({"spectrogram_path": path}))


if __name__ == "__main__":
    main()
