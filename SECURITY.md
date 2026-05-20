# Security Policy

Audio Conform Syncer is a local command-line media tool. It does not require accounts, tokens, or hosted services for MVP use.

## Supported Versions

No public release is supported yet.

| Version | Supported |
| --- | --- |
| 0.1.x | No public support policy yet |

## Reporting a Vulnerability

If this project becomes public, add a preferred private reporting channel here before release.

Until then, avoid opening public issues that include private media paths, client names, proprietary filenames, or reproduction assets that cannot be shared.

## Local Media Safety

- Treat unknown media files as untrusted input.
- Keep FFmpeg updated.
- Do not run the tool with elevated privileges.
- Do not commit generated reports if they contain private production metadata.
- Review `.env.example` before adding any future configuration variables.
