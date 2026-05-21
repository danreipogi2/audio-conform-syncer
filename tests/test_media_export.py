from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.exports.media_export import build_aligned_audio
from audio_conform_syncer.media.ffmpeg_tools import read_wav_mono, write_wav_mono
from audio_conform_syncer.models import AudioSummary, MatchCandidate, ReportSummary, SyncReport


class MediaExportTests(unittest.TestCase):
    def test_build_aligned_audio_places_source_match_on_reference_timeline(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "source.wav"
            sample_rate = 8000
            source_samples = np.linspace(-0.5, 0.5, sample_rate * 3, dtype=np.float32)
            write_wav_mono(source_path, source_samples, sample_rate=sample_rate)

            report = SyncReport(
                tool_name="Audio Conform Syncer",
                author="@danreipogi",
                created_at_utc="2026-05-21T00:00:00+00:00",
                reference_media=str(root / "edited.mp4"),
                audio_directory=str(root),
                reference_audio=AudioSummary(
                    path=str(root / "reference.wav"),
                    sample_rate=sample_rate,
                    sample_count=sample_rate * 3,
                    duration_seconds=3.0,
                ),
                source_audio=[],
                settings={"sample_rate": sample_rate},
                matches=[
                    MatchCandidate(
                        source_path=str(source_path),
                        reference_start_seconds=1.0,
                        reference_end_seconds=2.0,
                        source_start_seconds=0.5,
                        source_end_seconds=1.5,
                        score=0.9,
                        score_margin=0.2,
                        confidence="high",
                    )
                ],
                unmatched_regions=[],
                summary=ReportSummary(
                    source_count=1,
                    match_count=1,
                    unmatched_region_count=0,
                    reference_duration_seconds=3.0,
                    matched_duration_seconds=1.0,
                    unmatched_duration_seconds=2.0,
                    coverage_percent=33.333,
                    average_match_score=0.9,
                    highest_match_score=0.9,
                    ambiguous_match_count=0,
                ),
            )

            output_wav = build_aligned_audio(
                report,
                output_wav=root / "aligned.wav",
                work_dir=root / "work",
                sample_rate=sample_rate,
                use_reference_fallback=False,
            )
            aligned, _ = read_wav_mono(output_wav)

        np.testing.assert_allclose(aligned[:sample_rate], 0.0, atol=1e-4)
        np.testing.assert_allclose(
            aligned[sample_rate : sample_rate * 2],
            source_samples[sample_rate // 2 : sample_rate + sample_rate // 2],
            atol=1e-4,
        )


if __name__ == "__main__":
    unittest.main()
