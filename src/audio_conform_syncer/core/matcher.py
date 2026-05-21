from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from audio_conform_syncer.core.audio_features import best_alignment, peak_normalize, rms_energy
from audio_conform_syncer.core.timeline import build_unmatched_regions, merge_matches, merge_time_ranges
from audio_conform_syncer.exports.reporting import write_json_report
from audio_conform_syncer.media.ffmpeg_tools import extract_reference_audio, load_audio_mono
from audio_conform_syncer.models import (
    AudioSummary,
    DiagnosticNote,
    MatchCandidate,
    ReportSummary,
    SyncReport,
    TimeRange,
)

SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".wave",
}


@dataclass(frozen=True)
class MatchSettings:
    sample_rate: int = 16000
    window_seconds: float = 12.0
    hop_seconds: float = 4.0
    threshold: float = 0.55
    merge_gap_seconds: float = 0.75
    offset_tolerance_seconds: float = 1.0
    minimum_energy: float = 1e-4
    minimum_score_margin: float = 0.0


def run_conform(
    video_path: Path,
    audio_dir: Path,
    output_path: Path,
    work_dir: Path,
    settings: MatchSettings | None = None,
) -> SyncReport:
    settings = settings or MatchSettings()
    validate_settings(settings)

    video_path = video_path.expanduser().resolve()
    audio_dir = audio_dir.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    work_dir = work_dir.expanduser().resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"video not found: {video_path}")
    if not audio_dir.exists() or not audio_dir.is_dir():
        raise FileNotFoundError(f"audio directory not found: {audio_dir}")

    work_dir.mkdir(parents=True, exist_ok=True)
    reference_wav = work_dir / "reference_guide.wav"
    extract_reference_audio(video_path, reference_wav, sample_rate=settings.sample_rate)

    reference_samples, reference_rate = load_audio_mono(
        reference_wav,
        sample_rate=settings.sample_rate,
        work_dir=work_dir,
    )
    reference_samples = peak_normalize(reference_samples)

    source_files = discover_audio_files(audio_dir)
    if not source_files:
        raise FileNotFoundError(f"no supported audio files found in: {audio_dir}")

    sources: list[tuple[Path, np.ndarray, AudioSummary]] = []
    for source_file in source_files:
        samples, sample_rate = load_audio_mono(
            source_file,
            sample_rate=settings.sample_rate,
            work_dir=work_dir / "decoded_sources",
        )
        normalized = peak_normalize(samples)
        sources.append(
            (
                source_file,
                normalized,
                AudioSummary.from_samples(source_file, normalized, sample_rate),
            )
        )

    matches = find_matches(reference_samples, sources, settings)
    merged_matches = merge_matches(
        matches,
        gap_tolerance_seconds=settings.merge_gap_seconds,
        offset_tolerance_seconds=settings.offset_tolerance_seconds,
    )
    unmatched_regions = build_unmatched_regions(
        duration_seconds=len(reference_samples) / reference_rate,
        matches=merged_matches,
        gap_tolerance_seconds=settings.merge_gap_seconds,
    )
    reference_duration_seconds = len(reference_samples) / reference_rate
    summary = build_report_summary(
        reference_duration_seconds=reference_duration_seconds,
        matches=merged_matches,
        unmatched_regions=unmatched_regions,
        source_count=len(sources),
    )
    diagnostics = build_diagnostics(summary=summary, settings=settings)

    report = SyncReport(
        tool_name="Audio Conform Syncer",
        author="@danreipogi",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        reference_media=str(video_path),
        audio_directory=str(audio_dir),
        reference_audio=AudioSummary.from_samples(reference_wav, reference_samples, reference_rate),
        source_audio=[source for _, _, source in sources],
        settings=asdict(settings),
        matches=merged_matches,
        unmatched_regions=unmatched_regions,
        summary=summary,
        diagnostics=diagnostics,
    )
    write_json_report(report, output_path)
    return report


def discover_audio_files(audio_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in audio_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )


def find_matches(
    reference_samples: np.ndarray,
    sources: list[tuple[Path, np.ndarray, AudioSummary]],
    settings: MatchSettings,
) -> list[MatchCandidate]:
    matches: list[MatchCandidate] = []
    sample_rate = settings.sample_rate

    for reference_start_sample, window in iter_reference_windows(
        reference_samples,
        sample_rate=sample_rate,
        window_seconds=settings.window_seconds,
        hop_seconds=settings.hop_seconds,
    ):
        if rms_energy(window) < settings.minimum_energy:
            continue

        best_candidate: MatchCandidate | None = None
        for source_path, source_samples, _ in sources:
            alignment = best_alignment(window, source_samples)
            if alignment.score < settings.threshold:
                continue
            if alignment.score_margin < settings.minimum_score_margin:
                continue

            reference_start = reference_start_sample / sample_rate
            reference_end = (reference_start_sample + len(window)) / sample_rate
            source_start = alignment.offset_seconds(sample_rate)
            source_end = source_start + (len(window) / sample_rate)
            candidate = MatchCandidate(
                source_path=str(source_path),
                reference_start_seconds=reference_start,
                reference_end_seconds=reference_end,
                source_start_seconds=source_start,
                source_end_seconds=source_end,
                score=alignment.score,
                score_margin=alignment.score_margin,
                confidence=classify_confidence(
                    score=alignment.score,
                    score_margin=alignment.score_margin,
                    threshold=settings.threshold,
                ),
            )
            if best_candidate is None or candidate.score > best_candidate.score:
                best_candidate = candidate

        if best_candidate is not None:
            matches.append(best_candidate)

    return matches


