from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TimeRange:
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


@dataclass(frozen=True)
class MatchCandidate:
    source_path: str
    reference_start_seconds: float
    reference_end_seconds: float
    source_start_seconds: float
    source_end_seconds: float
    score: float
    score_margin: float = 0.0
    confidence: str = "unknown"


@dataclass(frozen=True)
class AudioSummary:
    path: str
    sample_rate: int
    sample_count: int
    duration_seconds: float

    @classmethod
    def from_samples(cls, path: Path, samples: np.ndarray, sample_rate: int) -> "AudioSummary":
        sample_count = int(len(samples))
        duration = sample_count / sample_rate if sample_rate else 0.0
        return cls(
            path=str(path),
            sample_rate=int(sample_rate),
            sample_count=sample_count,
            duration_seconds=duration,
        )


@dataclass(frozen=True)
class ReportSummary:
    source_count: int
    match_count: int
    unmatched_region_count: int
    reference_duration_seconds: float
    matched_duration_seconds: float
    unmatched_duration_seconds: float
    coverage_percent: float
    average_match_score: float
    highest_match_score: float
    ambiguous_match_count: int


@dataclass(frozen=True)
class DiagnosticNote:
    level: str
    message: str


@dataclass(frozen=True)
class SyncReport:
    tool_name: str
    author: str
    created_at_utc: str
    reference_media: str
    audio_directory: str
    reference_audio: AudioSummary
    source_audio: list[AudioSummary]
    settings: dict[str, Any]
    matches: list[MatchCandidate]
    unmatched_regions: list[TimeRange]
    summary: ReportSummary = field(
        default_factory=lambda: ReportSummary(
            source_count=0,
            match_count=0,
            unmatched_region_count=0,
            reference_duration_seconds=0.0,
            matched_duration_seconds=0.0,
            unmatched_duration_seconds=0.0,
            coverage_percent=0.0,
            average_match_score=0.0,
            highest_match_score=0.0,
            ambiguous_match_count=0,
        )
    )
    diagnostics: list[DiagnosticNote] = field(default_factory=list)
    schema_version: str = "1.0"
