from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from audio_conform_syncer import __version__
from audio_conform_syncer.core.matcher import (
    MatchSettings,
    discover_audio_files,
    run_conform,
    validate_settings,
)
from audio_conform_syncer.exports.reporting import write_markdown_report
from audio_conform_syncer.media.ffmpeg_tools import FFmpegError, ffmpeg_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-conform-syncer",
        description="Match a flattened edited video guide track against clean source audio files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--video", help="Path to the flattened edited video.")
    parser.add_argument("--audio-dir", help="Folder containing clean source audio files.")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check local runtime dependencies and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and settings without extracting or matching media.",
    )
    parser.add_argument(
        "--app",
        action="store_true",
        help="Launch the local drag-and-drop sync app.",
    )
    parser.add_argument(
        "--app-host",
        default="127.0.0.1",
        help="Host for the local app. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--app-port",
        type=int,
        default=8765,
        help="Port for the local app. Defaults to 8765.",
    )
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
    parser.add_argument(
        "--min-score-margin",
        type=float,
        default=0.0,
        help=(
            "Reject matches whose best score is not this much stronger than the nearest "
            "distinct runner-up. Defaults to 0.0."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.doctor:
        return run_doctor()

    if args.app:
        from audio_conform_syncer.app.server import run_app

        return run_app(host=args.app_host, port=args.app_port)

    if not args.video or not args.audio_dir:
        parser.error("--video and --audio-dir are required unless --doctor or --app is used")

    settings = MatchSettings(
        sample_rate=args.sample_rate,
        window_seconds=args.window_seconds,
        hop_seconds=args.hop_seconds,
        threshold=args.threshold,
        merge_gap_seconds=args.merge_gap_seconds,
        minimum_score_margin=args.min_score_margin,
    )
    try:
        validate_settings(settings)
    except ValueError as error:
        parser.error(str(error))

    if args.dry_run:
        return run_dry_run(Path(args.video), Path(args.audio_dir), settings)

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
    print(f"Coverage: {report.summary.coverage_percent:.1f}%")
    for note in report.diagnostics:
        print(f"{note.level}: {note.message}")
    return 0


def run_doctor() -> int:
    checks: list[tuple[str, bool, str]] = [
        ("Audio Conform Syncer", True, __version__),
        ("Python", True, sys.version.split()[0]),
        ("NumPy", True, np.__version__),
    ]

    try:
        checks.append(("FFmpeg", True, ffmpeg_version()))
    except FFmpegError as error:
        checks.append(("FFmpeg", False, str(error)))

    for name, ok, detail in checks:
        status = "ok" if ok else "missing"
        print(f"{status:7} {name}: {detail}")

    return 0 if all(ok for _, ok, _ in checks) else 1


def run_dry_run(video_path: Path, audio_dir: Path, settings: MatchSettings) -> int:
    try:
        version = ffmpeg_version()
    except FFmpegError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    video_path = video_path.expanduser().resolve()
    audio_dir = audio_dir.expanduser().resolve()
    if not video_path.exists():
        print(f"error: video not found: {video_path}", file=sys.stderr)
        return 1
    if not audio_dir.exists() or not audio_dir.is_dir():
        print(f"error: audio directory not found: {audio_dir}", file=sys.stderr)
        return 1

    source_files = discover_audio_files(audio_dir)
    if not source_files:
        print(f"error: no supported audio files found in: {audio_dir}", file=sys.stderr)
        return 1

    print("Dry run passed.")
    print(f"FFmpeg: {version}")
    print(f"Video: {video_path}")
    print(f"Audio directory: {audio_dir}")
    print(f"Source audio files: {len(source_files)}")
    print("Settings:")
    for key, value in asdict(settings).items():
        print(f"  {key}: {value}")
    return 0
