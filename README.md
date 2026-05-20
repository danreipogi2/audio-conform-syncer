# Audio Conform Syncer

Local audio conform matching for edited video timelines, by [@danreipogi](https://github.com/danreipogi).

Audio Conform Syncer is a Python-first tool for finding where clean source audio appears inside a flattened edited video with baked-in guide audio. It extracts the guide track, scans original audio files, and writes a structured sync report that can become the foundation for future XML export workflows.

## Status

Early MVP / sync-engine foundation.

The current build focuses on the core matching path:

- extract reference audio from one edited video
- load clean source audio from a folder
- search for matching regions with normalized correlation
- merge adjacent hits into readable regions
- write a structured JSON report

Premiere XML export, DaVinci Resolve XML export, and review UI work are roadmap items, not current features.

## Supported Inputs

- One flattened edited video with baked-in guide audio
- A folder of original clean audio files
- FFmpeg-readable media formats for CLI runs
- WAV files for direct Python decoding

For best results, use clean production audio with the same content as the guide track and avoid heavily processed guide audio when possible.

## Outputs

- JSON sync report containing:
  - reference media metadata
  - source audio metadata
  - matched reference/source time ranges
  - confidence scores
  - unmatched reference regions
  - run settings
- Optional Markdown summary for manual review

## Requirements

- Python 3.10+
- FFmpeg available on `PATH`
- NumPy

## Install

Create a virtual environment, then install the package in editable mode:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

For development:

```powershell
python -m pip install -e ".[dev]"
```

## Run

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --output sync_report.json
```

Example with a Markdown review summary:

```powershell
audio-conform-syncer `
  --video ".\media\episode_edit.mp4" `
  --audio-dir ".\media\clean_audio" `
  --output ".\reports\sync_report.json" `
  --markdown-output ".\reports\sync_report.md"
```

Useful tuning flags:

```powershell
audio-conform-syncer --help
```

The defaults are intentionally conservative for MVP use. If the report is too sparse, lower `--threshold` slightly. If it is too noisy, raise it.

Check the local environment:

```powershell
audio-conform-syncer --doctor
```

Validate inputs without extracting or matching media:

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --dry-run
```

## Quick Demo

Generate tiny synthetic media for a local smoke test:

```powershell
python scripts/create_demo_media.py
```

Then run the matcher:

```powershell
audio-conform-syncer `
  --video ".\demo_media\edited_cut.mp4" `
  --audio-dir ".\demo_media\clean_audio" `
  --output ".\demo_media\sync_report.json" `
  --markdown-output ".\demo_media\sync_report.md" `
  --window-seconds 1 `
  --hop-seconds 0.5 `
  --threshold 0.5
```

The demo script writes generated files to `demo_media/`, which is ignored by Git.

## Project Structure

```text
audio-conform-syncer/
  docs/
    ARCHITECTURE.md
    DEVELOPMENT.md
    PROCESS.md
    REPORT_SCHEMA.md
    ROADMAP.md
  src/
    audio_conform_syncer/
      cli/          command-line entry point
      core/         matching and timeline logic
      exports/      report writers
      media/        FFmpeg and WAV handling
      models/       dataclasses shared across the package
  scripts/
    create_demo_media.py
  tests/
    test_correlation.py
    test_merge.py
```

## Manual QA Checklist

Before a public release or tagged build:

- Confirm `ffmpeg -version` works in the active shell.
- Run the CLI against a short edited video with guide audio.
- Use at least two clean source audio files in the input folder.
- Confirm `sync_report.json` is created and valid JSON.
- Check that reported reference/source time ranges are plausible.
- Re-run with a higher threshold and confirm fewer or equal matches.
- Re-run with `--markdown-output` and confirm the review summary opens cleanly.
- Run the automated tests.

## Roadmap

- Strengthen match scoring and false-positive handling.
- Add Premiere-compatible XML export.
- Add DaVinci Resolve XML export.
- Add a review UI or desktop app for inspecting matches.
- Add fixture-based integration tests with tiny media samples.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the working roadmap.

## Build Process

This project is developed milestone by milestone:

- keep the CLI and report contract stable
- improve the match engine with deterministic tests
- add export support only after the report layer is reliable
- keep roadmap items clearly separated from shipped features

See [docs/PROCESS.md](docs/PROCESS.md) for the working process.

## Contributing

Contributions should keep the tool practical, local-first, and honest about what is implemented. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Security

This is a local media-processing tool. Do not run it on untrusted media in privileged environments. See [SECURITY.md](SECURITY.md).

## License

No license has been selected yet. Choose a license before public release so users know what rights they have to use, modify, and redistribute the project.
