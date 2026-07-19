# Changelog

## 0.4.0

- Remove credentials from media-player state and stored resume keys, migrate
  legacy resume data, and cap the resume store at 500 entries.
- Add optional RelayTV bearer-token configuration, setup validation,
  reauthentication, and reconfiguration flows.
- Report connection, authentication, and server errors instead of silently
  treating failed actions as successful.
- Prevent an invalid explicit service target from falling back to a different
  RelayTV server and preserve the selected sidebar target during startup.
- Add native mute support, accurate zero-valued media properties, stable
  Home Assistant device metadata, and quieter idle-state event handling.
- Add a pinned Home Assistant 2026.7 test environment and GitHub Actions CI.

Security note: older Home Assistant recorder rows can retain media identifiers
written by an earlier integration release. Rotate any affected upstream media
API credentials and purge the RelayTV entity's old recorder history if those
identifiers contained secrets.

## 0.3.12

- Fix the HACS release archive layout so `manifest.json` installs directly
  under `/config/custom_components/relaytv/`.

## 0.2.3

- Fix HA seek bar by providing media_position_updated_at.
- Add entity_picture support (thumbnail) when RelayTV status includes artwork fields.
- Improve seek/volume command payload compatibility.

## 0.2.2
- Fix `relaytv.smart_url` behavior: prefer enqueue/smart endpoints and avoid replacing current playback when possible.
## v0.2.1
- Fix OptionsFlow crash (`config_entry` is a read-only property in recent Home Assistant versions)

## v0.2.0
- Add `media_player.relaytv` entity backed by RelayTV HTTP API
- Add `relaytv.smart_url` service for automations / Companion App sharing

## v0.1.0
- Initial HACS-ready release of **RelayTV Panel**
- Adds a sidebar iframe panel pointing to a configurable RelayTV base URL
