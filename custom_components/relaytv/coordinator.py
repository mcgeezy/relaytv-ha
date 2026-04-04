"""Coordinator for RelayTV status refresh and UI event streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .relaytv_api import RelayTVApi

_LOGGER = logging.getLogger(__name__)

_POLL_INTERVAL_FALLBACK = timedelta(seconds=3)
_SSE_CONNECT_TIMEOUT = 10
_SSE_READ_TIMEOUT = 90
_SSE_REFRESH_DEBOUNCE_SEC = 0.25


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

    return (
        str(data.get("state") or ""),
        bool(data.get("playing")),
        bool(data.get("paused")),
        int(data.get("queue_length") or 0),
        bool(has_now_playing),
        _rounded_int(data.get("position")),
        _rounded_int(data.get("duration")),
        _rounded_int(data.get("volume")),
        None if data.get("mute") is None else bool(data.get("mute")),
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
    """Hybrid RelayTV coordinator using /status plus /ui/events."""

    def __init__(self, hass: HomeAssistant, api: RelayTVApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="RelayTV status",
            update_interval=_POLL_INTERVAL_FALLBACK,
        )
        self.api = api
        self._sse_task: asyncio.Task[None] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._sse_enabled = False

    async def _async_update_data(self) -> dict[str, Any]:
        data = await self.api.get_status()
        if data is None:
            raise UpdateFailed("Unable to fetch RelayTV status")
        return data

    async def async_start(self) -> None:
        """Start the background SSE listener."""
        if self._sse_task and not self._sse_task.done():
            return
        self._sse_task = asyncio.create_task(self._async_sse_loop())

    async def async_stop(self) -> None:
        """Stop background tasks owned by the coordinator."""
        tasks = [task for task in (self._refresh_task, self._sse_task) if task is not None]
        self._refresh_task = None
        self._sse_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._set_sse_enabled(False)

    async def async_restart(self) -> None:
        """Reconnect the SSE stream, used after base URL changes."""
        await self.async_stop()
        await self.async_start()

    def _set_sse_enabled(self, enabled: bool) -> None:
        if self._sse_enabled == enabled:
            return
        self._sse_enabled = enabled
        self.update_interval = None if enabled else _POLL_INTERVAL_FALLBACK
        self._async_unsub_refresh()
        if not enabled and self._listeners:
            DataUpdateCoordinator._schedule_refresh(self)
        _LOGGER.debug("RelayTV SSE %s for %s", "enabled" if enabled else "disabled", self.api.base_url)

    def _schedule_debounced_refresh(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return

        async def _delayed_refresh() -> None:
            try:
                await asyncio.sleep(_SSE_REFRESH_DEBOUNCE_SEC)
                await self.async_request_refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("RelayTV SSE-triggered refresh failed", exc_info=True)

        self._refresh_task = asyncio.create_task(_delayed_refresh())

    async def _async_dispatch_event(self, event_name: str | None, data_lines: list[str]) -> None:
        if not data_lines and not event_name:
            return

        raw = "\n".join(data_lines).strip()
        payload: Any
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                _LOGGER.debug("Ignoring non-JSON RelayTV SSE payload for %s: %r", event_name, raw)
                return
        else:
            payload = {}

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
            if not isinstance(self.data, dict) or not self.last_update_success:
                self._schedule_debounced_refresh()
            return

        if event_name == "ping":
            return

        _LOGGER.debug("Ignoring unsupported RelayTV SSE event %s", event_name)

    async def _async_sse_loop(self) -> None:
        backoff = 1.0
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        while True:
            try:
                timeout = aiohttp.ClientTimeout(
                    total=None,
                    connect=_SSE_CONNECT_TIMEOUT,
                    sock_read=_SSE_READ_TIMEOUT,
                )
                async with self.api.session.get(self.api.url_for("ui/events"), headers=headers, timeout=timeout) as resp:
                    if resp.status >= 400:
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=f"Unexpected RelayTV SSE response: {resp.status}",
                            headers=resp.headers,
                        )

                    self._set_sse_enabled(True)
                    backoff = 1.0
                    event_name: str | None = None
                    data_lines: list[str] = []

                    async for raw_line in resp.content:
                        line = raw_line.decode("utf-8", "ignore").rstrip("\r\n")
                        if line == "":
                            await self._async_dispatch_event(event_name, data_lines)
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
                        await self._async_dispatch_event(event_name, data_lines)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("RelayTV SSE loop disconnected for %s", self.api.base_url, exc_info=True)
            finally:
                self._set_sse_enabled(False)

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
