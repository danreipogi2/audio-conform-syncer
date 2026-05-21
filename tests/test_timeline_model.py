from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.exports.timeline_model import (
    build_timeline_project,
    timeline_project_to_dict,
    waveform_peaks_for_samples,
)
from audio_conform_syncer.models import AudioSummary, MatchCandidate, ReportSummary, SyncReport


class TimelineModelTests(unittest.TestCase):
    def test_timeline_project_marks_matched_and_unmatched_audio_tracks(self) -> None:
        report = _report_with_two_sources()

        project = build_timeline_project(
            report,
            job_id="job-1",
            warnings=["Ignored extra video file: alt.mov"],
            include_waveforms=False,
        )
        data = timeline_project_to_dict(project)

        self.assertEqual(data["job_id"], "job-1")
        self.assertEqual(data["video_track"]["kind"], "video")
        self.assertEqual(data["guide_audio_track"]["kind"], "guide_audio")
        self.assertEqual(len(data["audio_tracks"]), 2)
        self.assertEqual(data["audio_tracks"][0]["status"], "matched")
        self.assertEqual(data["audio_tracks"][1]["status"], "unmatched")
        self.assertEqual(data["guide_audio_track"]["sample_rate"], 16000)
        self.assertEqual(data["audio_tracks"][0]["sample_rate"], 16000)
        self.assertEqual(data["audio_tracks"][0]["clips"][0]["timeline_in_seconds"], 1.0)
        self.assertFalse(data["audio_tracks"][0]["clips"][0]["low_confidence"])

    def test_timeline_project_flags_low_confidence_regions(self) -> None:
        report = _report_with_two_sources(confidence="low", score=0.62)

        project = build_timeline_project(report, job_id="job-low", include_waveforms=False)
        data = timeline_project_to_dict(project)

        self.assertTrue(data["audio_tracks"][0]["clips"][0]["low_confidence"])

    def test_waveform_peaks_are_normalized(self) -> None:
        peaks = waveform_peaks_for_samples([0.0, 0.5, -0.5, 1.0], bars=2)

        self.assertEqual(peaks, [0.5, 1.0])


def _report_with_two_sources(confidence: str = "high", score: float = 0.91) -> SyncReport:
    source_a = str(Path("source-a.wav").resolve())
    source_b = str(Path("source-b.wav").resolve())
    return SyncReport(
        tool_name="Audio Conform Syncer",
        author="@danreipogi",
        created_at_utc="2026-05-21T00:00:00+00:00",
        reference_media=str(Path("edit.mov").resolve()),
        audio_directory=str(Path(".").resolve()),
        reference_audio=AudioSummary(
            path=str(Path("guide.wav").resolve()),
            sample_rate=16000,
            sample_count=160000,
            duration_seconds=10.0,
        ),
        source_audio=[
            AudioSummary(source_a, 16000, 80000, 5.0),
            AudioSummary(source_b, 16000, 80000, 5.0),
        ],
        settings={"sample_rate": 16000},
        matches=[
            MatchCandidate(
                source_path=source_a,
                reference_start_seconds=1.0,
                reference_end_seconds=3.0,
                source_start_seconds=0.5,
                source_end_seconds=2.5,
                score=score,
                score_margin=0.2,
                confidence=confidence,
            )
        ],
        unmatched_regions=[],
        summary=ReportSummary(
            source_count=2,
            match_count=1,
            unmatched_region_count=0,
            reference_duration_seconds=10.0,
            matched_duration_seconds=2.0,
            unmatched_duration_seconds=8.0,
            coverage_percent=20.0,
            average_match_score=score,
            highest_match_score=score,
            ambiguous_match_count=0,
        ),
    )


if __name__ == "__main__":
    unittest.main()
