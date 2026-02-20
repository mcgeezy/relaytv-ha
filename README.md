# RelayTV Panel (Home Assistant)

A minimal Home Assistant integration that adds a **RelayTV** sidebar panel (iframe) pointing at your RelayTV instance.

- **Domain:** `relaytv`
- **Type:** Sidebar panel (iframe)
- **Entities:** None (RelayTV remains the control surface)

## Install via HACS (Custom Repository)

1. In Home Assistant, go to **HACS → Integrations**
2. Open the menu (⋮) → **Custom repositories**
3. Add this repository URL, category **Integration**
4. Install **RelayTV Panel**
5. Restart Home Assistant
6. Add the integration: **Settings → Devices & Services → Add Integration → RelayTV Panel**
7. Enter your RelayTV base URL (example: `http://relaytv-host:8787`)

## Manual Install

Copy `custom_components/relaytv` into:

```
/config/custom_components/relaytv
```

Restart Home Assistant, then add the integration from the UI.

## Configuration

During setup you provide:

- **RelayTV base URL** (required)

Options allow:

- Sidebar title
- Sidebar icon (MDI)
- Sidebar path (URL slug)

## Notes

- This integration does **not** create a `media_player` entity.
- It embeds the RelayTV UI at `/ui` via iframe.

## Versioning

This repo uses semantic versioning.
Current version: **v0.1.0**

## License

TBD
