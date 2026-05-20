from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audio_conform_syncer import __version__
from audio_conform_syncer.core.matcher import MatchSettings, run_conform
from audio_conform_syncer.exports.reporting import write_markdown_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-conform-syncer",
        description="Match a flattened edited video guide track against clean source audio files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--video", required=True, help="Path to the flattened edited video.")
    parser.add_argument("--audio-dir", required=True, help="Folder containing clean source audio files.")
    parser.add_argument(
        "--output",
        default="sync_report.json",
        help="Path for the JSON sync report. Defaults to sync_report.json.",
    )
    parser.add_argument(
        "--markdown-output",
        help="Optional path for a human-readable Markdown review summary.",
    )
    parser.add_argument(
        "--work-dir",
        default=".audio-conform-syncer",
        help="Directory for temporary extracted/decoded audio files.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Analysis sample rate in Hz. Defaults to 16000.",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=12.0,
        help="Reference window size used for matching. Defaults to 12.0.",
    )
    parser.add_argument(
        "--hop-seconds",
        type=float,
        default=4.0,
        help="Seconds between reference windows. Defaults to 4.0.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.55,
        help="Minimum normalized correlation score for a match. Defaults to 0.55.",
    )
    parser.add_argument(
        "--merge-gap-seconds",
        type=float,
        default=0.75,
        help="Maximum reference gap to merge adjacent matches. Defaults to 0.75.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = MatchSettings(
        sample_rate=args.sample_rate,
        window_seconds=args.window_seconds,
        hop_seconds=args.hop_seconds,
        threshold=args.threshold,
        merge_gap_seconds=args.merge_gap_seconds,
    )

    try:
        report = run_conform(
            video_path=Path(args.video),
            audio_dir=Path(args.audio_dir),
            output_path=Path(args.output),
            work_dir=Path(args.work_dir),
            settings=settings,
        )
        if args.markdown_output:
            write_markdown_report(report, Path(args.markdown_output))
    except Exception as error:  # pragma: no cover - exercised by real CLI failures
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote sync report: {Path(args.output)}")
    if args.markdown_output:
        print(f"Wrote Markdown summary: {Path(args.markdown_output)}")
    print(f"Matches: {len(report.matches)}")
    print(f"Unmatched regions: {len(report.unmatched_regions)}")
    return 0
