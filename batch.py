#!/usr/bin/env python3
"""
Usage:
  python batch.py <folder_or_file> [--output report]

Outputs: report.csv + report.pdf in the same dir as the input (or cwd).
"""
import os
import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

from core.cache import get_or_analyze
from core.export.csv_writer import write_csv
from core.export.pdf_writer import write_pdf
from core.utils import numpy_to_native

SUPPORTED = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg"}


def collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED else []
    return sorted(
        f for f in path.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED
    )


def run_batch(input_path: str, output_stem: str | None = None) -> dict:
    p = Path(input_path)
    files = collect_files(p)

    if not files:
        print(f"No supported audio files found in: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(files)} file(s)...", file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = {pool.submit(get_or_analyze, str(f)): f for f in files}
        for i, future in enumerate(as_completed(futures), 1):
            f = futures[future]
            try:
                result = future.result()
            except Exception as e:
                result = {"filename": f.name, "error": str(e)}
            results.append(result)
            verdict = result.get("verdict", "ERROR")
            flags = " ".join(result.get("flags", []))
            print(f"  [{i}/{len(files)}] {f.name} → {verdict} {flags}", file=sys.stderr)

    # Sort: DO NOT PLAY first, then REVIEW, CLUB READY
    order = {"DO NOT PLAY": 0, "REVIEW": 1, "CLUB READY": 2, "ERROR": 3}
    results.sort(key=lambda r: order.get(r.get("verdict", "ERROR"), 9))

    # Determine output stem
    base = Path(output_stem) if output_stem else (p.parent if p.is_file() else p) / "report"

    csv_path = write_csv(results, str(base) + ".csv")
    pdf_path = write_pdf(results, str(base) + ".pdf")

    print(f"\nCSV → {csv_path}", file=sys.stderr)
    print(f"PDF → {pdf_path}", file=sys.stderr)

    return {"files": len(results), "csv": csv_path, "pdf": pdf_path, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DJ Audio Quality Batch Analyzer")
    parser.add_argument("input", help="Audio file or folder to analyze")
    parser.add_argument("--output", help="Output path stem (without extension)", default=None)
    parser.add_argument("--json", action="store_true", help="Print full results JSON to stdout")
    args = parser.parse_args()

    summary = run_batch(args.input, args.output)

    if args.json:
        print(json.dumps(summary["results"], indent=2, default=numpy_to_native))
    else:
        print(f"\nDone. {summary['files']} files analyzed.", file=sys.stderr)
