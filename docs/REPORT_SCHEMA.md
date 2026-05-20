# Sync Report Schema

The JSON sync report is the stable handoff between the match engine, future timeline exporters, and future review UI.

The schema is not frozen yet, but fields should remain clear, explicit, and machine-readable.

## Top-Level Fields

```json
{
  "tool_name": "Audio Conform Syncer",
  "author": "@danreipogi",
  "created_at_utc": "2026-05-20T00:00:00+00:00",
  "reference_media": "path/to/edited_cut.mp4",
  "audio_directory": "path/to/clean_audio",
  "reference_audio": {},
  "source_audio": [],
  "settings": {},
  "matches": [],
  "unmatched_regions": []
}
```

## Audio Summary

Used for `reference_audio` and each item in `source_audio`.

```json
{
  "path": "path/to/audio.wav",
  "sample_rate": 16000,
  "sample_count": 96000,
  "duration_seconds": 6.0
}
```

## Match Candidate

Each match connects one reference timeline range to one clean source audio range.

```json
{
  "source_path": "path/to/source.wav",
  "reference_start_seconds": 0.5,
  "reference_end_seconds": 2.5,
  "source_start_seconds": 1.0,
  "source_end_seconds": 3.0,
  "score": 0.932
}
```

## Unmatched Region

Unmatched regions describe reference timeline ranges that did not produce a confident match.

```json
{
  "start_seconds": 4.5,
  "end_seconds": 5.25
}
```

## Exporter Notes

Future Premiere and Resolve exporters should consume this report instead of calling the matcher directly. That keeps export logic deterministic and makes review workflows possible before timeline files are generated.
