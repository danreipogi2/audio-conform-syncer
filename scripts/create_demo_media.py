from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import wave
from pathlib import Path


SAMPLE_RATE = 16_000


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate tiny demo media for Audio Conform Syncer.")
    parser.add_argument(
        "--output-dir",
        default="demo_media",
        help="Directory for generated demo media. Defaults to demo_media.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing files in the output directory.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not args.overwrite:
        raise SystemExit(f"{output_dir} already contains files. Re-run with --overwrite.")

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_audio_dir = output_dir / "clean_audio"
    clean_audio_dir.mkdir(parents=True, exist_ok=True)

    source_a = _tone_sequence([330.0, 392.0, 494.0, 392.0], tone_seconds=1.0)
    source_b = _tone_sequence([523.25, 659.25, 587.33, 523.25], tone_seconds=1.0)
    guide = _concat(
        _silence(0.5),
        source_a[int(0.5 * SAMPLE_RATE) : int(2.5 * SAMPLE_RATE)],
        _silence(0.5),
        source_b[int(1.0 * SAMPLE_RATE) : int(3.0 * SAMPLE_RATE)],
        _silence(0.75),
    )

    write_wav(clean_audio_dir / "source_a.wav", source_a)
    write_wav(clean_audio_dir / "source_b.wav", source_b)
    guide_wav = output_dir / "reference_guide.wav"
    write_wav(guide_wav, guide)

    edited_video = output_dir / "edited_cut.mp4"
    if shutil.which("ffmpeg"):
        _make_video_with_audio(guide_wav, edited_video)
        print(f"Wrote demo video: {edited_video}")
    else:
        print("FFmpeg was not found on PATH. Wrote reference_guide.wav but skipped MP4 creation.")

    print(f"Wrote clean audio folder: {clean_audio_dir}")
    print("Demo media is generated, synthetic, and safe to delete.")
    return 0


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, sample))
            frames.extend(int(value * 32767).to_bytes(2, byteorder="little", signed=True))
        wav_file.writeframes(bytes(frames))


def _tone_sequence(frequencies: list[float], tone_seconds: float) -> list[float]:
    samples: list[float] = []
    for frequency in frequencies:
        samples.extend(_tone(frequency, tone_seconds))
    return samples


def _tone(frequency: float, seconds: float) -> list[float]:
    total = int(seconds * SAMPLE_RATE)
    return [
        0.6 * math.sin(2.0 * math.pi * frequency * (index / SAMPLE_RATE))
        for index in range(total)
    ]


def _silence(seconds: float) -> list[float]:
    return [0.0] * int(seconds * SAMPLE_RATE)


def _concat(*chunks: list[float]) -> list[float]:
    samples: list[float] = []
    for chunk in chunks:
        samples.extend(chunk)
    return samples


def _make_video_with_audio(audio_path: Path, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1280x720:r=24",
        "-i",
        str(audio_path),
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"FFmpeg failed while creating demo video: {detail}")


if __name__ == "__main__":
    raise SystemExit(main())
