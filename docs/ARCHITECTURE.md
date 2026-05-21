# Architecture

Audio Conform Syncer is organized around one MVP workflow:

1. Import media through the local drag-and-drop app or CLI.
2. Automatically separate one video reference from clean source audio.
3. Extract guide audio from the flattened edited video.
4. Decode clean source audio files.
5. Compare reference windows against each source file.
6. Merge adjacent matches into readable timeline regions.
7. Summarize coverage, confidence, and diagnostics.
8. Build a timeline layer model for app review and XML export.
9. Write structured reports and, from the app, export synced MP4/XML files.

## Package Layout

```text
audio_conform_syncer/
  app/       local browser workspace and upload/sync API
  cli/       command-line parsing and process exit behavior
  core/      audio matching and timeline logic
  exports/   JSON, Markdown, MP4, timeline model, and XML writers
  media/     FFmpeg calls and WAV decoding
  models/    dataclasses shared across modules
```

## Core Matching

The MVP matcher uses normalized correlation. For each reference window, it searches each source file and keeps the strongest match above the configured threshold.

Each alignment also records a runner-up margin so repeated dialogue, tones, or music beds can be marked as ambiguous or filtered with `--min-score-margin`. This is intentionally simple and inspectable. It is not a full conform engine, but it is a complete local report-first MVP.

## Data Flow

```text
edited video
  -> app/CLI input classification
  -> extracted guide WAV
  -> reference samples
  -> sliding reference windows
  -> best source alignment per window
  -> confidence and ambiguity scoring
  -> merged match regions
  -> coverage and diagnostic summary
  -> JSON/Markdown report
  -> timeline layer model
  -> synced MP4 export
  -> Premiere/Resolve XML export
```

## Boundaries

- `media/` owns filesystem media decoding and FFmpeg execution.
- `core/` owns signal analysis and timeline operations.
- `exports/` owns output formatting.
- `cli/` owns user-facing command behavior.
- `app/` owns local browser UX, upload handling, and job orchestration.

Keeping these boundaries small makes future XML export work easier without mixing export logic into the matcher.

## Future Extension Points

- Add stronger fingerprints or multi-stage scoring inside `core/`.
- Improve Premiere and Resolve serializers under `exports/`.
- Expand the app review layer while keeping it downstream of the shared timeline model.

See [REPORT_SCHEMA.md](REPORT_SCHEMA.md) for the report contract that future exporters should consume.
