from __future__ import annotations

import hashlib
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from audio_conform_syncer.core.audio_features import resample_linear, to_float_mono


class FFmpegError(RuntimeError):
    """Raised when FFmpeg fails or is not available."""


def ffmpeg_version() -> str:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise FFmpegError("FFmpeg was not found on PATH")

    completed = subprocess.run(
        [executable, "-version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise FFmpegError(f"FFmpeg version check failed: {detail}")

    first_line = completed.stdout.splitlines()[0] if completed.stdout else "ffmpeg"
    return first_line


def extract_reference_audio(video_path: Path, output_wav: Path, sample_rate: int) -> None:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-acodec",
            "pcm_s16le",
            str(output_wav),
        ],
        action=f"extracting guide audio from {video_path}",
    )


def load_audio_mono(
    path: Path,
    sample_rate: int,
    work_dir: Path | None = None,
) -> tuple[np.ndarray, int]:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"audio file not found: {path}")

    if path.suffix.lower() in {".wav", ".wave"}:
        samples, source_rate = read_wav_mono(path)
    else:
        if work_dir is None:
            work_dir = path.parent / ".audio-conform-syncer"
        work_dir.mkdir(parents=True, exist_ok=True)
        decoded_path = _decoded_wav_path(path, work_dir)
        decode_audio_to_wav(path, decoded_path, sample_rate=sample_rate)
        samples, source_rate = read_wav_mono(decoded_path)

    if source_rate != sample_rate:
        samples = resample_linear(samples, source_rate=source_rate, target_rate=sample_rate)
        source_rate = sample_rate
    return to_float_mono(samples), source_rate


def decode_audio_to_wav(input_path: Path, output_wav: Path, sample_rate: int) -> None:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-acodec",
            "pcm_s16le",
            str(output_wav),
        ],
        action=f"decoding audio file {input_path}",
    )


def mux_video_with_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    copy_video: bool = True,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_args = ["-c:v", "copy"] if copy_video else ["-c:v", "libx264", "-preset", "veryfast"]
    _run_ffmpeg(
        [
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            *video_args,
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ],
        action=f"muxing synced audio into {video_path}",
    )


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    samples = _pcm_to_float(raw, sample_width)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), sample_rate


def write_wav_mono(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    mono = to_float_mono(samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(mono, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def _run_ffmpeg(args: list[str], action: str = "running FFmpeg") -> None:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise FFmpegError("FFmpeg was not found on PATH")

    completed = subprocess.run(
        [executable, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise FFmpegError(f"FFmpeg failed while {action}: {_shorten_process_output(detail)}")


def _shorten_process_output(detail: str, limit: int = 1400) -> str:
    if len(detail) <= limit:
        return detail
    return detail[:limit].rstrip() + "..."


def _decoded_wav_path(input_path: Path, work_dir: Path) -> Path:
    digest = hashlib.sha1(str(input_path).encode("utf-8")).hexdigest()[:10]
    return work_dir / f"{input_path.stem}-{digest}.wav"


def _pcm_to_float(raw: bytes, sample_width: int) -> np.ndarray:
    if not raw:
        return np.array([], dtype=np.float32)

    if sample_width == 1:
        array = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        return (array - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        bytes_array = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = bytes_array[:, 0] | (bytes_array[:, 1] << 8) | (bytes_array[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0

    raise ValueError(f"unsupported WAV sample width: {sample_width} bytes")
