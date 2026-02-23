# RelayTV – Home Assistant Integration

RelayTV transforms Home Assistant into a **programmable local media automation engine**.

It exposes your RelayTV server as a `media_player` (plus services), supports queue-based playback, and makes it easy to drive **local HDMI playback** from automations (doorbells, sensors, schedules, scenes, and AI).

> Tip: The YAML below uses the `relaytv.*` service names as examples. If your integration exposes slightly different names/fields, keep the **automation patterns** and adjust the service calls accordingly.

---

# 🚀 What RelayTV Enables Today

## 🎬 Media Player Control
- `media_player` entity support
- Play / pause / stop / seek / volume
- Queue management
- Resume playback support (where implemented)
- Local HDMI playback
- yt-dlp powered “smart URL” stream resolution

---

# ⭐ Key Mobile UX Feature: “Share to Home Assistant” → Play / Enqueue

One of the best day-to-day workflows is using your phone like a “remote link picker”:

1. On iOS/Android, **share a link** (YouTube, Twitch, a direct stream URL, etc.)
2. Choose **Home Assistant** from the share sheet
3. Home Assistant fires an event (`mobile_app.share`) containing the shared `url` or `text`
4. An automation can then **play now** or **enqueue** on RelayTV

This feels *incredible* in practice: you browse normally on your phone, tap Share, and your TV starts playing.

> Pro tip: Use the HA UI automation editor to duplicate this automation into variants:
> - “Share → Play Now (Living Room)"
> - “Share → Enqueue (Bedroom)"
> - “Share → Ask which TV” (roadmap: actionable notification picker)

---

# 🔵 Practical Automation Use Cases (Available Now)

- 🚪 Doorbell / camera pop on the TV
- ⏰ Morning video alarm clock
- 🌙 Bedtime routines (relaxing queue + auto stop)
- 🏠 Home/Away/Movie mode scenes that change what’s on screen
- 📺 Queue-based “experiences” (workouts, parties, timers, intros)
- 📲 **Mobile Share → Play/Enqueue** from iOS/Android browsing (see below)

---

# 🟢 Creative & Fun Automation Ideas

- 👻 Late-night motion jump scares
- 🧟 Halloween mode (seasonal triggers + ambient loops)
- 🐶 Dog cam on bark detection
- 🎉 Birthday surprise mode
- 🎮 Easter-egg triggers (sensor patterns launch hidden clips)

---

# 🔴 Advanced Home Automation Scenarios

- 🤖 AI-powered announcements (TTS + relevant clip)
- 🌧 Weather-based media (radar, warnings, checklist videos)
- 📈 Energy monitoring visualizations (play alert/graph clip)
- 🛡 “Command center” camera rotation on alarm events
- 📰 AI daily digest queue (headlines + summaries)

---

# 🧠 Core Services (Examples)

| Service | Description |
|--------|-------------|
| `relaytv.play_now` | Immediately plays a URL |
| `relaytv.enqueue` | Adds URL to queue |
| `relaytv.smart_url` | Resolves URL via yt-dlp (when applicable) |
| `relaytv.clear_queue` | Clears current queue |
| `relaytv.seek` | Seek to a time position |
| `relaytv.volume_set` | Adjust volume |

---

# ✅ Automation Examples (YAML)

## 0) Drop-in: Share to Home Assistant → Play Now (Mobile)

**What it does:** When you share a link to the Home Assistant app, this plays it immediately on RelayTV.

- Trigger: `mobile_app.share`
- Uses: `trigger.event.data.url` (preferred) or `trigger.event.data.text`

```yaml
alias: RelayTV - Mobile Share -> Play Now
mode: queued
trigger:
  - platform: event
    event_type: mobile_app.share
action:
  - variables:
      shared_url: >-
        {{ trigger.event.data.url
           if trigger.event.data.url is defined
           else (trigger.event.data.text if trigger.event.data.text is defined else '') }}
  - condition: template
    value_template: "{{ shared_url | length > 0 }}"
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "{{ shared_url }}"
  - service: notify.notify
    data:
      title: "RelayTV"
      message: "Playing: {{ shared_url }}"
```

### Variant: Mobile Share → Enqueue Instead of Play Now

```yaml
alias: RelayTV - Mobile Share -> Enqueue
mode: queued
trigger:
  - platform: event
    event_type: mobile_app.share
action:
  - variables:
      shared_url: >-
        {{ trigger.event.data.url
           if trigger.event.data.url is defined
           else (trigger.event.data.text if trigger.event.data.text is defined else '') }}
  - condition: template
    value_template: "{{ shared_url | length > 0 }}"
  - service: relaytv.enqueue
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "{{ shared_url }}"
  - service: notify.notify
    data:
      title: "RelayTV"
      message: "Enqueued: {{ shared_url }}"
```

---

## 1) Doorbell → Show Front Door Camera (RTSP)

```yaml
alias: RelayTV - Doorbell Camera Pop
mode: single
trigger:
  - platform: state
    entity_id: binary_sensor.front_door_ding
    to: "on"
action:
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "rtsp://user:pass@10.0.55.10:554/stream1"
  - service: relaytv.volume_set
    target:
      entity_id: media_player.relaytv_living_room
    data:
      volume_level: 0.55
```

## 2) Morning Video Alarm Clock (Playlist + Lights)

