# Security Policy

## Supported versions

Only the latest commit on `main` is supported during the pre-1.0 phase.

## Reporting a vulnerability

Do not open a public issue containing exploit details or credentials. Use GitHub's private vulnerability reporting feature for this repository. Include affected commit, reproduction steps, impact and a minimal proof of concept.

## Security boundaries

The sample pipeline requires no credentials and performs no network calls. Never commit real production payloads, API keys or customer data. The container runs as a non-root numeric user and the Compose service uses a read-only filesystem with `no-new-privileges`.
