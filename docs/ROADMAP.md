# Roadmap

Audio Conform Syncer is currently a complete MVP alpha for local report-based audio conform matching.

## Now

- Keep the CLI stable and boring.
- Run manual QA on short real edits and collect false-positive cases.
- Keep reports structured and reviewable before export tooling.
- Tune confidence and ambiguity thresholds from real media.

## Next

- Add exporter preflight checks for Premiere and Resolve assumptions.
- Expand fixture coverage for repeated dialogue, music beds, and noisy guide tracks.
- Add stronger multi-stage scoring beyond normalized correlation.
- Add a small report viewer for manual review.

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
