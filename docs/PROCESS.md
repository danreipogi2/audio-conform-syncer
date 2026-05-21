# Build Process

Audio Conform Syncer should move like a serious small tool: tight loops, clear milestones, and no pretend features.

## Operating Principles

- Ship the smallest useful vertical slice first.
- Keep every feature tied to a real conform workflow.
- Prefer deterministic tests over subjective demos.
- Keep generated reports reviewable before adding timeline export.
- Document roadmap items as roadmap items until they are implemented.

## Definition of Done

A change is done when:

- The behavior is implemented.
- Tests cover the risky part.
- CLI behavior is documented when user-facing.
- Reports remain structured and machine-readable.
- Manual QA steps are clear enough for another editor/developer to repeat.

## Milestone Flow

1. Define the user workflow.
2. Add or update the report contract if needed.
3. Implement the smallest matching/export/UI slice.
4. Add focused automated tests.
5. Run a demo-media smoke test.
6. Update docs and changelog.

## Near-Term Milestones

### Milestone 1: Reliable CLI Foundation

- Status: complete for MVP alpha.
- Keep install, demo generation, tests, and CI stable as changes land.
- Keep report schema documentation aligned with generated JSON.

### Milestone 2: Better Match Quality

- Status: in progress beyond MVP alpha.
- Expand fixture coverage using real-world repeated dialogue and music cases.
- Tune confidence bands and score-margin thresholds from real media.

### Milestone 3: Drag-and-Drop Sync App

- Status: timeline review slice in progress.
- Keep media import automatic: users drop files/folders, the app separates video from audio.
- Keep output links visible for synced MP4, XML, JSON report, and Markdown report.
- Show the flattened edit, guide audio, and external sources as readable timeline layers.
- Improve progress feedback for long media jobs.

### Milestone 4: Export Foundation

- Status: conservative XML export slice in progress.
- Keep XML generation downstream of the shared timeline model.
- Add dry-run validators and compatibility notes for Premiere and Resolve import assumptions.

### Milestone 5: Review Experience

- Add a lightweight review surface for matches and unmatched regions.
- Keep it downstream of the report contract so the engine stays reusable.
