# RelayTV Home Assistant Integration

This integration provides a RelayTV `media_player` entity, RelayTV service actions, and an optional Home Assistant sidebar panel embedding RelayTV UI.

## Implemented Behavior

- `media_player` platform is enabled (`custom_components/relaytv/media_player.py`).
- Polling coordinator refreshes RelayTV `GET /status` every 3 seconds.
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
- Overlay requires `text` or `image_url`.
- Snapshot requires active playback on the RelayTV server.
- Snapshot responses are normalized to absolute URLs for Home Assistant entity attributes.

For fuller documentation and examples, see the repository root README.
