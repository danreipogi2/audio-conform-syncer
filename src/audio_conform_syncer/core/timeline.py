from __future__ import annotations

from audio_conform_syncer.models import MatchCandidate, TimeRange


def merge_time_ranges(
    ranges: list[TimeRange],
    gap_tolerance_seconds: float = 0.0,
) -> list[TimeRange]:
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda item: (item.start_seconds, item.end_seconds))
    merged: list[TimeRange] = []
    current = sorted_ranges[0]

    for item in sorted_ranges[1:]:
        if item.start_seconds <= current.end_seconds + gap_tolerance_seconds:
            current = TimeRange(
                start_seconds=current.start_seconds,
                end_seconds=max(current.end_seconds, item.end_seconds),
            )
            continue
        merged.append(current)
        current = item

    merged.append(current)
    return merged


def merge_matches(
    matches: list[MatchCandidate],
    gap_tolerance_seconds: float = 0.75,
    offset_tolerance_seconds: float = 1.0,
) -> list[MatchCandidate]:
    if not matches:
        return []

    sorted_matches = sorted(
        matches,
        key=lambda item: (item.source_path, item.reference_start_seconds, item.source_start_seconds),
    )
    merged: list[MatchCandidate] = []
    current = sorted_matches[0]

    for item in sorted_matches[1:]:
        if _can_merge(current, item, gap_tolerance_seconds, offset_tolerance_seconds):
            current = _merge_pair(current, item)
            continue
        merged.append(current)
        current = item

    merged.append(current)
    return sorted(merged, key=lambda item: item.reference_start_seconds)


def build_unmatched_regions(
    duration_seconds: float,
    matches: list[MatchCandidate],
    gap_tolerance_seconds: float = 0.0,
) -> list[TimeRange]:
    matched_ranges = [
        TimeRange(item.reference_start_seconds, item.reference_end_seconds)
        for item in matches
    ]
    merged_ranges = merge_time_ranges(matched_ranges, gap_tolerance_seconds)

    unmatched: list[TimeRange] = []
    cursor = 0.0
    for item in merged_ranges:
        if item.start_seconds > cursor:
            unmatched.append(TimeRange(cursor, item.start_seconds))
        cursor = max(cursor, item.end_seconds)

    if cursor < duration_seconds:
        unmatched.append(TimeRange(cursor, duration_seconds))
    return unmatched


def _can_merge(
    left: MatchCandidate,
    right: MatchCandidate,
    gap_tolerance_seconds: float,
    offset_tolerance_seconds: float,
) -> bool:
    if left.source_path != right.source_path:
        return False
    reference_gap = right.reference_start_seconds - left.reference_end_seconds
    if reference_gap > gap_tolerance_seconds:
        return False

    left_offset = left.source_start_seconds - left.reference_start_seconds
    right_offset = right.source_start_seconds - right.reference_start_seconds
    return abs(left_offset - right_offset) <= offset_tolerance_seconds


def _merge_pair(left: MatchCandidate, right: MatchCandidate) -> MatchCandidate:
    left_duration = max(0.0, left.reference_end_seconds - left.reference_start_seconds)
    right_duration = max(0.0, right.reference_end_seconds - right.reference_start_seconds)
    total_duration = left_duration + right_duration
    if total_duration <= 0:
        score = max(left.score, right.score)
    else:
        score = ((left.score * left_duration) + (right.score * right_duration)) / total_duration

    return MatchCandidate(
        source_path=left.source_path,
        reference_start_seconds=min(left.reference_start_seconds, right.reference_start_seconds),
        reference_end_seconds=max(left.reference_end_seconds, right.reference_end_seconds),
        source_start_seconds=min(left.source_start_seconds, right.source_start_seconds),
        source_end_seconds=max(left.source_end_seconds, right.source_end_seconds),
        score=score,
    )
