from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from audio_conform_syncer.models import MatchCandidate, SyncReport, TimeRange


def report_to_dict(report: SyncReport) -> dict[str, Any]:
    return asdict(report)


def write_json_report(report: SyncReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report_to_dict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def render_markdown_report(report: SyncReport) -> str:
    lines = [
        "# Audio Conform Syncer Report",
        "",
        f"Tool: {report.tool_name}",
        f"Author: {report.author}",
        f"Created UTC: {report.created_at_utc}",
        f"Reference media: `{report.reference_media}`",
        f"Audio directory: `{report.audio_directory}`",
        "",
        "## Summary",
        "",
        f"- Sources scanned: {report.summary.source_count}",
        f"- Matches: {report.summary.match_count}",
        f"- Unmatched regions: {report.summary.unmatched_region_count}",
        f"- Coverage: {report.summary.coverage_percent:.1f}%",
        f"- Average score: {report.summary.average_match_score:.3f}",
        f"- Sample rate: {report.settings.get('sample_rate')} Hz",
        f"- Threshold: {report.settings.get('threshold')}",
        "",
    ]

    lines.extend(_render_diagnostics(report))
    lines.extend(_render_matches(report.matches))
    lines.extend(_render_unmatched(report.unmatched_regions))
    return "\n".join(lines) + "\n"


def write_markdown_report(report: SyncReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def _render_matches(matches: list[MatchCandidate]) -> list[str]:
    lines = ["## Matches", ""]
    if not matches:
        lines.extend(["No matches found.", ""])
        return lines

    lines.extend(
        [
            "| Reference | Source | Score | Margin | Confidence | File |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for item in matches:
        lines.append(
            "| "
            f"{_format_range(item.reference_start_seconds, item.reference_end_seconds)} | "
            f"{_format_range(item.source_start_seconds, item.source_end_seconds)} | "
            f"{item.score:.3f} | "
            f"{item.score_margin:.3f} | "
            f"{item.confidence} | "
            f"`{item.source_path}` |"
        )
    lines.append("")
    return lines


def _render_diagnostics(report: SyncReport) -> list[str]:
    lines = ["## Diagnostics", ""]
    for note in report.diagnostics:
        lines.append(f"- {note.level}: {note.message}")
    lines.append("")
    return lines


def _render_unmatched(ranges: list[TimeRange]) -> list[str]:
    lines = ["## Unmatched Reference Regions", ""]
    if not ranges:
        lines.extend(["No unmatched reference regions.", ""])
        return lines

    for item in ranges:
        lines.append(f"- {_format_range(item.start_seconds, item.end_seconds)}")
    lines.append("")
    return lines


def _format_range(start: float, end: float) -> str:
    return f"{_format_seconds(start)} - {_format_seconds(end)}"


def _format_seconds(value: float) -> str:
    minutes, seconds = divmod(max(0.0, value), 60.0)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    return f"{minutes:02d}:{seconds:06.3f}"
