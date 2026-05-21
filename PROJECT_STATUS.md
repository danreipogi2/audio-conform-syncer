# Audio Conform Syncer Project Status

Last updated: 2026-05-21

## Current State

Audio Conform Syncer has two layers right now:

1. A committed and pushed sync-engine MVP on GitHub.
2. A local in-progress drag-and-drop app layer that moves the project toward a PluralEyes-style user experience with timeline layers and XML export.

The GitHub branch `main` is synced with the last committed engine/reporting MVP. The local working tree currently contains uncommitted UI/app work.

## Pushed To GitHub

Repository:

https://github.com/danreipogi2/audio-conform-syncer

Latest pushed commit:

```text
c0eab6b feat: complete mvp reporting and diagnostics
```

That pushed version includes:

- Python package structure
- CLI entry point
- FFmpeg-based guide audio extraction
- Clean source audio decoding
- Normalized correlation matching
- Adjacent match merging
- JSON sync reports
- Markdown review reports
- Coverage summary
- Confidence labels and score margins
- Diagnostics for ambiguous or weak results
- `--min-score-margin` tuning
- Synthetic demo media generator
- Automated tests for core matching, merging, CLI behavior, and demo workflow

The pushed MVP was validated with:

```text
python -m pytest
python -B -m unittest discover -s tests
python -m pip wheel . --no-deps
demo media end-to-end CLI smoke test
```

## Local In-Progress Work

The current local working tree adds the first version of the app UX the project actually needs:

- Local browser app launched with:

```powershell
python -B -m audio_conform_syncer --app
```

- Drag-and-drop media intake
- File/folder picker fallback
- Automatic video/audio classification
- One video plus one or more audio files
- Sync button and results panel
- JSON report link
- Markdown report link
- First-pass synced MP4 export
- Timeline layer results view
- Lightweight waveform-like peak previews
- Premiere XML export
- DaVinci Resolve XML export
- Local job storage under:

```text
.audio-conform-syncer/ui_jobs/
```

New local files include:

```text
src/audio_conform_syncer/app/
src/audio_conform_syncer/exports/media_export.py
src/audio_conform_syncer/exports/timeline_model.py
src/audio_conform_syncer/exports/xml_export.py
tests/test_app_server.py
tests/test_media_export.py
tests/test_timeline_model.py
tests/test_xml_export.py
```

Modified local files include docs, CLI wiring, package metadata, FFmpeg helpers, and security notes.

## Validation Status

Before the final small app-server hardening edits, this local app work passed:

```text
python -B -m pytest
13 passed
```

It also passed a CLI help check after adding `--app`.

The timeline/XML branch currently has automated coverage for upload intake, timeline serialization, XML export, and media export. The next step is still a manual browser drag-and-drop test with real media.

## Current Product Direction

The intended UX is PluralEyes-style:

1. User opens the app.
2. User drops mixed video/audio files or folders.
3. App automatically separates video from audio.
4. User clicks Synchronize.
5. App shows match coverage, confidence, diagnostics, and timeline layers.
6. User downloads/reviews the synced video, XML exports, and reports.

The command line should remain available, but it should no longer be the primary user experience.

## What Works Now

The committed engine can already:

- Analyze a video guide track against clean audio.
- Find matching source regions.
- Report match confidence and ambiguity.
- Generate JSON and Markdown reports.

The local app work is designed to:

- Make import simple.
- Hide path management from the user.
- Produce a synced MP4, XML files, and reports.

## Not Done Yet

- Final validation of the local drag-and-drop app after the latest edits
- Manual browser testing with real dragged files
- Strong progress feedback during long sync jobs
- Richer zoomable timeline review UI
- Multi-video batch workflows
- Round-trip validation in Premiere Pro and DaVinci Resolve
- Release license selection
- `v0.1.0` tag/release

## Next Recommended Steps

1. Run validation:

```powershell
python -B -m pytest
python -B -m audio_conform_syncer --help
python -B -m audio_conform_syncer --doctor
```

2. Launch the app:

```powershell
python -B -m audio_conform_syncer --app
```

3. Test the UI with one edited video and one or more clean audio files.

4. Fix any browser/app issues found during manual testing.

5. Commit and push the app work.

6. Add a license and prepare a `v0.1.0` release.
