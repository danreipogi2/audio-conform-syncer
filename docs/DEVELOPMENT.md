# Development

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

FFmpeg must be available on `PATH` for end-to-end CLI runs:

```powershell
ffmpeg -version
```

## Test

```powershell
python -m pytest
```

The current automated tests cover the matching primitive and timeline merge behavior. End-to-end media tests should use tiny synthetic fixtures when added.

## Run Locally

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --output sync_report.json
```

Add a Markdown summary when doing manual review:

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --output sync_report.json --markdown-output sync_report.md
```

## Generate Demo Media

The repository includes a tiny synthetic media generator for smoke testing the full CLI path without private production files:

```powershell
python scripts/create_demo_media.py
```

The script creates clean source WAVs, a guide WAV, and an `edited_cut.mp4` when FFmpeg is available. Generated files are written to `demo_media/` and ignored by Git.

## Tuning

- `--threshold` controls how confident a match must be.
- `--window-seconds` controls how much reference audio is compared at once.
- `--hop-seconds` controls how often the reference timeline is sampled.
- `--sample-rate` controls analysis sample rate.

Lower thresholds find more candidates and may create false positives. Higher thresholds produce cleaner but sparser reports.

## Diagnostics

Check the local environment:

```powershell
audio-conform-syncer --doctor
```

Validate inputs without extracting or matching:

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --dry-run
```

## Release Notes

Before tagging a release:

- Select a license.
- Confirm README install instructions from a clean virtual environment.
- Run tests.
- Run manual QA against a short real media sample.
- Update `CHANGELOG.md`.

## Pull Request Verification

Before opening a pull request:

```powershell
python -B -m unittest discover -s tests
python -B scripts\create_demo_media.py --help
python -m pip wheel . --no-deps --wheel-dir dist
```

Clean generated `build/`, `dist/`, `*.egg-info`, and `demo_media/` artifacts before committing.
