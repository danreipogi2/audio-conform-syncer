from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.core.timeline import build_unmatched_regions, merge_matches, merge_time_ranges
from audio_conform_syncer.models import MatchCandidate, TimeRange


class MergeTests(unittest.TestCase):
    def test_merge_time_ranges_combines_overlaps_and_small_gaps(self) -> None:
        ranges = [
            TimeRange(0.0, 1.0),
            TimeRange(1.2, 2.0),
            TimeRange(4.0, 5.0),
        ]

        merged = merge_time_ranges(ranges, gap_tolerance_seconds=0.25)

        self.assertEqual(merged, [TimeRange(0.0, 2.0), TimeRange(4.0, 5.0)])

    def test_merge_matches_combines_adjacent_matches_from_same_source(self) -> None:
        matches = [
            MatchCandidate("a.wav", 0.0, 4.0, 10.0, 14.0, 0.9),
            MatchCandidate("a.wav", 4.2, 8.0, 14.2, 18.0, 0.8),
            MatchCandidate("b.wav", 9.0, 12.0, 2.0, 5.0, 0.95),
        ]

        merged = merge_matches(matches, gap_tolerance_seconds=0.5)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].source_path, "a.wav")
        self.assertAlmostEqual(merged[0].reference_start_seconds, 0.0)
        self.assertAlmostEqual(merged[0].reference_end_seconds, 8.0)

    def test_build_unmatched_regions_finds_gaps(self) -> None:
        matches = [
            MatchCandidate("a.wav", 1.0, 2.0, 4.0, 5.0, 0.9),
            MatchCandidate("a.wav", 3.0, 4.0, 6.0, 7.0, 0.9),
        ]

        unmatched = build_unmatched_regions(5.0, matches)

        self.assertEqual(
            unmatched,
            [TimeRange(0.0, 1.0), TimeRange(2.0, 3.0), TimeRange(4.0, 5.0)],
        )


if __name__ == "__main__":
    unittest.main()
