from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AlignmentResult:
    """Best alignment of a query signal inside a larger target signal."""

    offset_samples: int
    score: float
    runner_up_score: float = 0.0
    score_margin: float = 0.0

    def offset_seconds(self, sample_rate: int) -> float:
        return self.offset_samples / sample_rate


def to_float_mono(samples: np.ndarray) -> np.ndarray:
    """Return a contiguous mono float32 signal."""

    array = np.asarray(samples)
    if array.ndim == 2:
        array = array.mean(axis=1)
    if array.ndim != 1:
        raise ValueError("audio samples must be a mono array or a channels-last 2D array")
    return np.ascontiguousarray(array, dtype=np.float32)


def peak_normalize(samples: np.ndarray) -> np.ndarray:
    mono = to_float_mono(samples)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    if peak <= 0.0:
        return mono
    return mono / peak


def resample_linear(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    """Resample with linear interpolation for lightweight analysis use."""

    mono = to_float_mono(samples)
    if source_rate == target_rate:
        return mono
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive")
    if mono.size == 0:
        return mono

    duration = mono.size / source_rate
    target_size = max(1, int(round(duration * target_rate)))
    source_x = np.linspace(0.0, duration, num=mono.size, endpoint=False)
    target_x = np.linspace(0.0, duration, num=target_size, endpoint=False)
    return np.interp(target_x, source_x, mono).astype(np.float32)


def rms_energy(samples: np.ndarray) -> float:
    mono = to_float_mono(samples)
    if mono.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))


def best_alignment(query: np.ndarray, target: np.ndarray) -> AlignmentResult:
    """Find the strongest normalized correlation of query inside target."""

    query_signal = to_float_mono(query).astype(np.float64)
    target_signal = to_float_mono(target).astype(np.float64)

    if query_signal.size == 0 or target_signal.size == 0:
        return AlignmentResult(offset_samples=0, score=0.0)
    if query_signal.size > target_signal.size:
        return AlignmentResult(offset_samples=0, score=0.0)

    query_signal = query_signal - float(np.mean(query_signal))
    query_norm = float(np.linalg.norm(query_signal))
    if query_norm <= 1e-12:
        return AlignmentResult(offset_samples=0, score=0.0)

    window_size = query_signal.size
    dots = _fft_correlate_valid(target_signal, query_signal)

    window_sums = _sliding_sum(target_signal, window_size)
    window_squares = _sliding_sum(np.square(target_signal), window_size)
    window_variance = window_squares - (np.square(window_sums) / window_size)
    window_variance = np.maximum(window_variance, 0.0)

    denominator = np.sqrt(window_variance) * query_norm
    scores = np.divide(
        dots,
        denominator,
        out=np.zeros_like(dots, dtype=np.float64),
        where=denominator > 1e-12,
    )
    abs_scores = np.abs(scores)
    best_index = int(np.argmax(abs_scores))
    best_score = float(abs_scores[best_index])
    runner_up_score = _runner_up_peak_score(
        abs_scores,
        best_index=best_index,
        exclusion_radius=window_size,
    )
    return AlignmentResult(
        offset_samples=best_index,
        score=best_score,
        runner_up_score=runner_up_score,
        score_margin=max(0.0, best_score - runner_up_score),
    )


def _fft_correlate_valid(target: np.ndarray, query: np.ndarray) -> np.ndarray:
    full_size = target.size + query.size - 1
    fft_size = 1 << (full_size - 1).bit_length()
    target_fft = np.fft.rfft(target, n=fft_size)
    query_fft = np.fft.rfft(query[::-1], n=fft_size)
    full = np.fft.irfft(target_fft * query_fft, n=fft_size)[:full_size]
    return full[query.size - 1 : target.size]


def _sliding_sum(samples: np.ndarray, window_size: int) -> np.ndarray:
    cumulative = np.concatenate(([0.0], np.cumsum(samples, dtype=np.float64)))
    return cumulative[window_size:] - cumulative[:-window_size]


def _runner_up_peak_score(
    scores: np.ndarray,
    best_index: int,
    exclusion_radius: int,
) -> float:
    if scores.size <= 1:
        return 0.0

    masked = scores.copy()
    start = max(0, best_index - exclusion_radius + 1)
    end = min(scores.size, best_index + exclusion_radius)
    masked[start:end] = 0.0
    return float(np.max(masked)) if masked.size else 0.0
