from __future__ import annotations

import shutil
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.core.matcher import MatchSettings, run_conform


class ConformWorkflowTests(unittest.TestCase):
    def test_run_conform_writes_report_with_matches(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "clean_audio"
            source_dir.mkdir()

            source_samples = _sine(440.0, seconds=4.0)
            reference_samples = np.concatenate(
                [
                    np.zeros(4000, dtype=np.float32),
                    source_samples[8000:24000],
                    np.zeros(4000, dtype=np.float32),
                ]
            )

            source_path = source_dir / "source.wav"
            reference_input = root / "edited_cut.mp4"
            extracted_reference = root / "reference.wav"
            source_path.write_bytes(b"placeholder")
            reference_input.write_bytes(b"placeholder")
            _write_wav(source_path, source_samples)
            _write_wav(extracted_reference, reference_samples)

            def fake_extract_reference_audio(video_path: Path, output_wav: Path, sample_rate: int) -> None:
                shutil.copyfile(extracted_reference, output_wav)

            with patch(
                "audio_conform_syncer.core.matcher.extract_reference_audio",
                side_effect=fake_extract_reference_audio,
            ):
                report = run_conform(
                    video_path=reference_input,
                    audio_dir=source_dir,
                    output_path=root / "sync_report.json",
                    work_dir=root / "work",
                    settings=MatchSettings(
                        sample_rate=8000,
                        window_seconds=1.0,
                        hop_seconds=0.5,
                        threshold=0.9,
                        merge_gap_seconds=0.5,
                    ),
                )

            self.assertTrue((root / "sync_report.json").exists())
            self.assertGreaterEqual(len(report.matches), 1)
            self.assertEqual(report.matches[0].source_path, str(source_path.resolve()))


def _sine(frequency: float, seconds: float, sample_rate: int = 8000) -> np.ndarray:
    index = np.arange(int(seconds * sample_rate), dtype=np.float32)
    return (0.8 * np.sin(2.0 * np.pi * frequency * index / sample_rate)).astype(np.float32)


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        values = np.clip(samples, -1.0, 1.0)
        pcm = (values * 32767).astype("<i2")
        wav_file.writeframes(pcm.tobytes())


if __name__ == "__main__":
    unittest.main()
