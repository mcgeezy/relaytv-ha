## 0.2.3
- Fix HA seek bar by providing media_position_updated_at.
- Add entity_picture support (thumbnail) when RelayTV status includes artwork fields.
- Improve seek/volume command payload compatibility.

# Changelog

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
