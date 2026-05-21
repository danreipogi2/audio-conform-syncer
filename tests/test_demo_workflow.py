from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.core.matcher import MatchSettings, run_conform
from scripts.create_demo_media import generate_demo_media


class DemoWorkflowTests(unittest.TestCase):
    def test_generated_demo_media_runs_through_matcher_without_ffmpeg(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = generate_demo_media(root / "demo_media", create_video=False)
            video_path = media.output_dir / "edited_cut.mp4"
            video_path.write_bytes(b"placeholder")

            def fake_extract_reference_audio(video_path: Path, output_wav: Path, sample_rate: int) -> None:
                shutil.copyfile(media.guide_wav, output_wav)

            with patch(
                "audio_conform_syncer.core.matcher.extract_reference_audio",
                side_effect=fake_extract_reference_audio,
            ):
                report = run_conform(
                    video_path=video_path,
                    audio_dir=media.clean_audio_dir,
                    output_path=media.output_dir / "sync_report.json",
                    work_dir=media.output_dir / "work",
                    settings=MatchSettings(
                        sample_rate=16000,
                        window_seconds=1.0,
                        hop_seconds=0.5,
                        threshold=0.6,
                        merge_gap_seconds=0.5,
                    ),
                )

        self.assertEqual(report.summary.source_count, 2)
        self.assertGreaterEqual(report.summary.match_count, 2)
        self.assertGreater(report.summary.coverage_percent, 50.0)
        self.assertTrue({item.confidence for item in report.matches})


if __name__ == "__main__":
    unittest.main()
