# RelayTV HA 0.5.0

This release gives RelayTV media-player entities faster, more resilient local
state updates by preferring the server's versioned WebSocket transport. It
requires Home Assistant 2026.7 or newer.

## Highlights

- Automatically prefers RelayTV's versioned `/ui/ws` local WebSocket.
- Falls back to `/ui/events` SSE and then adaptive `/status` polling when a
  server, proxy, or network path cannot sustain WebSocket connectivity.
- Performs an authoritative refresh after sequence gaps, reconnects, and
  RelayTV server restarts.
- Keeps only the active configuration generation capable of publishing state
  during unload, reconfiguration, or server switching.
- Reports `local_push` to Home Assistant while push is supported, without
  dropping compatibility with older RelayTV servers.
- Keeps optional bearer authentication out of URLs and applies it consistently
  to capability discovery and both push transports.

## Compatibility and deployment

- No configuration migration or breaking change is required.
- RelayTV servers with realtime protocol version 1 use WebSocket first.
- Older servers and servers returning `404` for capability discovery continue
  through the existing SSE and polling paths.
- Reverse proxies should permit WebSocket upgrades for `/ui/ws`; blocking them
  is safe because the integration falls back automatically.
- The minimum supported Home Assistant version remains 2026.7.

Breaking changes: None.

## Verification

- Ruff and the complete pytest suite pass.
- Coverage includes capability discovery, WebSocket framing, sequence gaps,
  WS-to-SSE-to-poll fallback, bearer headers, unload/reconfiguration ownership,
  and compatibility with legacy RelayTV servers.
- The integration was deployed and verified against live NUC and Raspberry Pi
  RelayTV servers using WebSocket state updates.

## Upgrade

Install 0.5.0 through HACS and restart Home Assistant. Existing entries and
optional API tokens are reused without reconfiguration. The HACS archive
remains flat, with `manifest.json` directly at the archive root as required for
`/config/custom_components/relaytv/` installation.
