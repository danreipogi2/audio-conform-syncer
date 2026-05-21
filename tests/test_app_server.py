from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tempfile import TemporaryDirectory

from audio_conform_syncer.app.server import classify_media_path, save_uploaded_media_parts


class AppServerTests(unittest.TestCase):
    def test_classify_media_path_detects_video_and_audio(self) -> None:
        self.assertEqual(classify_media_path("camera-a/scene.mov"), "video")
        self.assertEqual(classify_media_path("recorder/take_01.WAV"), "audio")
        self.assertEqual(classify_media_path("notes.txt"), "unknown")

    def test_save_uploaded_media_parts_keeps_first_video_and_all_audio(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = save_uploaded_media_parts(
                [
                    {"filename": "edit.mov", "content": b"video-a"},
                    {"filename": "extra.mp4", "content": b"video-b"},
                    {"filename": "boom.wav", "content": b"audio-a"},
                    {"filename": "lav.m4a", "content": b"audio-b"},
                    {"filename": "notes.txt", "content": b"notes"},
                ],
                video_dir=root / "video",
                audio_dir=root / "audio",
            )

        self.assertEqual(media.selected_video.name, "edit.mov")
        self.assertEqual([path.name for path in media.audio_files], ["boom.wav", "lav.m4a"])
        self.assertEqual(media.unsupported_files, ["notes.txt"])
        self.assertTrue(any("Ignored extra video file" in warning for warning in media.warnings))
        self.assertTrue(any("Unsupported files skipped" in warning for warning in media.warnings))


if __name__ == "__main__":
    unittest.main()