def iter_reference_windows(
    samples: np.ndarray,
    sample_rate: int,
    window_seconds: float,
    hop_seconds: float,
):
    window_size = max(1, int(round(window_seconds * sample_rate)))
    hop_size = max(1, int(round(hop_seconds * sample_rate)))
    total_samples = len(samples)

    if total_samples == 0:
        return
    if total_samples <= window_size:
        yield 0, samples
        return

    emitted_last = False
    last_start = total_samples - window_size
    for start in range(0, last_start + 1, hop_size):
        emitted_last = start == last_start
        yield start, samples[start : start + window_size]
    if not emitted_last:
        yield last_start, samples[last_start:]


def validate_settings(settings: MatchSettings) -> None:
    if settings.sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if settings.window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    if settings.hop_seconds <= 0:
        raise ValueError("hop_seconds must be positive")
    if not 0.0 <= settings.threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    if settings.merge_gap_seconds < 0:
        raise ValueError("merge_gap_seconds must be zero or positive")
    if settings.offset_tolerance_seconds < 0:
        raise ValueError("offset_tolerance_seconds must be zero or positive")
    if settings.minimum_energy < 0:
        raise ValueError("minimum_energy must be zero or positive")
    if settings.minimum_score_margin < 0:
        raise ValueError("minimum_score_margin must be zero or positive")


_validate_settings = validate_settings


def classify_confidence(score: float, score_margin: float, threshold: float) -> str:
    if score_margin < 0.03:
        return "ambiguous"
    if score >= max(0.85, threshold) and score_margin >= 0.10:
        return "high"
    if score >= max(0.70, threshold) and score_margin >= 0.05:
        return "medium"
    return "low"


def build_report_summary(
    reference_duration_seconds: float,
    matches: list[MatchCandidate],
    unmatched_regions: list[TimeRange],
    source_count: int,
) -> ReportSummary:
    matched_ranges = merge_time_ranges(
        [
            TimeRange(item.reference_start_seconds, item.reference_end_seconds)
            for item in matches
        ]
    )
    matched_duration = sum(item.duration_seconds for item in matched_ranges)
    unmatched_duration = sum(item.duration_seconds for item in unmatched_regions)
    scores = [item.score for item in matches]
    coverage = (
        (matched_duration / reference_duration_seconds) * 100.0
        if reference_duration_seconds > 0.0
        else 0.0
    )

    return ReportSummary(
        source_count=source_count,
        match_count=len(matches),
        unmatched_region_count=len(unmatched_regions),
        reference_duration_seconds=reference_duration_seconds,
        matched_duration_seconds=matched_duration,
        unmatched_duration_seconds=unmatched_duration,
        coverage_percent=coverage,
        average_match_score=(sum(scores) / len(scores)) if scores else 0.0,
        highest_match_score=max(scores) if scores else 0.0,
        ambiguous_match_count=sum(1 for item in matches if item.confidence == "ambiguous"),
    )


def build_diagnostics(
    summary: ReportSummary,
    settings: MatchSettings,
) -> list[DiagnosticNote]:
    diagnostics: list[DiagnosticNote] = []

    if summary.match_count == 0:
        diagnostics.append(
            DiagnosticNote(
                level="warning",
                message=(
                    "No confident matches were found. Try lowering --threshold, using a longer "
                    "--window-seconds value, or checking that the guide audio matches the source files."
                ),
            )
        )
    elif summary.coverage_percent < 50.0:
        diagnostics.append(
            DiagnosticNote(
                level="warning",
                message=(
                    "Less than half of the reference timeline matched clean source audio. Review "
                    "unmatched regions before using this report for conform decisions."
                ),
            )
        )

    if summary.ambiguous_match_count:
        diagnostics.append(
            DiagnosticNote(
                level="info",
                message=(
                    f"{summary.ambiguous_match_count} match region(s) had a close runner-up score. "
                    "Raise --min-score-margin to filter ambiguous repeated audio."
                ),
            )
        )

    if settings.minimum_score_margin > 0.0:
        diagnostics.append(
            DiagnosticNote(
                level="info",
                message=f"Filtered matches with a score margin below {settings.minimum_score_margin:.3f}.",
            )
        )

    if not diagnostics:
        diagnostics.append(
            DiagnosticNote(
                level="info",
                message="No matching diagnostics were raised.",
            )
        )

    return diagnostics
