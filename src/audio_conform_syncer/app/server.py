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
from audio_conform_syncer.app.job_log import append_job_log, job_logs_to_dicts, read_job_log
from audio_conform_syncer.core.matcher import MatchSettings, run_conform, validate_settings
from audio_conform_syncer.exports.media_export import export_synced_video
from audio_conform_syncer.exports.reporting import report_from_dict, write_markdown_report
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

JOBS_ROOT = Path(".audio-conform-syncer") / "ui_jobs"
JOB_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[a-fA-F0-9]{8}$")


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
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send_static("index.html", "text/html; charset=utf-8")
            return
        if path == "/static/app.css":
            self._send_static("app.css", "text/css; charset=utf-8")
            return
        if path == "/static/app.js":
            self._send_static("app.js", "text/javascript; charset=utf-8")
            return
        if path == "/api/health":
            self._send_json(self._health_payload())
            return
        logs_job_id = _match_logs_api_path(path)
        if logs_job_id:
            self._send_job_logs(logs_job_id)
            return
        if path.startswith("/jobs/"):
            self._send_job_file()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        export_request = _match_export_api_path(path)
        if export_request:
            job_id, target = export_request
            self._handle_xml_export(job_id, target)
            return

        if path != "/api/sync":
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
        job_root = JOBS_ROOT / job_id
        video_dir = job_root / "input" / "video"
        audio_dir = job_root / "input" / "audio"
        output_dir = job_root / "outputs"
        work_dir = job_root / "work"
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        def log_event(
            level: str,
            message: str,
            details: dict[str, Any] | None = None,
        ) -> None:
            append_job_log(job_root, level, message, details)

        append_job_log(job_root, "info", "Job created", {"job_id": job_id})
        append_job_log(job_root, "info", "Files received", {"count": len(files)})

        try:
            uploaded_media = save_uploaded_media_parts(
                files,
                video_dir=video_dir,
                audio_dir=audio_dir,
            )
            append_job_log(
                job_root,
                "info",
                "Video detected",
                {"file": uploaded_media.selected_video.name},
            )
            append_job_log(
                job_root,
                "info",
                "Audio files detected",
                {"count": len(uploaded_media.audio_files)},
            )
            if uploaded_media.unsupported_files:
                append_job_log(
                    job_root,
                    "warning",
                    "Unsupported files ignored",
                    {"files": uploaded_media.unsupported_files},
                )
            for warning in uploaded_media.warnings:
                append_job_log(job_root, "warning", warning)

            if not uploaded_media.audio_files:
                raise ValueError("drop at least one supported audio file")

            output_urls = {
                "json": _job_url(job_id, "outputs/sync_report.json"),
                "markdown": _job_url(job_id, "outputs/sync_report.md"),
                "synced_video": "",
                "premiere_xml": "",
                "resolve_xml": "",
            }
            xml_status = {
                "premiere": {"ok": False, "error": "", "url": ""},
                "resolve": {"ok": False, "error": "", "url": ""},
            }
            _write_job_manifest(
                job_root,
                {
                    "job_id": job_id,
                    "status": "syncing",
                    "warnings": uploaded_media.warnings,
                    "unsupported": uploaded_media.unsupported_files,
                    "outputs": output_urls,
                    "xml_exports": xml_status,
                },
            )

            report_path = output_dir / "sync_report.json"
            markdown_path = output_dir / "sync_report.md"
            synced_video_path = output_dir / "synced_video.mp4"

            report = run_conform(
                video_path=uploaded_media.selected_video,
                audio_dir=audio_dir,
                output_path=report_path,
                work_dir=work_dir,
                settings=settings,
                event_callback=log_event,
            )
            for note in report.diagnostics:
                append_job_log(job_root, note.level, note.message)
            append_job_log(job_root, "info", "Writing Markdown report", {"path": str(markdown_path)})
            write_markdown_report(report, markdown_path)

            export_status = {"ok": True, "error": ""}
            append_job_log(job_root, "info", "Exporting synced MP4")
            try:
                export_synced_video(
                    report,
                    output_video=synced_video_path,
                    work_dir=work_dir / "export",
                )
                output_urls["synced_video"] = _job_url(job_id, "outputs/synced_video.mp4")
                append_job_log(job_root, "success", "Synced MP4 export complete")
            except (FFmpegError, OSError, ValueError) as error:
                export_status = {"ok": False, "error": str(error)}
                append_job_log(job_root, "warning", "Synced MP4 export failed", {"error": str(error)})

            if not report.matches:
                reason = "XML export needs at least one synced region."
                xml_status["premiere"]["error"] = reason
                xml_status["resolve"]["error"] = reason

            append_job_log(job_root, "info", "Building timeline model")
            timeline_project = build_timeline_project(
                report,
                job_id=job_id,
                warnings=uploaded_media.warnings,
                export_paths=output_urls,
            )

            _write_job_manifest(
                job_root,
                {
                    "job_id": job_id,
                    "status": "synced",
                    "warnings": uploaded_media.warnings,
                    "unsupported": uploaded_media.unsupported_files,
                    "outputs": output_urls,
                    "xml_exports": xml_status,
                },
            )
            append_job_log(
                job_root,
                "success",
                "Sync complete",
                {"matches": len(report.matches), "coverage_percent": report.summary.coverage_percent},
            )

            return {
                "ok": True,
                "job_id": job_id,
                "video_count": 1,
                "audio_count": len(uploaded_media.audio_files),
                "unsupported": uploaded_media.unsupported_files,
                "warnings": uploaded_media.warnings,
                "summary": asdict(report.summary),
                "diagnostics": [asdict(item) for item in report.diagnostics],
                "matches": [asdict(item) for item in report.matches],
                "outputs": output_urls,
                "export": export_status,
                "xml_exports": xml_status,
                "logs": job_logs_to_dicts(read_job_log(job_root)),
                "timeline": timeline_project_to_dict(timeline_project),
            }
        except Exception as error:
            append_job_log(job_root, "error", "Error details", {"error": str(error)})
            _write_job_manifest(
                job_root,
                {
                    "job_id": job_id,
                    "status": "error",
                    "error": str(error),
                },
            )
            raise

    def _send_static(self, filename: str, content_type: str) -> None:
        static_root = Path(__file__).with_name("static")
        path = static_root / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_bytes(path.read_bytes(), content_type)

    def _send_job_logs(self, job_id: str) -> None:
        job_root = _validated_job_root(job_id)
        if job_root is None or not job_root.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            {
                "ok": True,
                "job_id": job_id,
                "logs": job_logs_to_dicts(read_job_log(job_root)),
            }
        )

    def _handle_xml_export(self, job_id: str, target: str) -> None:
        job_root = _validated_job_root(job_id)
        if job_root is None or not job_root.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if target == "premiere":
            label = "Premiere XML"
            output_key = "premiere_xml"
            output_name = "premiere_sync.xml"
            export_fn = export_premiere_xml
        elif target == "resolve":
            label = "DaVinci Resolve XML"
            output_key = "resolve_xml"
            output_name = "resolve_sync.xml"
            export_fn = export_resolve_xml
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        manifest = _read_job_manifest(job_root)
        if manifest.get("status") != "synced":
            append_job_log(
                job_root,
                "error",
                f"Exporting {label} failed",
                {"error": "Sync must complete before XML export."},
            )
            self._send_json(
                {
                    "ok": False,
                    "error": "Sync must complete before XML export.",
                    "logs": job_logs_to_dicts(read_job_log(job_root)),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        try:
            report = _read_sync_report(job_root)
        except (OSError, ValueError, KeyError) as error:
            append_job_log(job_root, "error", f"Exporting {label} failed", {"error": str(error)})
            self._send_json(
                {
                    "ok": False,
                    "error": str(error),
                    "logs": job_logs_to_dicts(read_job_log(job_root)),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        if not report.matches:
            error = "XML export needs at least one synced region."
            append_job_log(job_root, "error", f"Exporting {label} failed", {"error": error})
            self._send_json(
                {
                    "ok": False,
                    "error": error,
                    "logs": job_logs_to_dicts(read_job_log(job_root)),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        append_job_log(job_root, "info", f"Exporting {label}")
        try:
            outputs = dict(manifest.get("outputs") or {})
            output_path = _job_output_path(job_root, output_name)
            project = build_timeline_project(
                report,
                job_id=job_id,
                warnings=list(manifest.get("warnings") or []),
                export_paths=outputs,
                include_waveforms=False,
            )
            export_fn(project, output_path)
            url = _job_url(job_id, f"outputs/{output_name}")
            outputs[output_key] = url
            xml_exports = dict(manifest.get("xml_exports") or {})
            xml_exports[target] = {"ok": True, "error": "", "url": url}
            manifest["outputs"] = outputs
            manifest["xml_exports"] = xml_exports
            _write_job_manifest(job_root, manifest)
            append_job_log(job_root, "success", "Export complete", {"target": target, "url": url})
            self._send_json(
                {
                    "ok": True,
                    "job_id": job_id,
                    "target": target,
                    "url": url,
                    "outputs": outputs,
                    "xml_exports": xml_exports,
                    "logs": job_logs_to_dicts(read_job_log(job_root)),
                }
            )
        except Exception as error:
            append_job_log(job_root, "error", f"Exporting {label} failed", {"error": str(error)})
            self._send_json(
                {
                    "ok": False,
                    "error": str(error),
                    "logs": job_logs_to_dicts(read_job_log(job_root)),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _send_job_file(self) -> None:
        relative = unquote(self.path.split("?", 1)[0].removeprefix("/jobs/"))
        safe_parts = [part for part in Path(relative).parts if part not in {"", ".", ".."}]
        if not safe_parts or not _is_valid_job_id(safe_parts[0]):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = JOBS_ROOT / Path(*safe_parts)
        try:
            resolved = path.resolve()
            root = JOBS_ROOT.resolve()
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


def _match_logs_api_path(path: str) -> str | None:
    match = re.fullmatch(r"/api/jobs/([^/]+)/logs", path)
    if not match:
        return None
    job_id = unquote(match.group(1))
    return job_id if _is_valid_job_id(job_id) else None


def _match_export_api_path(path: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"/api/jobs/([^/]+)/exports/([^/]+)", path)
    if not match:
        return None
    job_id = unquote(match.group(1))
    target = unquote(match.group(2))
    if not _is_valid_job_id(job_id):
        return None
    return job_id, target


def _is_valid_job_id(job_id: str) -> bool:
    return bool(JOB_ID_PATTERN.fullmatch(job_id))


def _validated_job_root(job_id: str) -> Path | None:
    if not _is_valid_job_id(job_id):
        return None
    root = JOBS_ROOT.resolve()
    job_root = (JOBS_ROOT / job_id).resolve()
    if root != job_root and root not in job_root.parents:
        return None
    return job_root


def _read_job_manifest(job_root: Path) -> dict[str, Any]:
    path = job_root / "job_manifest.json"
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _write_job_manifest(job_root: Path, manifest: dict[str, Any]) -> None:
    path = job_root / "job_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_sync_report(job_root: Path):
    path = _job_output_path(job_root, "sync_report.json")
    if not path.exists():
        raise ValueError("Sync report is not available for this job.")
    return report_from_dict(json.loads(path.read_text(encoding="utf-8")))


def _job_output_path(job_root: Path, filename: str) -> Path:
    output_dir = (job_root / "outputs").resolve()
    output_path = (output_dir / filename).resolve()
    if output_dir != output_path.parent:
        raise ValueError("Invalid output path.")
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
