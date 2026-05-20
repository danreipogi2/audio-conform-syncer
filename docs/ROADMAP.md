# Roadmap

Audio Conform Syncer is currently an early MVP / sync-engine foundation.

## Now

- Keep the CLI stable and boring.
- Improve matching quality with real test cases.
- Keep reports structured enough for export tooling.
- Document manual QA clearly.

## Next

- Add fixture-based integration tests with tiny generated media.
- Improve match confidence scoring.
- Reduce false positives across repeated dialogue or music beds.
- Add clearer diagnostics when FFmpeg is missing or media decode fails.

## Later

- Premiere-compatible XML export.
- DaVinci Resolve XML export.
- Review UI or desktop app for inspecting matches.
- Batch workflows for multiple edited cuts.

## Non-Goals For The MVP

- Cloud upload.
- Account systems.
- Timeline editing UI.
- Silent XML export without a reviewable report layer.
