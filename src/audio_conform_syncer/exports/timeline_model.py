from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from audio_conform_syncer.media.ffmpeg_tools import load_audio_mono
from audio_conform_syncer.models import AudioSummary, MatchCandidate, SyncReport


LOW_CONFIDENCE_LABELS = {"ambiguous", "low", "unknown"}


@dataclass(frozen=True)
class TimelineClip:
    id: str
    source_path: str
    source_name: str
    timeline_in_seconds: float
    timeline_out_seconds: float
    source_in_seconds: float
    source_out_seconds: float
    confidence: str
    score: float
    score_margin: float
    track_index: int

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.timeline_out_seconds - self.timeline_in_seconds)

    @property
    def low_confidence(self) -> bool:
        return self.confidence in LOW_CONFIDENCE_LABELS or self.score < 0.7


@dataclass(frozen=True)
class TimelineTrack:
    id: str
    kind: str
    name: str
    source_path: str
    source_name: str
    duration_seconds: float
    track_index: int
    status: str
    sample_rate: int = 0
    channels: int = 0
    clips: list[TimelineClip] = field(default_factory=list)
    waveform_peaks: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineProject:
    job_id: str
    reference_video_path: str
    reference_video_name: str
    duration_seconds: float
    video_track: TimelineTrack
    guide_audio_track: TimelineTrack
    audio_tracks: list[TimelineTrack]
    warnings: list[str] = field(default_factory=list)
    export_paths: dict[str, str] = field(default_factory=dict)


def build_timeline_project(
    report: SyncReport,
    job_id: str,
    warnings: list[str] | None = None,
    export_paths: dict[str, str] | None = None,
    waveform_bars: int = 80,
    include_waveforms: bool = True,
) -> TimelineProject:
    duration = (
        report.summary.reference_duration_seconds
        or report.reference_audio.duration_seconds
        or _latest_timeline_out(report.matches)
    )
    reference_video = Path(report.reference_media)

    video_track = TimelineTrack(
        id="video-reference",
        kind="video",
        name="Flattened edit / reference video",
        source_path=report.reference_media,
        source_name=reference_video.name,
        duration_seconds=duration,
        track_index=0,
        status="reference",
        clips=[
            TimelineClip(
                id="video-reference-clip",
                source_path=report.reference_media,
                source_name=reference_video.name,
                timeline_in_seconds=0.0,
                timeline_out_seconds=duration,
                source_in_seconds=0.0,
                source_out_seconds=duration,
                confidence="reference",
                score=1.0,
                score_margin=1.0,
                track_index=0,
            )
        ],
    )

    guide_audio_track = TimelineTrack(
        id="audio-guide",
        kind="guide_audio",
        name="Baked-in guide audio",
        source_path=report.reference_audio.path,
        source_name=f"{reference_video.name} guide",
        duration_seconds=duration,
        track_index=1,
        status="reference",
        sample_rate=report.reference_audio.sample_rate,
        waveform_peaks=_safe_waveform_peaks(
            Path(report.reference_audio.path),
            bars=waveform_bars,
            include_waveforms=include_waveforms,
        ),
    )

    matches_by_source = _group_matches_by_source(report.matches)
    audio_tracks: list[TimelineTrack] = []
    for index, source in enumerate(report.source_audio, start=2):
        source_path = str(Path(source.path).resolve())
        source_matches = matches_by_source.get(source_path, [])
        clips = [
            _clip_from_match(match, clip_index=clip_index, track_index=index)
            for clip_index, match in enumerate(source_matches, start=1)
        ]
        audio_tracks.append(
            TimelineTrack(
                id=f"audio-source-{index - 1}",
                kind="external_audio",
                name=Path(source.path).name,
                source_path=source_path,
                source_name=Path(source.path).name,
                duration_seconds=source.duration_seconds,
                track_index=index,
                status="matched" if clips else "unmatched",
                sample_rate=source.sample_rate,
                clips=clips,
                waveform_peaks=_safe_waveform_peaks(
                    Path(source.path),
                    bars=waveform_bars,
                    include_waveforms=include_waveforms,
                ),
            )
        )

    return TimelineProject(
        job_id=job_id,
        reference_video_path=report.reference_media,
        reference_video_name=reference_video.name,
        duration_seconds=duration,
        video_track=video_track,
        guide_audio_track=guide_audio_track,
        audio_tracks=audio_tracks,
        warnings=warnings or [],
        export_paths=export_paths or {},
    )


def timeline_project_to_dict(project: TimelineProject) -> dict[str, Any]:
    data = asdict(project)
    for track in [data["video_track"], data["guide_audio_track"], *data["audio_tracks"]]:
        for clip in track.get("clips", []):
            clip["duration_seconds"] = max(
                0.0,
                clip["timeline_out_seconds"] - clip["timeline_in_seconds"],
            )
            clip["low_confidence"] = (
                clip["confidence"] in LOW_CONFIDENCE_LABELS or clip["score"] < 0.7
            )
    return data


def waveform_peaks_for_samples(samples: np.ndarray, bars: int = 80) -> list[float]:
    if bars <= 0:
        raise ValueError("bars must be positive")

    mono = np.asarray(samples, dtype=np.float32)
    if mono.size == 0:
        return []

    chunks = np.array_split(np.abs(mono), min(bars, mono.size))
    peaks = np.array([float(np.max(chunk)) if chunk.size else 0.0 for chunk in chunks])
    maximum = float(np.max(peaks)) if peaks.size else 0.0
    if maximum <= 0.0:
        return [0.0 for _ in peaks]
    return [round(float(value / maximum), 4) for value in peaks]


def _safe_waveform_peaks(path: Path, bars: int, include_waveforms: bool) -> list[float]:
    if not include_waveforms or not path.exists():
        return []
    try:
        samples, _ = load_audio_mono(path, sample_rate=8000)
    except Exception:
        return []
    return waveform_peaks_for_samples(samples, bars=bars)


def _clip_from_match(match: MatchCandidate, clip_index: int, track_index: int) -> TimelineClip:
    source_path = str(Path(match.source_path).resolve())
    return TimelineClip(
        id=f"track-{track_index}-clip-{clip_index}",
        source_path=source_path,
        source_name=Path(match.source_path).name,
        timeline_in_seconds=match.reference_start_seconds,
        timeline_out_seconds=match.reference_end_seconds,
        source_in_seconds=match.source_start_seconds,
        source_out_seconds=match.source_end_seconds,
        confidence=match.confidence,
        score=match.score,
        score_margin=match.score_margin,
        track_index=track_index,
    )


def _group_matches_by_source(matches: list[MatchCandidate]) -> dict[str, list[MatchCandidate]]:
    grouped: dict[str, list[MatchCandidate]] = {}
    for match in matches:
        source_path = str(Path(match.source_path).resolve())
        grouped.setdefault(source_path, []).append(match)
    for source_matches in grouped.values():
        source_matches.sort(key=lambda item: item.reference_start_seconds)
    return grouped


def _latest_timeline_out(matches: list[MatchCandidate]) -> float:
    if not matches:
        return 0.0
    return max(item.reference_end_seconds for item in matches)
