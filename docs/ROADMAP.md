# Roadmap

Audio Conform Syncer is currently a complete MVP alpha for local report-based audio conform matching.

## Now

- Keep the CLI stable and boring.
- Keep the drag-and-drop app stable for one-video plus one-or-more-audio workflows.
- Keep the timeline layer view and XML export actions stable.
- Run manual QA on short real edits and collect false-positive cases.
- Keep reports structured and reviewable before export tooling.
- Tune confidence and ambiguity thresholds from real media.

## Next

- Add exporter preflight checks for Premiere and Resolve import assumptions.
- Improve the timeline review view with richer waveform previews and zoom.
- Expand fixture coverage for repeated dialogue, music beds, and noisy guide tracks.
- Add stronger multi-stage scoring beyond normalized correlation.
- Improve synced-video export quality and multi-track handling.

## Later

- Round-trip verification against real Premiere and Resolve projects.
- Desktop packaging.
- Batch workflows for multiple edited cuts.

## Non-Goals For The MVP

- Cloud upload.
- Account systems.
- Timeline editing UI.
- Silent XML export without a reviewable report layer.
