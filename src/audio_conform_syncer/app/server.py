from __future__ import annotations

import json
import mimetypes
import re
import time
import uuid
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from audio_conform_syncer import __version__
from audio_conform_syncer.core.matcher import MatchSettings, run_conform, validate_settings
from audio_conform_syncer.exports.media_export import export_synced_video
from audio_conform_syncer.exports.reporting import write_markdown_report
from audio_conform_syncer.exports.timeline_model import (
    build_timeline_project,
    timeline_project_to_dict,
)
from audio_conform_syncer.exports.xml_export import export_premiere_xml, export_resolve_xml
from audio_conform_syncer.media.ffmpeg_tools import FFmpegError, ffmpeg_version

VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".mxf",
    ".webm",
}

AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".wave",
}


@dataclass(frozen=True)
class UploadedMedia:
    selected_video: Path
    audio_files: list[Path]
    unsupported_files: list[str]
    warnings: list[str]


def run_app(host: str = "127.0.0.1", port: int = 8765) -> int:
    server = ThreadingHTTPServer((host, port), SyncAppHandler)
    print(f"Audio Conform Syncer app running at http://{host}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Audio Conform Syncer app.")
    finally:
        server.server_close()
    return 0


def main() -> int:
    return run_app()


def classify_media_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
    return "unknown"


