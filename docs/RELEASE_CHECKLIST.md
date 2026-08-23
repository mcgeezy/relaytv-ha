# RelayTV Home Assistant Release Checklist

Use this checklist before publishing a HACS release of the RelayTV integration.

## Automated readiness

1. Confirm `custom_components/relaytv/manifest.json`, `RELEASE_NOTES.md`, and
   the intended release version agree.
2. Run the local quality gates:

   ```bash
   python -m pip install --requirement requirements_test.txt
   ruff check custom_components tests
   python -m pytest -q
   git diff --check
   ```

3. Confirm the GitHub test and HACS validation workflows pass.
4. Confirm the release archive is flat: `manifest.json` must be at the root of
   `relaytv.zip`, matching `/config/custom_components/relaytv/`.

## Connectivity and compatibility

1. With a current RelayTV server, confirm the coordinator selects `/ui/ws` and
   media state, position, queue hints, and reconnect refreshes remain correct.
2. Block WebSocket and confirm `/ui/events` SSE becomes healthy. Block both
   push transports and confirm three-second `/status` polling activates without
   clearing the last valid state during the reconnect grace period.
3. Configure a server that returns `404` for `/realtime/capabilities`; confirm
   the integration uses legacy SSE/polling and discovers WebSocket after the
   server is upgraded without requiring a Home Assistant restart.
4. Verify direct HTTP and proxied HTTPS RelayTV URLs. The proxy must support
   WebSocket upgrades for `/ui/ws`; failure must downgrade automatically rather
   than making the entity unavailable.
5. Verify both an unprotected server and a protected server. A valid optional
   token must authenticate all transports and writes through headers, while a
   missing or rejected token must produce the expected reauthentication or
   service error without appearing in URLs, entity state, diagnostics, or logs.

To observe transport selection during live verification, temporarily enable
debug logging for `custom_components.relaytv`. The coordinator logs transitions
with `transport=websocket`, `transport=sse`, or a disabled push state. Remove
debug logging after verification.

## Lifecycle and live verification

1. Reload and unload the integration while push is connected; retired tasks
   must close and must not publish or schedule reconnects.
2. Change the base URL, display name, and optional token through integration
   options. Confirm only the replacement entry/server publishes state.
3. Restart RelayTV, restart Home Assistant, and simulate a prolonged RelayTV
   outage. Confirm availability and authoritative state recover without manual
   reload.
4. Configure multiple RelayTV entries and verify services, sidebar targeting,
   entities, and reconnects remain isolated to the selected device.
5. Exercise playback, pause, seek, volume, queue mutation, snapshot, overlay,
   and one upload service against a live server.
6. Confirm the integration still reports `local_push` metadata and that the
   existing configuration requires no migration.

## Publication

1. Review release notes for user impact, operator impact, compatibility,
   breaking changes, and tests run.
2. Tag only the reviewed release commit according to the repository release
   process.
3. Confirm the GitHub Release contains `relaytv.zip` and that a clean HACS
   install plus Home Assistant restart loads the integration successfully.
