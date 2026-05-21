# Audio Conform Syncer

Local audio conform matching for edited video timelines, by [@danreipogi](https://github.com/danreipogi).

Audio Conform Syncer is a local tool for syncing edited video guide audio with clean external audio. It includes a drag-and-drop browser workspace for importing mixed media, reviewing clips, running sync, inspecting timeline tracks, watching diagnostics, and exporting reports, XML, and a synced MP4.

## Status

MVP alpha complete.

The current build focuses on the core matching path:

- launch a local drag-and-drop sync workspace
- review imported clips in media bins and a clip viewer
- extract reference audio from one edited video
- load clean source audio from a folder
- search for matching regions with normalized correlation
- flag ambiguous repeated-audio matches with confidence metadata
- merge adjacent hits into readable regions
- show synced regions as timeline layers in the local app
- show per-job diagnostics and lifecycle logs
- write structured JSON and Markdown reports with summary diagnostics
- export a synced MP4 with matched clean audio placed under the video
- export conservative Premiere and DaVinci Resolve XML from completed sync jobs

A richer timeline editor and deeper NLE-specific metadata are roadmap items, not current features.

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
  - score margins and confidence labels
  - coverage summary
  - diagnostic notes
  - unmatched reference regions
  - run settings
- Optional Markdown summary for manual review
- Optional synced MP4 from the local app
- Premiere XML from the local app after sync completes
- DaVinci Resolve XML from the local app after sync completes

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

Launch the local app:

```powershell
audio-conform-syncer --app
```

Open the printed local URL, then drop one flattened edit and one or more audio files or folders. The app separates media into a flattened edit bin, source audio bin, and warnings bin. Unsupported files are warnings, not fatal errors, and extra videos are ignored after the first selected flattened edit.

The browser workspace follows a simple editor-style flow:

1. Import media.
2. Review clips in the media pane and viewer.
3. Synchronize the guide audio against source audio.
4. Review synced regions on timeline tracks.
5. Export XML for Premiere Pro or DaVinci Resolve.

The workspace includes:

- top workflow buttons for Add Media, Synchronize, Export Premiere XML, and Export DaVinci Resolve XML
- a media pane with Flattened Edit, Source Audio, and Warnings bins
- a viewer/preview panel for the selected media or timeline region
- a timeline review with a time ruler, reference video row, guide-audio row, one source-audio row per file, confidence labels, and unmatched rows
- a diagnostics/job log panel with timestamped backend events
- a results area with JSON, Markdown, synced MP4, and XML download links

After sync completes, the timeline shows:

- a flattened edit / reference video layer
- a baked-in guide audio layer
- one external audio layer per source file
- synced audio regions positioned on the timeline
- unmatched audio layers
- confidence labels and low-confidence styling

Job outputs are written under `.audio-conform-syncer/ui_jobs/<job-id>/outputs/`. Original source media is never modified or overwritten. XML export actions are only enabled after a successful sync, and XML files are written only into that job output folder.

The command-line path is still available:

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

If repeated dialogue, room tone, or music creates ambiguous matches, use `--min-score-margin` to require the best alignment to beat the nearest distinct runner-up:

```powershell
audio-conform-syncer --video edited_cut.mp4 --audio-dir clean_audio --min-score-margin 0.05
```

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
      app/          local drag-and-drop browser app
      cli/          command-line entry point
      core/         matching and timeline logic
      exports/      report writers
      media/        FFmpeg and WAV handling
      models/       dataclasses shared across the package
  scripts/
    create_demo_media.py
  tests/
    test_correlation.py
    test_demo_workflow.py
    test_merge.py
```

## Manual QA Checklist

Before a public release or tagged build:

- Confirm `ffmpeg -version` works in the active shell.
- Run the CLI against a short edited video with guide audio.
- Run `audio-conform-syncer --app`, drop the same media, and confirm the synced MP4/report links appear.
- Confirm all highlighted files from a multi-file drag appear in the intake lists.
- Confirm the timeline layer view appears after sync.
- Confirm Premiere XML and DaVinci Resolve XML buttons are enabled after sync.
- Click each XML export button and confirm the XML link appears after export.
- Use at least two clean source audio files in the input folder.
- Confirm `sync_report.json` is created and valid JSON.
- Check that reported reference/source time ranges are plausible.
- Check report coverage, match confidence labels, and diagnostic notes.
- Re-run with a higher threshold and confirm fewer or equal matches.
- Re-run with `--min-score-margin 0.05` if repeated source audio creates ambiguous matches.
- Re-run with `--markdown-output` and confirm the review summary opens cleanly.
- Run the automated tests.

## Roadmap

- Strengthen match scoring and false-positive handling.
- Improve Premiere-compatible XML export metadata.
- Improve DaVinci Resolve XML export metadata.
- Improve the review UI timeline for inspecting matches.
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