class SyncAppHandler(BaseHTTPRequestHandler):
    server_version = "AudioConformSyncer/0.1"

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send_static("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/static/app.css":
            self._send_static("app.css", "text/css; charset=utf-8")
            return
        if self.path == "/static/app.js":
            self._send_static("app.js", "text/javascript; charset=utf-8")
            return
        if self.path == "/api/health":
            self._send_json(self._health_payload())
            return
        if self.path.startswith("/jobs/"):
            self._send_job_file()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/sync":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._handle_sync_upload()
        except Exception as error:  # pragma: no cover - endpoint safety net
            self._send_json({"ok": False, "error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(payload)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _handle_sync_upload(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        boundary = _extract_boundary(content_type)
        if not boundary:
            raise ValueError("missing multipart boundary")

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("empty upload")

        parts = _parse_multipart(self.rfile.read(content_length), boundary)
        fields: dict[str, str] = {}
        files = []
        for part in parts:
            if part["filename"] is None:
                fields[part["name"]] = part["content"].decode("utf-8", errors="replace")
            elif part["name"] == "files":
                files.append(part)

        settings = _settings_from_fields(fields)
        validate_settings(settings)

        job_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        job_root = Path(".audio-conform-syncer") / "ui_jobs" / job_id
        video_dir = job_root / "input" / "video"
        audio_dir = job_root / "input" / "audio"
        output_dir = job_root / "outputs"
        work_dir = job_root / "work"
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_videos: list[Path] = []
        uploaded_media = save_uploaded_media_parts(files, video_dir=video_dir, audio_dir=audio_dir)
        saved_videos.append(uploaded_media.selected_video)

        if not uploaded_media.audio_files:
            raise ValueError("drop at least one supported audio file")

        report_path = output_dir / "sync_report.json"
        markdown_path = output_dir / "sync_report.md"
        synced_video_path = output_dir / "synced_video.mp4"
        premiere_xml_path = output_dir / "premiere_sync.xml"
        resolve_xml_path = output_dir / "resolve_sync.xml"

        report = run_conform(
            video_path=uploaded_media.selected_video,
            audio_dir=audio_dir,
            output_path=report_path,
            work_dir=work_dir,
            settings=settings,
        )
        write_markdown_report(report, markdown_path)

        output_urls = {
            "json": _job_url(job_id, "outputs/sync_report.json"),
            "markdown": _job_url(job_id, "outputs/sync_report.md"),
            "synced_video": "",
            "premiere_xml": "",
            "resolve_xml": "",
        }

        export_status = {"ok": True, "error": ""}
        try:
            export_synced_video(
                report,
                output_video=synced_video_path,
                work_dir=work_dir / "export",
            )
            output_urls["synced_video"] = _job_url(job_id, "outputs/synced_video.mp4")
        except (FFmpegError, OSError, ValueError) as error:
            export_status = {"ok": False, "error": str(error)}

        xml_status = {
            "premiere": {"ok": False, "error": "", "url": ""},
            "resolve": {"ok": False, "error": "", "url": ""},
        }
        if report.matches:
            xml_project = build_timeline_project(
                report,
                job_id=job_id,
                warnings=uploaded_media.warnings,
                include_waveforms=False,
            )
            try:
                export_premiere_xml(xml_project, premiere_xml_path)
                output_urls["premiere_xml"] = _job_url(job_id, "outputs/premiere_sync.xml")
                xml_status["premiere"] = {
                    "ok": True,
                    "error": "",
                    "url": output_urls["premiere_xml"],
                }
            except Exception as error:
                xml_status["premiere"]["error"] = str(error)

            try:
                export_resolve_xml(xml_project, resolve_xml_path)
                output_urls["resolve_xml"] = _job_url(job_id, "outputs/resolve_sync.xml")
                xml_status["resolve"] = {
                    "ok": True,
                    "error": "",
                    "url": output_urls["resolve_xml"],
                }
            except Exception as error:
                xml_status["resolve"]["error"] = str(error)
        else:
            reason = "XML export needs at least one synced region."
            xml_status["premiere"]["error"] = reason
            xml_status["resolve"]["error"] = reason

        timeline_project = build_timeline_project(
            report,
            job_id=job_id,
            warnings=uploaded_media.warnings,
            export_paths=output_urls,
        )

        return {
            "ok": True,
            "job_id": job_id,
            "video_count": len(saved_videos),
            "audio_count": len(uploaded_media.audio_files),
            "unsupported": uploaded_media.unsupported_files,
            "warnings": uploaded_media.warnings,
            "summary": asdict(report.summary),
            "diagnostics": [asdict(item) for item in report.diagnostics],
            "matches": [asdict(item) for item in report.matches],
            "outputs": output_urls,
            "export": export_status,
            "xml_exports": xml_status,
            "timeline": timeline_project_to_dict(timeline_project),
        }

    def _send_static(self, filename: str, content_type: str) -> None:
        static_root = Path(__file__).with_name("static")
        path = static_root / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_bytes(path.read_bytes(), content_type)

    def _send_job_file(self) -> None:
        relative = unquote(self.path.removeprefix("/jobs/"))
        safe_parts = [part for part in Path(relative).parts if part not in {"", ".", ".."}]
        if not safe_parts:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = Path(".audio-conform-syncer") / "ui_jobs" / Path(*safe_parts)
        try:
            resolved = path.resolve()
            root = (Path(".audio-conform-syncer") / "ui_jobs").resolve()
            if root not in resolved.parents:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send_bytes(path.read_bytes(), content_type)

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        self._send_bytes(
            json.dumps(payload, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            status=status,
        )

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: int = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _health_payload(self) -> dict[str, Any]:
        try:
            ffmpeg = {"ok": True, "detail": ffmpeg_version()}
        except FFmpegError as error:
            ffmpeg = {"ok": False, "detail": str(error)}
        return {"ok": True, "version": __version__, "ffmpeg": ffmpeg}


def _settings_from_fields(fields: dict[str, str]) -> MatchSettings:
    return MatchSettings(
        sample_rate=int(fields.get("sample_rate", "16000")),
        window_seconds=float(fields.get("window_seconds", "1.0")),
        hop_seconds=float(fields.get("hop_seconds", "0.5")),
        threshold=float(fields.get("threshold", "0.5")),
        merge_gap_seconds=float(fields.get("merge_gap_seconds", "0.75")),
        minimum_score_margin=float(fields.get("minimum_score_margin", "0.0")),
    )


def save_uploaded_media_parts(
    files: list[dict[str, Any]],
    video_dir: Path,
    audio_dir: Path,
) -> UploadedMedia:
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    selected_video: Path | None = None
    audio_files: list[Path] = []
    unsupported_files: list[str] = []
    warnings: list[str] = []
    seen_names: dict[str, int] = {}

    for part in files:
        original_name = str(part.get("filename") or "media")
        media_type = classify_media_path(original_name)
        if media_type == "unknown":
            unsupported_files.append(original_name)
            continue

        if media_type == "video" and selected_video is not None:
            warnings.append(f"Ignored extra video file: {original_name}")
            continue

        safe_name = _unique_name(_safe_filename(original_name), seen_names)
        destination = (video_dir if media_type == "video" else audio_dir) / safe_name
        destination.write_bytes(part["content"])

        if media_type == "video":
            selected_video = destination
        else:
            audio_files.append(destination)

    if selected_video is None:
        raise ValueError("drop exactly one video file; found 0")
    if unsupported_files:
        warnings.append(f"Unsupported files skipped: {len(unsupported_files)}")

    return UploadedMedia(
        selected_video=selected_video,
        audio_files=audio_files,
        unsupported_files=unsupported_files,
        warnings=warnings,
    )


def _extract_boundary(content_type: str) -> bytes | None:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        return None
    boundary = match.group("boundary").strip().strip('"')
    return boundary.encode("utf-8")


def _parse_multipart(body: bytes, boundary: bytes) -> list[dict[str, Any]]:
    delimiter = b"--" + boundary
    parts: list[dict[str, Any]] = []
    for raw_part in body.split(delimiter):
        if not raw_part or raw_part in {b"--", b"--\r\n"}:
            continue
        if raw_part.startswith(b"\r\n"):
            raw_part = raw_part[2:]
        if raw_part.endswith(b"--"):
            raw_part = raw_part[:-2]
        if raw_part.endswith(b"\r\n"):
            raw_part = raw_part[:-2]
        if b"\r\n\r\n" not in raw_part:
            continue
        header_blob, content = raw_part.split(b"\r\n\r\n", 1)
        headers = _parse_part_headers(header_blob)
        disposition = headers.get("content-disposition", "")
        name = _extract_disposition_value(disposition, "name")
        filename = _extract_disposition_value(disposition, "filename")
        if not name:
            continue
        parts.append({"name": name, "filename": filename, "content": content})
    return parts


def _parse_part_headers(header_blob: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_blob.decode("latin-1").split("\r\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _extract_disposition_value(disposition: str, key: str) -> str | None:
    match = re.search(rf'{re.escape(key)}="(?P<value>[^"]*)"', disposition)
    if match:
        return match.group("value")
    return None


def _safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned or "media"


def _unique_name(filename: str, seen_names: dict[str, int]) -> str:
    count = seen_names.get(filename, 0)
    seen_names[filename] = count + 1
    if count == 0:
        return filename
    path = Path(filename)
    return f"{path.stem}-{count}{path.suffix}"


def _job_url(job_id: str, relative_path: str) -> str:
    safe_relative = relative_path.replace("\\", "/")
    return f"/jobs/{job_id}/{safe_relative}"


if __name__ == "__main__":
    raise SystemExit(main())
