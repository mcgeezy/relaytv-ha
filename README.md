# RelayTV Home Assistant Integration

![RelayTV logo](custom_components/relaytv/brand/logo.png)

RelayTV for Home Assistant adds your self-hosted RelayTV servers as Home Assistant entities and services, making it easy to control playback, launch media, trigger overlays, and integrate RelayTV into automations and dashboards.

RelayTV server:  
https://github.com/mcgeezy/relaytv

Android companion app:  
https://github.com/mcgeezy/relaytv-android

Support the project:  
https://buymeacoffee.com/relaytv

---

## What This Integration Adds

RelayTV integrates with Home Assistant as a local `media_player` plus RelayTV-specific services.

### Core features

- Creates a `media_player` entity for each RelayTV config entry
- Supports multiple RelayTV servers
- Uses RelayTV live event updates plus `/status` refresh fallback
- Adds a Home Assistant sidebar panel for the RelayTV web UI
- Exposes RelayTV-specific services for smart play, temporary playback, overlays, snapshots, synchronized playback, and resume behavior
- Supports automation-friendly control from scripts, dashboards, and mobile workflows

### Supported media controls

- Play
- Pause
- Stop
- Next
- Previous
- Seek
- Set volume
- Turn on
- Turn off

### Advanced RelayTV features

- Smart queue/play behavior
- Temporary interrupt + resume playback
- Text and image overlays
- Snapshot capture
- Multi-target synchronized playback
- Resume-position support
- Optional sensor-to-stream mapping triggers

---

## Screenshots

<!-- Suggested screenshots:
1. Home Assistant Devices & Services config entry
2. Media player entity card
3. Sidebar panel showing RelayTV UI
4. Example automation/service call
-->

_Add screenshots here for release._

---

## RelayTV Services

| Service | RelayTV endpoint | Notes |
| --- | --- | --- |
| `relaytv.smart_url` | `POST /smart` | Smart play/enqueue behavior |
| `relaytv.play_now` | `POST /play` | Immediate playback; clears queue |
| `relaytv.announce` | `POST /play` | Alias of `play_now` |
| `relaytv.play_temporary` | `POST /play_temporary` | Temporary interrupt + resume flow |
| `relaytv.overlay` | `POST /overlay` | Text/image overlay |
| `relaytv.play_synced` | `POST /play_at` | Multi-entity time-aligned start |
| `relaytv.snapshot` | `POST /snapshot` (fallback `GET /snapshot`) | Captures current frame |
| `relaytv.play_with_resume` | `POST /play` + `POST /seek_abs` | Resume per-URL saved position |

---

## Installation

### HACS

1. Open HACS in Home Assistant
2. Add this repository as a custom repository with category `Integration`
3. Install `RelayTV`
4. Restart Home Assistant
5. Add the `RelayTV` integration from **Settings → Devices & Services**

### Manual

1. Copy `custom_components/relaytv` into your Home Assistant config:

   ```text
   /config/custom_components/relaytv/
   ```

2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **RelayTV**
5. Enter:
   - RelayTV base URL, for example `http://relaytv-host:8787`
   - Display name for this RelayTV instance

---

## Configuration Options

From the integration options flow, you can configure:

- `panel_enabled` — enable or disable sidebar panel registration
- `panel_target_entry_id` — choose which RelayTV server is used by the shared sidebar panel
- `sensor_stream_mappings` — map sensors to temporary playback URLs

---

## Example Service Calls

### Smart play / enqueue

```yaml
service: relaytv.smart_url
target:
  entity_id: media_player.relaytv_living_room
data:
  url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### Immediate playback

```yaml
service: relaytv.play_now
target:
  entity_id: media_player.relaytv_living_room
data:
  url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  use_ytdlp: true
  cec: false
```

### Temporary playback

```yaml
service: relaytv.play_temporary
target:
  entity_id: media_player.relaytv_living_room
data:
  url: https://example.com/doorbell-chime.mp3
  timeout: 10
  volume: 0.6
```

### Overlay message

```yaml
service: relaytv.overlay
target:
  entity_id: media_player.relaytv_living_room
data:
  text: Front door opened
  duration: 8
  position: top-right
```

---

## Typical Use Cases

- Send shared links from Home Assistant automations to a RelayTV screen
- Launch temporary doorbell or announcement media, then resume previous playback
- Display overlay messages on TVs around the home
- Add RelayTV as a dashboard-accessible media target
- Keep multiple RelayTV devices available in one Home Assistant setup
- Start synchronized playback across more than one RelayTV screen


---

## Companion Projects

- RelayTV server: https://github.com/mcgeezy/relaytv
- RelayTV Android app: https://github.com/mcgeezy/relaytv-android

### Planned / work in progress

- iPhone companion app
- Continued multi-device and automation improvements
- Ongoing UX polish across the RelayTV ecosystem

---

## Support The Project

If RelayTV is useful to you, donations help support continued development of the server, Home Assistant integration, Android app, and future companion apps.

Buy me a coffee:  
https://buymeacoffee.com/relaytv

---

## Compatibility

Validated against the RelayTV server API and current app route structure.

## License

Same license as the RelayTV core project:  
https://github.com/mcgeezy/relaytv
