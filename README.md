# RelayTV Home Assistant Integration

![RelayTV logo](custom_components/relaytv/brand/logo.png)

RelayTV integrates with Home Assistant as a local `media_player` plus RelayTV-specific services.

## Current Feature Set

- Creates a `media_player` entity for each RelayTV config entry.
- Polls RelayTV `GET /status` every 3 seconds.
- Supports media controls from Home Assistant:
  - Play, pause, stop
  - Next and previous
  - Seek
  - Volume set
  - Turn on / turn off
- Registers a Home Assistant sidebar panel that embeds the RelayTV UI.
- Supports multi-target synchronized start (`play_synced`) using RelayTV `POST /play_at`.
- Supports snapshots (`snapshot`) and exposes `snapshot_url` on the entity.
- Stores resume positions and provides `play_with_resume` behavior.
- Supports optional sensor->stream mappings that trigger temporary playback when a mapped sensor turns `on`.

## RelayTV Services

| Service | RelayTV endpoint | Notes |
| --- | --- | --- |
| `relaytv.smart_url` | `POST /smart` | One-button play/enqueue behavior from RelayTV |
| `relaytv.play_now` | `POST /play` | Immediate playback; clears queue |
| `relaytv.announce` | `POST /play` | Alias of `play_now` |
| `relaytv.play_temporary` | `POST /play_temporary` | Temporary interrupt + resume flow |
| `relaytv.overlay` | `POST /overlay` | Text/image overlay |
| `relaytv.play_synced` | `POST /play_at` | Multi-entity time-aligned start |
| `relaytv.snapshot` | `POST /snapshot` (fallback `GET /snapshot`) | Captures current frame |
| `relaytv.play_with_resume` | `POST /play` + `POST /seek_abs` | Resume per-URL saved position |

## Installation (HACS)

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository with category `Integration`.
3. Install `RelayTV`.
4. Restart Home Assistant.
5. Add the `RelayTV` integration from **Settings -> Devices & Services**.

## Installation (Manual)

1. Copy this repository's `custom_components/relaytv` folder into your Home Assistant config:

   `/config/custom_components/relaytv/`

2. Restart Home Assistant.
3. Go to **Settings -> Devices & Services -> Add Integration**.
4. Search for **RelayTV**.
5. Enter:
   - RelayTV base URL (example: `http://relaytv-host:8787`)
   - Display name for this RelayTV instance

## Options

From the integration options flow, you can configure:

- `panel_enabled`: enable/disable sidebar panel registration
- `panel_target_entry_id`: which RelayTV config entry is used by the shared sidebar panel
- `sensor_stream_mappings`: list of sensor-to-URL mappings for temporary playback triggers

## Example Service Calls

```yaml
service: relaytv.play_now
target:
  entity_id: media_player.relaytv_living_room
data:
  url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  use_ytdlp: true
  cec: false
```

```yaml
service: relaytv.play_temporary
target:
  entity_id: media_player.relaytv_living_room
data:
  url: https://example.com/doorbell-chime.mp3
  timeout: 10
  volume: 0.6
```

```yaml
service: relaytv.overlay
target:
  entity_id: media_player.relaytv_living_room
data:
  text: Front door opened
  duration: 8
  position: top-right
```

## Known Limitations

- `relaytv.play_now` currently maps to RelayTV `POST /play` (queue-clearing behavior).
- No dedicated `enqueue` or `clear_queue` Home Assistant service is currently registered by this integration.
- Overlay calls must include at least `text` or `image_url`.
- Integration uses local polling; it does not currently use WebSocket push updates.

## Compatibility

Validated against RelayTV app routes in `/opt/relaytv/app/relaytv_app/routes.py` and API docs in `/opt/relaytv/docs/API.md`.
