# Contributing

Audio Conform Syncer is early, so the best contributions are focused and easy to verify.

## Principles

- Keep the project local-first and Python-first.
- Do not add export formats until the report data is strong enough to support them.
- Prefer small, testable changes over broad rewrites.
- Keep CLI behavior stable once released.
- Do not commit secrets, sample client media, or large binary files.

## Development Flow

1. Create a virtual environment.
2. Install the package with development extras.
3. Run tests before opening a pull request.
4. Update docs when user-facing behavior changes.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

## Pull Request Checklist

- The change has a clear reason.
- Tests pass locally.
- New behavior is documented.
- Reports remain machine-readable.
- Roadmap-only features are not presented as shipped features.

## Commit Style

Use Conventional Commit style when it fits:

```text
feat: add markdown report output
fix: handle short reference clips
refactor: organize media decoding helpers
docs: clarify manual QA steps
```
