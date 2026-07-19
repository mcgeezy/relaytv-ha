# RelayTV HA 0.4.0

This release hardens the Home Assistant integration for credential safety,
authenticated RelayTV servers, and dependable multi-server control. It
requires Home Assistant 2026.7 or newer.

## Highlights

- Playback URLs are sanitized before being exposed as media-player state or
  used as persisted resume keys.
- Legacy resume data is migrated automatically, deduplicated, and capped at
  500 entries.
- Optional `RELAYTV_API_TOKEN` bearer authentication can be configured with a
  masked field and recovered through Home Assistant reauthentication.
- RelayTV API failures now surface as real Home Assistant action errors.
- Explicit service targets can no longer fall back to another TV.
- Sidebar target selection survives multi-entry startup ordering.
- The media player adds native mute, correct zero-valued position/duration,
  and a stable Home Assistant device with a configuration link.
- Automated coverage now includes configuration flows, setup authentication,
  URL/storage migration, targeting, panel persistence, API failures,
  coordinator deduplication, and media properties.

## Security migration

The integration migrates its own resume store on first startup. Home Assistant
recorder history from an older release is intentionally left untouched. If an
old media identifier included a Jellyfin/Emby API key, bearer token, or signed
stream credential:

1. Rotate the affected upstream credential.
2. Purge old recorder history for the RelayTV media-player entity if required
   by your security policy.
3. Update the RelayTV server to the companion release that redacts private
   playback fields from public status, SSE, queue, and history responses.

The companion server update also adds `POST /auth/check` for non-mutating token
validation and cross-origin headers for Home Assistant thumbnail rendering.
Older unprotected RelayTV servers remain compatible, but the current server is
strongly recommended.

## Upgrade

Install 0.4.0 through HACS, restart Home Assistant, and use **Reconfigure** on
the RelayTV integration entry if the server has `RELAYTV_API_TOKEN` enabled.
The HACS archive remains flat, with `manifest.json` directly at the archive
root as required for `/config/custom_components/relaytv/` installation.
