from __future__ import annotations

import io
import sys
import unittest
from http import HTTPStatus
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tempfile import TemporaryDirectory

from audio_conform_syncer.app import server as app_server
from audio_conform_syncer.app.job_log import append_job_log, read_job_log
from audio_conform_syncer.app.server import SyncAppHandler, classify_media_path, save_uploaded_media_parts
from audio_conform_syncer.exports.reporting import write_json_report
from audio_conform_syncer.models import (
    AudioSummary,
    DiagnosticNote,
    MatchCandidate,
    ReportSummary,
    SyncReport,
)


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

    def test_job_log_round_trips_timestamped_events(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_job_log(root, "info", "Files received", {"count": 3})
            append_job_log(root, "success", "Sync complete")

            events = read_job_log(root)

        self.assertEqual([event.message for event in events], ["Files received", "Sync complete"])
        self.assertEqual(events[0].details, {"count": 3})
        self.assertTrue(events[0].timestamp)

    def test_sync_upload_returns_job_logs_timeline_and_deferred_xml_exports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_jobs_root = app_server.JOBS_ROOT
            original_run_conform = app_server.run_conform
            original_export_synced_video = app_server.export_synced_video
            app_server.JOBS_ROOT = root / "ui_jobs"
            app_server.run_conform = _fake_run_conform
            app_server.export_synced_video = _fake_export_synced_video
            try:
                handler = object.__new__(SyncAppHandler)
                body, boundary = _multipart_body(
                    [
                        ("files", "edit.mov", b"video"),
                        ("files", "boom.wav", b"audio-a"),
                        ("files", "lav.wav", b"audio-b"),
                        ("files", "notes.txt", b"notes"),
                    ]
                )
                handler.headers = {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(body)),
                }
                handler.rfile = io.BytesIO(body)

                payload = handler._handle_sync_upload()
            finally:
                app_server.JOBS_ROOT = original_jobs_root
                app_server.run_conform = original_run_conform
                app_server.export_synced_video = original_export_synced_video

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["audio_count"], 2)
        self.assertEqual(payload["unsupported"], ["notes.txt"])
        self.assertEqual(payload["outputs"]["premiere_xml"], "")
        self.assertEqual(payload["xml_exports"]["premiere"]["ok"], False)
        self.assertTrue(payload["outputs"]["synced_video"].endswith("synced_video.mp4"))
        self.assertEqual(len(payload["timeline"]["audio_tracks"]), 2)
        self.assertEqual(payload["timeline"]["audio_tracks"][1]["status"], "unmatched")
        messages = [event["message"] for event in payload["logs"]]
        self.assertIn("Files received", messages)
        self.assertIn("Extracting guide audio", messages)
        self.assertIn("Running correlation matching", messages)
        self.assertIn("Writing JSON report", messages)
        self.assertIn("Building timeline model", messages)
        self.assertIn("Sync complete", messages)

    def test_xml_export_endpoint_requires_completed_sync(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "20260521-120000-abcdef12"
            original_jobs_root = app_server.JOBS_ROOT
            app_server.JOBS_ROOT = root / "ui_jobs"
            try:
                job_root = app_server.JOBS_ROOT / job_id
                app_server._write_job_manifest(job_root, {"job_id": job_id, "status": "syncing"})
                handler, sent = _handler_with_json_capture()

                handler._handle_xml_export(job_id, "premiere")
                self.assertFalse(
                    (root / "ui_jobs" / job_id / "outputs" / "premiere_sync.xml").exists()
                )
            finally:
                app_server.JOBS_ROOT = original_jobs_root

        self.assertEqual(sent["status"], HTTPStatus.CONFLICT)
        self.assertFalse(sent["payload"]["ok"])

    def test_xml_export_endpoint_writes_inside_job_output_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "20260521-120000-abcdef12"
            original_jobs_root = app_server.JOBS_ROOT
            app_server.JOBS_ROOT = root / "ui_jobs"
            try:
                job_root = app_server.JOBS_ROOT / job_id
                report = _fake_report(
                    video_path=job_root / "input" / "video" / "edit.mov",
                    source_paths=[
                        job_root / "input" / "audio" / "boom.wav",
                        job_root / "input" / "audio" / "lav.wav",
                    ],
                )
                (job_root / "outputs").mkdir(parents=True, exist_ok=True)
                write_json_report(report, job_root / "outputs" / "sync_report.json")
                app_server._write_job_manifest(
                    job_root,
                    {
                        "job_id": job_id,
                        "status": "synced",
                        "warnings": [],
                        "outputs": {"premiere_xml": "", "resolve_xml": ""},
                        "xml_exports": {},
                    },
                )
                handler, sent = _handler_with_json_capture()

                handler._handle_xml_export(job_id, "premiere")
                xml_path = root / "ui_jobs" / job_id / "outputs" / "premiere_sync.xml"
                self.assertTrue(xml_path.exists())
            finally:
                app_server.JOBS_ROOT = original_jobs_root

        self.assertEqual(sent["status"], HTTPStatus.OK)
        self.assertTrue(sent["payload"]["ok"])
        self.assertIn(f"/jobs/{job_id}/outputs/premiere_sync.xml", sent["payload"]["url"])


def _multipart_body(files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "----AudioConformSyncerTest"
    chunks: list[bytes] = []
    for name, filename, content in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                b"Content-Type: application/octet-stream\r\n\r\n",
                content,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def _fake_run_conform(
    video_path: Path,
    audio_dir: Path,
    output_path: Path,
    work_dir: Path,
    settings,
    event_callback=None,
) -> SyncReport:
    del work_dir, settings
    source_paths = sorted(audio_dir.glob("*.wav"))
    for message in [
        "Extracting guide audio",
        "Decoding source audio",
        "Running correlation matching",
        "Merging adjacent matches",
        "Writing JSON report",
    ]:
        if event_callback:
            event_callback("info", message, {})
    report = _fake_report(video_path=video_path, source_paths=source_paths)
    write_json_report(report, output_path)
    return report


def _fake_export_synced_video(report: SyncReport, output_video: Path, work_dir: Path) -> Path:
    del report, work_dir
    output_video.parent.mkdir(parents=True, exist_ok=True)
    output_video.write_bytes(b"mp4")
    return output_video


def _fake_report(video_path: Path, source_paths: list[Path]) -> SyncReport:
    first_source = source_paths[0]
    return SyncReport(
        tool_name="Audio Conform Syncer",
        author="@danreipogi",
        created_at_utc="2026-05-21T00:00:00+00:00",
        reference_media=str(video_path.resolve()),
        audio_directory=str(first_source.parent.resolve()),
        reference_audio=AudioSummary(
            path=str((video_path.parent / "guide.wav").resolve()),
            sample_rate=16000,
            sample_count=160000,
            duration_seconds=10.0,
        ),
        source_audio=[
            AudioSummary(str(source_path.resolve()), 16000, 80000, 5.0)
            for source_path in source_paths
        ],
        settings={"sample_rate": 16000},
        matches=[
            MatchCandidate(
                source_path=str(first_source.resolve()),
                reference_start_seconds=1.0,
                reference_end_seconds=3.0,
                source_start_seconds=0.5,
                source_end_seconds=2.5,
                score=0.92,
                score_margin=0.2,
                confidence="high",
            )
        ],
        unmatched_regions=[],
        summary=ReportSummary(
            source_count=len(source_paths),
            match_count=1,
            unmatched_region_count=0,
            reference_duration_seconds=10.0,
            matched_duration_seconds=2.0,
            unmatched_duration_seconds=8.0,
            coverage_percent=20.0,
            average_match_score=0.92,
            highest_match_score=0.92,
            ambiguous_match_count=0,
        ),
        diagnostics=[DiagnosticNote("info", "No matching diagnostics were raised.")],
    )


def _handler_with_json_capture():
    handler = object.__new__(SyncAppHandler)
    sent = {}

    def send_json(payload, status=HTTPStatus.OK):
        sent["payload"] = payload
        sent["status"] = status

    def send_error(status):
        sent["error"] = status

    handler._send_json = send_json
    handler.send_error = send_error
    return handler, sent


if __name__ == "__main__":
    unittest.main()
