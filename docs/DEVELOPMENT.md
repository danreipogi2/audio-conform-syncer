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

The automated tests cover the matching primitive, ambiguity scoring, timeline merge behavior, CLI validation, generated demo-media workflow, upload intake, timeline serialization, media export, and XML export.

## Run Locally

Launch the drag-and-drop app:

```powershell
audio-conform-syncer --app
```

The app serves only on `127.0.0.1` by default. Uploaded media and generated outputs are written under `.audio-conform-syncer/ui_jobs/`, which is ignored by Git.

Manual app smoke test:

1. Launch `audio-conform-syncer --app`.
2. Drag one flattened video and several audio files into the drop zone.
3. Confirm the first video is selected and all audio files are listed.
4. Click Synchronize.
5. Confirm timeline layers render for the reference video, guide audio, and each external audio file.
6. Confirm Premiere XML, DaVinci Resolve XML, synced MP4, JSON, and Markdown links appear.

Run the CLI directly:

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
- `--min-score-margin` filters ambiguous repeated audio by requiring the best alignment to beat the nearest distinct runner-up.
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
