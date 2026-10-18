# RelayTV HA 0.6.0

Play URLs and local Home Assistant media directly through the standard
media-player actions, including announcements that restore previous playback
and queue controls. This release also adds RelayTV services, richer live-stream
state, and safer URL handling. It requires Home Assistant 2026.7 or newer.

## Highlights

- Support native `media_player.play_media` with `enqueue: replace | add | next | play`,
  `announce: true`, and local `media-source://` uploads, plus
  `media_player.clear_playlist`.
- Add `relaytv.enqueue`, `relaytv.clear_queue`, `relaytv.cancel_temporary`, and
  `relaytv.jump_to_live` for queue, temporary-playback, and DVR control.
- Add resolver, CEC, and playlist options to smart playback, and
  preserve-current and playlist options to `relaytv.play_now`.
- Honor announcement and enqueue options for local uploads. Move play-next
  items by their stable queue IDs, keeping duplicate URLs distinct.
- Expose provider, live-stream, and DVR attributes and report the server
  software version. Keep media identities when the server omits playback URLs,
  clear stale metadata after stop, and publish DVR changes while paused.
- Redact Plex tokens from media URLs, validate malformed base URL hosts and
  ports, and align overlay positions with the server.

## Compatibility and deployment

- Existing configuration and optional API tokens are reused without migration.
- The minimum supported Home Assistant version remains 2026.7.
- Use an up-to-date RelayTV server for playlist imports, DVR controls, and other
  new endpoints. Preserve-current playback falls back to `/play` when
  `/play_now` is unavailable; that fallback clears the queue.
- `relaytv.play_now` retains queue-clearing behavior by default. Preservation
  options use `/play_now`, with `preserve_to: queue_front` as the supported
  destination.
- Playlist imports append to the queue. Play-next supports individual items;
  use `playlist_mode: video` to select one video from a YouTube playlist link.
  Unsupported play-next playlist imports are rejected before queueing.
- Play-next requires a server that returns stable queue IDs and supports
  `/queue/move`. If the server omits the new item's ID, the action reports that
  it was appended but could not be moved.
- Existing WebSocket, SSE, and polling fallback behavior remains available.

Breaking changes: None to existing released services.

## Verification

- All 74 automated tests and Ruff checks pass.
- Regression coverage includes queue ordering with duplicate URLs, supported
  preservation options, local-file announcement and enqueue behavior, upload
  responses without playable URLs, and DVR-only push updates.
- The release archive layout is checked for a root-level `manifest.json`.
- Live-device playback and clean HACS installation must still be verified
  before publication using the release checklist.

## Upgrade

Install 0.6.0 through HACS when published and restart Home Assistant. Existing
entries and optional API tokens are reused without reconfiguration. The HACS
archive remains flat, with `manifest.json` directly at its root for installation
under `/config/custom_components/relaytv/`.
