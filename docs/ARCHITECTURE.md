# Architecture

Audio Conform Syncer is organized around one MVP workflow:

1. Extract guide audio from a flattened edited video.
2. Decode clean source audio files.
3. Compare reference windows against each source file.
4. Merge adjacent matches into readable timeline regions.
5. Write a structured sync report.

## Package Layout

```text
audio_conform_syncer/
  cli/       command-line parsing and process exit behavior
  core/      audio matching and timeline logic
  exports/   JSON and Markdown report writers
  media/     FFmpeg calls and WAV decoding
  models/    dataclasses shared across modules
```

## Core Matching

The MVP matcher uses normalized correlation. For each reference window, it searches each source file and keeps the strongest match above the configured threshold.

This is intentionally simple and inspectable. It is not yet a full conform engine, but it gives the project a real sync-engine foundation.

## Data Flow

```text
edited video
  -> extracted guide WAV
  -> reference samples
  -> sliding reference windows
  -> best source alignment per window
  -> merged match regions
  -> JSON report
```

## Boundaries

- `media/` owns filesystem media decoding and FFmpeg execution.
- `core/` owns signal analysis and timeline operations.
- `exports/` owns output formatting.
- `cli/` owns user-facing command behavior.

Keeping these boundaries small makes future XML export work easier without mixing export logic into the matcher.

## Future Extension Points

- Add stronger fingerprints or multi-stage scoring inside `core/`.
- Add Premiere and Resolve serializers under `exports/`.
- Add a desktop review layer that consumes the JSON report instead of duplicating matcher logic.
