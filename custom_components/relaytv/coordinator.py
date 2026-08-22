"""Coordinator for RelayTV status refresh and realtime push delivery."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .relaytv_api import RelayTVApi, RelayTVApiError, RelayTVAuthError

_LOGGER = logging.getLogger(__name__)

_POLL_INTERVAL_FALLBACK = timedelta(seconds=3)
_PUSH_CONNECT_TIMEOUT = 10
_PUSH_READ_TIMEOUT = 90
_PUSH_REFRESH_DEBOUNCE_SEC = 0.25
_PUSH_UPGRADE_INTERVAL_SEC = 300
_POSITION_UPDATE_BUCKET_SEC = 15
_REALTIME_SUBPROTOCOL = "relaytv.realtime.v1"


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _rounded_int(value: Any) -> int | None:
    num = _as_float(value)
    if num is None:
        return None
    return int(round(num))


def _position_bucket(data: dict[str, Any]) -> int | None:
    position = _as_float(data.get("position"))
    if position is None:
        return None
    if data.get("playing") and not data.get("paused"):
        return int(position // _POSITION_UPDATE_BUCKET_SEC)
    return int(round(position))


def _extract_media_fields(data: dict[str, Any]) -> tuple[str, str, str]:
    now_playing = data.get("now_playing")
    np = now_playing if isinstance(now_playing, dict) else {}

    title = str(np.get("title") or np.get("name") or data.get("title") or "")
    url = str(np.get("url") or np.get("input") or data.get("url") or "")
    thumbnail = str(
        np.get("thumbnail_local")
        or np.get("thumbnail")
        or np.get("thumb")
        or np.get("image")
        or np.get("art")
        or np.get("poster")
        or data.get("thumbnail_local")
        or data.get("thumbnail")
        or data.get("image")
        or data.get("art")
        or ""
    )
    return title, url, thumbnail


def _material_state_view(data: dict[str, Any] | None) -> tuple[Any, ...] | None:
    """Return a compact HA-visible state signature for deduplicating SSE updates."""
    if not isinstance(data, dict):
        return None

    title, url, thumbnail = _extract_media_fields(data)
    has_now_playing = data.get("has_now_playing")
    if has_now_playing is None:
        has_now_playing = bool(url or title)
    playing = bool(data.get("playing"))

    return (
        str(data.get("state") or ""),
        playing,
        bool(data.get("paused")),
        int(data.get("queue_length") or 0),
        bool(has_now_playing),
        _rounded_int(data.get("duration")),
        _position_bucket(data),
        _rounded_int(data.get("volume")) if playing else None,
        (None if data.get("mute") is None else bool(data.get("mute"))) if playing else None,
        title,
        url,
        thumbnail,
    )


def _apply_if_material_change(
    coordinator: "RelayTVCoordinator",
    payload: dict[str, Any],
) -> bool:
    """Update coordinator data only when HA-visible state materially changed."""
    if _material_state_view(coordinator.data) == _material_state_view(payload):
        return False
    coordinator.note_position_update(payload)
    coordinator.async_set_updated_data(payload)
    return True


def _merge_playback_snapshot(current: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Overlay compact playback-state fields onto the last full status payload."""
    if not isinstance(current, dict):
        return None

    merged = dict(current)
    merged.update(payload)
    return merged


class RelayTVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """RelayTV coordinator using WebSocket, SSE, then HTTP polling."""

    def __init__(self, hass: HomeAssistant, api: RelayTVApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="RelayTV status",
            update_interval=_POLL_INTERVAL_FALLBACK,
        )
        self.api = api
        self._push_task: asyncio.Task[None] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._push_enabled = False
        self._push_generation = 0
        self._active_transport: str | None = None
        self._active_connection: Any | None = None
        self._last_sequence = 0
        self.position_updated_at: datetime | None = None
        self._position_signature: tuple[Any, ...] | None = None

    @property
    def active_transport(self) -> str | None:
        """Return the currently healthy push transport for diagnostics."""
        return self._active_transport

    def note_position_update(self, data: dict[str, Any] | None) -> None:
        """Record when the reported playback position last changed.

        async_set_updated_data never stamps last_update_success_time, so the
        coordinator keeps its own timestamp for media_position_updated_at.
        """
        payload = data if isinstance(data, dict) else {}
        signature = (
            _as_float(payload.get("position")),
            bool(payload.get("playing")),
            bool(payload.get("paused")),
        )
        if signature != self._position_signature:
            self._position_signature = signature
            self.position_updated_at = dt_util.utcnow()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.get_status()
        except RelayTVAuthError as err:
            raise ConfigEntryAuthFailed from err
        except RelayTVApiError as err:
            raise UpdateFailed(str(err)) from err
        self.note_position_update(status)
        return status

    async def async_start(self) -> None:
        """Start the owned realtime transport task."""
        if self._push_task and not self._push_task.done():
            return
        self._push_generation += 1
        self._last_sequence = 0
        generation = self._push_generation
        self._push_task = asyncio.create_task(
            self._async_push_loop(generation),
            name="relaytv-realtime-push",
        )

    async def async_stop(self) -> None:
        """Stop background tasks owned by the coordinator."""
        self._push_generation += 1
        tasks = [task for task in (self._refresh_task, self._push_task) if task is not None]
        self._refresh_task = None
        self._push_task = None
        connection = self._active_connection
        self._active_connection = None
        for task in tasks:
            task.cancel()
        if connection is not None:
            try:
                closed = connection.close()
                if inspect.isawaitable(closed):
                    await closed
            except Exception:
                _LOGGER.debug("RelayTV push connection close failed", exc_info=True)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._set_push_enabled(False)

    async def async_restart(self) -> None:
        """Reconnect push delivery, used after base URL changes."""
        await self.async_stop()
        await self.async_start()

    def _owns_generation(self, generation: int) -> bool:
        return generation == self._push_generation

    def _set_push_enabled(
        self,
        enabled: bool,
        *,
        transport: str | None = None,
        generation: int | None = None,
    ) -> None:
        if generation is not None and not self._owns_generation(generation):
            return
        next_transport = transport if enabled else None
        if self._push_enabled == enabled and self._active_transport == next_transport:
            return
        self._push_enabled = enabled
        self._active_transport = next_transport
        self.update_interval = None if enabled else _POLL_INTERVAL_FALLBACK
        self._async_unsub_refresh()
        if not enabled and self._listeners:
            DataUpdateCoordinator._schedule_refresh(self)
        _LOGGER.debug(
            "RelayTV push %s for %s (transport=%s)",
            "enabled" if enabled else "disabled",
            self.api.base_url,
            next_transport,
        )

    def _schedule_debounced_refresh(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return

        async def _delayed_refresh() -> None:
            try:
                await asyncio.sleep(_PUSH_REFRESH_DEBOUNCE_SEC)
                await self.async_request_refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("RelayTV push-triggered refresh failed", exc_info=True)

        self._refresh_task = asyncio.create_task(_delayed_refresh())

    async def _async_dispatch_event(
        self,
        event_name: str | None,
        payload: Any,
        *,
        generation: int | None = None,
    ) -> None:
        if generation is not None and not self._owns_generation(generation):
            return
        if not event_name and isinstance(payload, dict):
            event_name = str(payload.get("type") or "").strip() or None
        if not event_name:
            return

        if event_name == "status":
            if isinstance(payload, dict):
                _apply_if_material_change(self, payload)
            else:
                self._schedule_debounced_refresh()
            return

        if event_name == "playback":
            if isinstance(payload, dict):
                merged = _merge_playback_snapshot(self.data, payload)
                if merged is not None:
                    _apply_if_material_change(self, merged)
                else:
                    self._schedule_debounced_refresh()
            else:
                self._schedule_debounced_refresh()
            return

        if event_name in ("queue", "jellyfin"):
            self._schedule_debounced_refresh()
            return

        if event_name == "hello":
            self._schedule_debounced_refresh()
            return

        if event_name == "ping":
            return

        _LOGGER.debug("Ignoring unsupported RelayTV push event %s", event_name)

    async def _async_dispatch_sse(
        self,
        event_name: str | None,
        data_lines: list[str],
        *,
        generation: int,
    ) -> None:
        if not data_lines and not event_name:
            return
        raw = "\n".join(data_lines).strip()
        if raw:
            try:
                payload: Any = json.loads(raw)
            except Exception:
                _LOGGER.debug("Ignoring non-JSON RelayTV SSE payload for %s: %r", event_name, raw)
                return
        else:
            payload = {}
        await self._async_dispatch_event(event_name, payload, generation=generation)

    def _record_sequence(self, sequence: Any, *, generation: int) -> None:
        if not self._owns_generation(generation):
            return
        try:
            next_sequence = int(sequence or 0)
        except (TypeError, ValueError):
            return
        if next_sequence <= 0:
            return
        if self._last_sequence > 0 and next_sequence > self._last_sequence + 1:
            self._schedule_debounced_refresh()
        self._last_sequence = max(self._last_sequence, next_sequence)

    async def _async_websocket_once(self, generation: int, config: dict[str, Any]) -> bool:
        path = str(config.get("ui") or "/ui/ws")
        subprotocol = str(config.get("subprotocol") or _REALTIME_SUBPROTOCOL)
        if subprotocol != _REALTIME_SUBPROTOCOL:
            _LOGGER.debug("RelayTV advertised unsupported WebSocket subprotocol %s", subprotocol)
            return False
        healthy = False
        socket = None
        try:
            socket = await asyncio.wait_for(
                self.api.session.ws_connect(
                    self.api.websocket_url_for(path),
                    protocols=[subprotocol],
                    headers=self.api.auth_headers,
                    timeout=aiohttp.ClientWSTimeout(ws_close=_PUSH_CONNECT_TIMEOUT),
                ),
                timeout=_PUSH_CONNECT_TIMEOUT,
            )
            if not self._owns_generation(generation):
                return False
            self._active_connection = socket
            if socket.protocol != subprotocol:
                raise RelayTVApiError("RelayTV did not negotiate the realtime WebSocket protocol")

            received_hello = False
            while self._owns_generation(generation):
                message = await asyncio.wait_for(socket.receive(), timeout=_PUSH_READ_TIMEOUT)
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        envelope = json.loads(message.data)
                    except Exception:
                        _LOGGER.debug("Ignoring non-JSON RelayTV WebSocket message")
                        continue
                    if not isinstance(envelope, dict) or envelope.get("version") != 1:
                        raise RelayTVApiError("RelayTV sent an unsupported realtime envelope")
                    event_name = str(envelope.get("event") or "").strip()
                    payload = envelope.get("data")
                    if not received_hello:
                        if event_name != "hello" or not isinstance(payload, dict):
                            raise RelayTVApiError("RelayTV WebSocket did not begin with hello")
                        if payload.get("protocol_version") != 1:
                            raise RelayTVApiError("RelayTV WebSocket hello version is unsupported")
                        received_hello = True
                        self._last_sequence = 0
                        healthy = True
                        self._set_push_enabled(True, transport="websocket", generation=generation)
                    self._record_sequence(envelope.get("sequence"), generation=generation)
                    await self._async_dispatch_event(event_name, payload, generation=generation)
                    continue
                if message.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    break
                if message.type == aiohttp.WSMsgType.ERROR:
                    raise RelayTVApiError("RelayTV WebSocket receive failed")
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.debug("RelayTV WebSocket disconnected for %s", self.api.base_url, exc_info=True)
        finally:
            if self._active_connection is socket:
                self._active_connection = None
            if socket is not None:
                try:
                    await socket.close()
                except Exception:
                    _LOGGER.debug("RelayTV WebSocket close failed", exc_info=True)
            self._set_push_enabled(False, generation=generation)
        return healthy

    async def _async_sse_once(
        self,
        generation: int,
        config: dict[str, Any],
        *,
        upgrade_after: float | None,
    ) -> bool:
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            **self.api.auth_headers,
        }
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=_PUSH_CONNECT_TIMEOUT,
            sock_read=_PUSH_READ_TIMEOUT,
        )
        healthy = False
        response = None

        async def _consume_response(resp: aiohttp.ClientResponse) -> None:
            nonlocal healthy
            self._set_push_enabled(True, transport="sse", generation=generation)
            healthy = True
            event_name: str | None = None
            data_lines: list[str] = []
            async for raw_line in resp.content:
                if not self._owns_generation(generation):
                    return
                line = raw_line.decode("utf-8", "ignore").rstrip("\r\n")
                if line == "":
                    await self._async_dispatch_sse(event_name, data_lines, generation=generation)
                    event_name = None
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                field, _, value = line.partition(":")
                if value.startswith(" "):
                    value = value[1:]
                if field == "event":
                    event_name = value.strip() or None
                elif field == "data":
                    data_lines.append(value)
            if event_name or data_lines:
                await self._async_dispatch_sse(event_name, data_lines, generation=generation)

        try:
            path = str(config.get("ui") or "/ui/events")
            async with self.api.session.get(self.api.url_for(path), headers=headers, timeout=timeout) as response:
                if not self._owns_generation(generation):
                    return False
                self._active_connection = response
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Unexpected RelayTV SSE response: {response.status}",
                        headers=response.headers,
                    )
                if upgrade_after is None:
                    await _consume_response(response)
                else:
                    try:
                        async with asyncio.timeout(upgrade_after):
                            await _consume_response(response)
                    except TimeoutError:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.debug("RelayTV SSE disconnected for %s", self.api.base_url, exc_info=True)
        finally:
            if self._active_connection is response:
                self._active_connection = None
            self._set_push_enabled(False, generation=generation)
        return healthy

    async def _async_push_loop(self, generation: int) -> None:
        backoff = 1.0
        capabilities: dict[str, Any] | None = None
        while self._owns_generation(generation):
            if capabilities is None:
                try:
                    capabilities = await self.api.get_realtime_capabilities()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.debug("RelayTV realtime discovery failed for %s", self.api.base_url, exc_info=True)
                    self._set_push_enabled(False, generation=generation)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 30.0)
                    continue
                if not self._owns_generation(generation):
                    return

            websocket = capabilities.get("websocket")
            sse = capabilities.get("sse")
            websocket_config = websocket if isinstance(websocket, dict) else {}
            sse_config = sse if isinstance(sse, dict) else {}
            websocket_enabled = (
                capabilities.get("protocol_version") == 1
                and websocket_config.get("enabled") is True
            )
            sse_enabled = sse_config.get("enabled") is True
            cycle_was_healthy = False

            if websocket_enabled and self._owns_generation(generation):
                cycle_was_healthy = await self._async_websocket_once(generation, websocket_config)
            if sse_enabled and self._owns_generation(generation):
                sse_healthy = await self._async_sse_once(
                    generation,
                    sse_config,
                    upgrade_after=_PUSH_UPGRADE_INTERVAL_SEC if websocket_enabled else None,
                )
                cycle_was_healthy = cycle_was_healthy or sse_healthy

            self._set_push_enabled(False, generation=generation)
            if not self._owns_generation(generation):
                return
            await asyncio.sleep(backoff)
            backoff = 1.0 if cycle_was_healthy else min(backoff * 2.0, 30.0)
