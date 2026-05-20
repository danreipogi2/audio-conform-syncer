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

- Keep install, demo generation, tests, and CI stable.
- Improve diagnostics for FFmpeg and media errors.
- Add report schema documentation.

### Milestone 2: Better Match Quality

- Add fixture-based media tests.
- Improve repeated-audio false-positive handling.
- Add confidence bands and richer diagnostics.

### Milestone 3: Export Foundation

- Freeze the sync report fields required by timeline exporters.
- Add dry-run validators for Premiere and Resolve export assumptions.
- Implement XML export only after the report layer is reliable.

### Milestone 4: Review Experience

- Add a lightweight review surface for matches and unmatched regions.
- Keep it downstream of the report contract so the engine stays reusable.
