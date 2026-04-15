# RelayTV Home Assistant Integration

This integration provides a RelayTV `media_player` entity, RelayTV service actions, and an optional Home Assistant sidebar panel embedding RelayTV UI.

## Implemented Behavior

- `media_player` platform is enabled (`custom_components/relaytv/media_player.py`).
- Hybrid state updates:
  - bootstrap/reconnect uses RelayTV `GET /status`
  - RelayTV `GET /ui/events` SSE provides hot-state updates
  - `status` events are treated as authoritative full snapshots
  - `playback` / `queue` / `jellyfin` events trigger fast updates or targeted refreshes
- Sidebar panel is registered via Home Assistant frontend iframe panel APIs.
- RelayTV services are registered from `services.yaml`:
  - `smart_url`
  - `play_now`
  - `announce`
  - `play_temporary`
  - `overlay`
  - `play_synced`
  - `snapshot`
  - `play_with_resume`
  - `upload_media`
  - `upload_media_play`
  - `upload_media_enqueue`

## Setup

1. Place this folder at:

   `/config/custom_components/relaytv/`

2. Restart Home Assistant.
3. Add integration: **Settings -> Devices & Services -> Add Integration -> RelayTV**.
4. Provide RelayTV base URL (example: `http://relaytv-host:8787`) and a server/display name.

## Options

- `panel_enabled`
- `panel_target_entry_id`
- `sensor_stream_mappings`

## Notes

- `smart_url` uses RelayTV `POST /smart`, which enqueues while already playing and otherwise starts playback immediately.
- `play_now` and `announce` currently target RelayTV `POST /play`.
- RelayTV also exposes `POST /play_now`, but this integration does not currently use its preserve-current behavior.
- Upload services target RelayTV `POST /ingest/media`, `POST /ingest/media/play`, and `POST /ingest/media/enqueue`.
- Upload services accept either a Home Assistant local media source selection or an allowlisted `file_path` visible inside the Home Assistant container.
- Overlay requires `text` or `image_url`.
- Snapshot requires active playback on the RelayTV server.
- Snapshot responses are normalized to absolute URLs for Home Assistant entity attributes.
- The integration keeps `/status` as bootstrap/fallback and does not treat `/ui/events` as a replay log.

For fuller documentation and examples, see the repository root README.
