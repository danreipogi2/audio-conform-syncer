from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from audio_conform_syncer.core.audio_features import best_alignment, peak_normalize, rms_energy
from audio_conform_syncer.core.timeline import build_unmatched_regions, merge_matches
from audio_conform_syncer.exports.reporting import write_json_report
from audio_conform_syncer.media.ffmpeg_tools import extract_reference_audio, load_audio_mono
from audio_conform_syncer.models import AudioSummary, MatchCandidate, SyncReport

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


def run_conform(
    video_path: Path,
    audio_dir: Path,
    output_path: Path,
    work_dir: Path,
    settings: MatchSettings | None = None,
) -> SyncReport:
    settings = settings or MatchSettings()
    _validate_settings(settings)

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


def _validate_settings(settings: MatchSettings) -> None:
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
