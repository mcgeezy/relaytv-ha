# RelayTV -- Home Assistant Integration

The RelayTV Home Assistant integration adds a sidebar panel that embeds
the RelayTV web UI directly inside Home Assistant.

This integration does **not** create media entities or mirror playback
state into HA.\
RelayTV remains the authoritative playback engine and UI.

------------------------------------------------------------------------

## What This Integration Does

-   Adds a dedicated **RelayTV** sidebar panel
-   Embeds the RelayTV `/ui` interface via iframe
-   Allows control from desktop or mobile HA apps
-   Keeps RelayTV fully self-contained

------------------------------------------------------------------------

## Requirements

-   A running RelayTV instance accessible from Home Assistant
-   RelayTV reachable via HTTP (e.g. `http://relaytv-host:8787`)
-   Home Assistant 2023.x or newer recommended

------------------------------------------------------------------------

## Installation (Manual)

1.  Copy the `relaytv_webui` folder into:

```{=html}
<!-- -->
```
    /config/custom_components/

So it becomes:

    /config/custom_components/relaytv_webui/

2.  Restart Home Assistant.

3.  Go to:

```{=html}
<!-- -->
```
    Settings → Devices & Services → Add Integration

4.  Search for **RelayTV Web UI Panel**.

5.  Enter the base URL where RelayTV is reachable from Home Assistant.

Example:

    http://relaytv-host:8787

------------------------------------------------------------------------

## Configuration Options

After installation, you can configure:

  Option          Description
  --------------- ----------------------------
  Sidebar title   Display name in HA sidebar
  Sidebar icon    Any valid MDI icon
  Sidebar path    URL slug used in HA

------------------------------------------------------------------------

## Example Configuration

Base URL:

    http://192.168.1.50:8787

Custom sidebar path:

    relaytv

Resulting HA path:

    http://homeassistant.local:8123/relaytv

------------------------------------------------------------------------

## How It Works

The integration registers a built-in Home Assistant **iframe panel**.

No polling, no entities, no media_player integration.

RelayTV's own API and state model remain independent and
server-authoritative.

------------------------------------------------------------------------

## Security Notes

-   RelayTV should only be exposed on trusted networks.
-   If accessing via HTTPS reverse proxy, use the proxied URL as the
    base URL.
-   Ensure CORS and authentication policies match your deployment
    environment.

------------------------------------------------------------------------

## Recommended Deployment Pattern

For maximum reliability:

-   Run RelayTV in Docker
-   Bind-mount `/data` for persistent queue/history
-   Use stable and beta containers during upgrades
-   Point HA at the stable instance

------------------------------------------------------------------------

## Roadmap

Planned future enhancements:

-   Optional HA media_player entity bridge
-   Service calls for play/enqueue
-   WebSocket event push support
-   HACS compatibility

------------------------------------------------------------------------

## Support

If the panel fails to load:

1.  Verify RelayTV is reachable from the HA container
2.  Confirm the base URL is correct
3.  Check HA logs for integration load errors
4.  Confirm no mixed HTTP/HTTPS blocking issues

------------------------------------------------------------------------

**RelayTV --- A local-first media runtime for your television.**
