# RelayTV Home Assistant 0.4.0 Roadmap

Status: implemented and verified on `feat/ha-hardening-v0.4.0`. The companion
RelayTV server changes are isolated on `fix/redact-public-playback-urls`.

This roadmap turns the July 2026 integration review into a coordinated Home
Assistant release and a small RelayTV server companion change. Each milestone
is independently testable and committed before the next milestone begins.

## Milestone 1 — Protect playback credentials and resume data

- Redact credentials and private resolved media URLs from RelayTV public
  status, SSE, queue, and history payloads.
- Sanitize media identifiers again in Home Assistant before exposing entity
  state or writing storage.
- Replace raw resume-URL keys with stable, credential-free keys.
- Migrate legacy resume data without retaining secrets, cap its size, and
  avoid unnecessary storage writes.
- Add server and integration regression tests for redaction and migration.

Acceptance: no API key, bearer token, signed stream credential, or private
resolved stream URL is present in public server payloads, Home Assistant state,
or the RelayTV runtime store.

## Milestone 2 — Authenticate and report failures correctly

- Add optional RelayTV API-token configuration using a password selector.
- Send bearer authentication on all write and upload requests.
- Validate connectivity and credentials during setup, options, and reauth.
- Preserve HTTP status/error context and raise Home Assistant-native errors.
- Restrict compatibility fallbacks to genuinely missing endpoints.

Acceptance: protected and unprotected RelayTV servers both work; rejected or
failed actions visibly fail in Home Assistant rather than reporting success.

## Milestone 3 — Correct targeting and media-player behavior

- Preserve the configured sidebar target across restart and multiple entries.
- Never fall back to another TV when an explicit target cannot be resolved.
- Add current RelayTV mute support and expose mute state.
- Register a Home Assistant device with stable metadata and configuration URL.
- Correct zero-valued position/duration parsing and normalize idle snapshots.

Acceptance: multi-server actions affect only their intended targets and the
media-player entity accurately represents current RelayTV capabilities.

## Milestone 4 — Automated and live verification

- Add pytest coverage for URL handling, coordinator merging, API errors,
  config flows, service targeting, panel persistence, and media properties.
- Run Ruff, pytest, Hassfest-compatible validation, and whitespace checks.
- Exercise the installed integration against the live RelayTV and Home
  Assistant containers.
- Confirm the authenticated Home Assistant entity and sidebar with Playwright.

Acceptance: automated checks pass and the live UI has no integration-related
console or network failures.

## Milestone 5 — HACS release preparation

- Bump the integration to `0.4.0`.
- Update README, changelog, and release notes with migration/security guidance.
- Confirm the HACS release archive layout and manifest contents.

Acceptance: the branch is ready for review as a HACS release PR; release
tagging and publication remain with the repository's release workflow.
