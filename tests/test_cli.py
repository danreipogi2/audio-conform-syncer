from __future__ import annotations

import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.cli.main import main


class CliTests(unittest.TestCase):
    def test_doctor_returns_success_when_dependencies_exist(self) -> None:
        with patch("audio_conform_syncer.cli.main.ffmpeg_version", return_value="ffmpeg version test"):
            with redirect_stdout(StringIO()):
                result = main(["--doctor"])

        self.assertEqual(result, 0)

    def test_dry_run_validates_inputs_without_processing_media(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "edited_cut.mp4"
            audio_dir = root / "clean_audio"
            audio_dir.mkdir()
            video.write_bytes(b"placeholder")
            (audio_dir / "source.wav").write_bytes(b"placeholder")

            with patch("audio_conform_syncer.cli.main.ffmpeg_version", return_value="ffmpeg version test"):
                with redirect_stdout(StringIO()):
                    result = main(
                        [
                            "--video",
                            str(video),
                            "--audio-dir",
                            str(audio_dir),
                            "--dry-run",
                        ]
                    )

        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
