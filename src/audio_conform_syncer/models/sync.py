from __future__ import annotations

from dataclasses import dataclass
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
