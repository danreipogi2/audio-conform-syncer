from __future__ import annotations

from pathlib import Path

import numpy as np

from audio_conform_syncer.media.ffmpeg_tools import (
    FFmpegError,
    extract_reference_audio,
    load_audio_mono,
    mux_video_with_audio,
    write_wav_mono,
)
from audio_conform_syncer.models import SyncReport


def build_aligned_audio(
    report: SyncReport,
    output_wav: Path,
    work_dir: Path,
    sample_rate: int = 48000,
    use_reference_fallback: bool = True,
) -> Path:
    """Create a timeline WAV with clean source audio placed at matched video times."""

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    work_dir = work_dir.expanduser().resolve()
    output_wav = output_wav.expanduser().resolve()
    duration_seconds = (
        report.summary.reference_duration_seconds
        or report.reference_audio.duration_seconds
        or _latest_match_end(report)
    )
    sample_count = max(1, int(round(duration_seconds * sample_rate)))
    timeline = np.zeros(sample_count, dtype=np.float32)

    if use_reference_fallback:
        reference_wav = work_dir / "export_reference_guide.wav"
        extract_reference_audio(Path(report.reference_media), reference_wav, sample_rate=sample_rate)
        reference_samples, _ = load_audio_mono(
            reference_wav,
            sample_rate=sample_rate,
            work_dir=work_dir / "export_reference_decode",
        )
        timeline[: min(sample_count, len(reference_samples))] = reference_samples[:sample_count]

    source_cache: dict[str, np.ndarray] = {}
    for match in report.matches:
        source_samples = source_cache.get(match.source_path)
        if source_samples is None:
            source_samples, _ = load_audio_mono(
                Path(match.source_path),
                sample_rate=sample_rate,
                work_dir=work_dir / "export_source_decode",
            )
            source_cache[match.source_path] = source_samples

        reference_start = max(0, int(round(match.reference_start_seconds * sample_rate)))
        reference_end = min(sample_count, int(round(match.reference_end_seconds * sample_rate)))
        source_start = max(0, int(round(match.source_start_seconds * sample_rate)))
        source_end = min(len(source_samples), int(round(match.source_end_seconds * sample_rate)))
        copy_count = min(reference_end - reference_start, source_end - source_start)
        if copy_count <= 0:
            continue

        timeline[reference_start : reference_start + copy_count] = source_samples[
            source_start : source_start + copy_count
        ]

    write_wav_mono(output_wav, timeline, sample_rate=sample_rate)
    return output_wav


def export_synced_video(
    report: SyncReport,
    output_video: Path,
    work_dir: Path,
    sample_rate: int = 48000,
) -> Path:
    aligned_wav = output_video.with_suffix(".aligned.wav")
    build_aligned_audio(
        report,
        output_wav=aligned_wav,
        work_dir=work_dir,
        sample_rate=sample_rate,
        use_reference_fallback=True,
    )
    try:
        mux_video_with_audio(Path(report.reference_media), aligned_wav, output_video, copy_video=True)
    except FFmpegError:
        mux_video_with_audio(Path(report.reference_media), aligned_wav, output_video, copy_video=False)
    return output_video


def _latest_match_end(report: SyncReport) -> float:
    if not report.matches:
        return 0.0
    return max(item.reference_end_seconds for item in report.matches)