```yaml
alias: RelayTV - Morning Video Alarm
mode: single
trigger:
  - platform: time
    at: "06:45:00"
condition:
  - condition: state
    entity_id: person.mark
    state: "home"
action:
  - service: light.turn_on
    target:
      entity_id: light.bedroom
    data:
      brightness_pct: 10
  - delay: "00:00:05"
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_bedroom
    data:
      url: "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
  - service: relaytv.volume_set
    target:
      entity_id: media_player.relaytv_bedroom
    data:
      volume_level: 0.25
  - delay: "00:05:00"
  - service: light.turn_on
    target:
      entity_id: light.bedroom
    data:
      brightness_pct: 45
```

## 3) Late-Night Motion → Jump Scare (Fun Mode)

```yaml
alias: RelayTV - Late Night Jump Scare
mode: single
trigger:
  - platform: state
    entity_id: binary_sensor.hall_motion
    to: "on"
condition:
  - condition: time
    after: "01:00:00"
    before: "04:00:00"
action:
  - service: relaytv.volume_set
    target:
      entity_id: media_player.relaytv_living_room
    data:
      volume_level: 0.85
  - service: light.turn_on
    target:
      entity_id: light.hallway
    data:
      brightness_pct: 100
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "https://www.youtube.com/watch?v=YOUR_JUMPSCARE_CLIP"
  - delay: "00:00:12"
  - service: light.turn_off
    target:
      entity_id: light.hallway
```

## 4) Alarm Trigger → “Command Center” Camera Rotation (Queue)

```yaml
alias: RelayTV - Alarm Command Center
mode: restart
trigger:
  - platform: state
    entity_id: alarm_control_panel.house
    to: "triggered"
action:
  - service: relaytv.clear_queue
    target:
      entity_id: media_player.relaytv_living_room
  - service: relaytv.enqueue
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "rtsp://user:pass@10.0.55.10:554/front"
  - service: relaytv.enqueue
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "rtsp://user:pass@10.0.55.10:554/driveway"
  - service: relaytv.enqueue
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "rtsp://user:pass@10.0.55.10:554/backyard"
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "rtsp://user:pass@10.0.55.10:554/front"
```

## 5) Party Mode Script (Intro Clip + Playlist)

Create this as a **Script** in HA (Settings → Automations & Scenes → Scripts).

```yaml
party_mode_relaytv:
  alias: Party Mode (RelayTV)
  mode: single
  sequence:
    - service: relaytv.clear_queue
      target:
        entity_id: media_player.relaytv_living_room
    - service: relaytv.enqueue
      target:
        entity_id: media_player.relaytv_living_room
      data:
        url: "https://www.youtube.com/watch?v=YOUR_INTRO_CLIP"
    - service: relaytv.enqueue
      target:
        entity_id: media_player.relaytv_living_room
      data:
        url: "https://www.youtube.com/playlist?list=YOUR_PARTY_PLAYLIST"
    - service: relaytv.volume_set
      target:
        entity_id: media_player.relaytv_living_room
      data:
        volume_level: 0.65
    - service: relaytv.play_now
      target:
        entity_id: media_player.relaytv_living_room
      data:
        url: "https://www.youtube.com/watch?v=YOUR_INTRO_CLIP"
```

## 6) “AI Announcement” Pattern (TTS + Video)

```yaml
alias: RelayTV - AI Announcement Pattern
mode: single
trigger:
  - platform: state
    entity_id: binary_sensor.garage_door_open_too_long
    to: "on"
action:
  - service: tts.speak
    data:
      media_player_entity_id: media_player.kitchen_speaker
      message: "Garage door has been open for a while."
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "https://www.youtube.com/watch?v=YOUR_ALERT_CLIP"
```

## 7) Energy Spike → Alert Clip + Reduce Loads

```yaml
alias: RelayTV - Energy Spike Alert
mode: single
trigger:
  - platform: numeric_state
    entity_id: sensor.home_power_kw
    above: 8.0
    for: "00:02:00"
action:
  - service: relaytv.play_now
    target:
      entity_id: media_player.relaytv_living_room
    data:
      url: "https://www.youtube.com/watch?v=YOUR_POWER_ALERT_CLIP"
  - service: switch.turn_off
    target:
      entity_id:
        - switch.space_heater
        - switch.shop_fan
```

---

# 🛣 Roadmap (Future Capabilities)

## 🔔 Interrupt + Resume Service
Temporarily interrupt playback for alerts, then auto-resume prior content.

## 🪟 Overlay Mode
Display notification banners without stopping playback.

## 🔄 Multi-Screen Sync
Synchronize playback across multiple RelayTV servers (perfect for whole-home announcements).

## 🖼 Snapshot Previews
Capture/preview before switching content (helps with camera pops).

## 🎛 Sensor → Stream Mapping UI
Map motion/doorbell sensors to streams directly in the integration options UI (no YAML required).

## 🧠 AI Clip Generator
Generate short clips (image + TTS + theme) for alerts, seasons, and events.

## 📢 Smart Alert Replacement
Insert custom “house announcements” during downtime or between queued items.

---

# 📦 Installation

## HACS
1. Add as Custom Repository (Integration)
2. Install
3. Restart Home Assistant
4. Add Integration
5. Configure server address

## Manual
Copy `custom_components/relaytv` into:

```text
/ config / custom_components / relaytv
```

Restart Home Assistant.

---

# 🔐 License
TBD
