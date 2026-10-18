# RelayTV Home Assistant Integration

This integration provides a RelayTV `media_player` entity, RelayTV service actions, and an optional Home Assistant sidebar panel embedding RelayTV UI.

## Implemented Behavior

- `media_player` platform is enabled (`custom_components/relaytv/media_player.py`).
- Hybrid state updates:
  - bootstrap/reconnect uses RelayTV `GET /status`
  - capability discovery prefers RelayTV `WEBSOCKET /ui/ws`
  - RelayTV `GET /ui/events` SSE remains the compatibility fallback
  - three-second `/status` polling activates when neither push transport is healthy
  - `status` events are treated as authoritative full snapshots
  - `playback` / `queue` / `jellyfin` events trigger fast updates or targeted refreshes
- Sidebar panel is registered via Home Assistant frontend iframe panel APIs.
- Optional bearer-token authentication is validated during setup and supports
  Home Assistant reauthentication.
- Credential-bearing query parameters are removed from entity state and
  persisted resume keys.
- RelayTV services are registered from `services.yaml`:
  - `smart_url`
  - `play_now`
  - `enqueue`
  - `clear_queue`
  - `announce`
  - `play_temporary`
  - `cancel_temporary`
  - `jump_to_live`
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
4. Provide RelayTV base URL (example: `http://relaytv-host:8787`), a
   server/display name, and the optional RelayTV API token.

## Options

- `panel_enabled`
- `panel_target_entry_id`
- `sensor_stream_mappings`

## Notes

- `smart_url` uses RelayTV `POST /smart`, which enqueues while already playing and otherwise starts playback immediately (including finite YouTube playlist auto-import via `playlist_mode`).
- `play_now` defaults to RelayTV `POST /play` (clears queue), and uses `POST /play_now` when `preserve_current`, `preserve_to`, `resume_current`, or `playlist_mode` options are specified.
- `enqueue` and `clear_queue` target RelayTV `POST /enqueue` and `POST /clear`.
- Standard Home Assistant `media_player.play_media` (including `enqueue` and `announce`) and `media_player.clear_playlist` are supported natively.
- Upload services target RelayTV `POST /ingest/media`, `POST /ingest/media/play`, and `POST /ingest/media/enqueue`.
- Upload services accept either a Home Assistant local media source selection or an allowlisted `file_path` visible inside the Home Assistant container.
- Overlay requires `text` or `image_url` and supports positions `top-left`, `top-right`, `top-center`, `bottom-left`, and `bottom-right`.
- Snapshot requires active playback on the RelayTV server.
- Snapshot responses are normalized to absolute URLs for Home Assistant entity attributes.
- The integration keeps `/status` as bootstrap/fallback and does not treat either push transport as a replay log.
- RelayTV HA 0.4.0 and newer require Home Assistant 2026.7 or newer.

For fuller documentation and examples, see the repository root README.

## License

RelayTV Home Assistant is licensed under the GNU General Public License,
version 3 only (`GPL-3.0-only`). See the repository root `LICENSE` file.
