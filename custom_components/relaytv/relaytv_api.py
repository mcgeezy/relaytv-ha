"""RelayTV local HTTP API helper.

This integration targets the RelayTV server API documented in relaytv/docs/API.md.
We intentionally prefer the canonical endpoints:

- GET  /status
- GET  /ui/events
- POST /play
- POST /smart
- POST /enqueue
- POST /ingest/media
- POST /ingest/media/play
- POST /ingest/media/enqueue
- POST /next
- POST /pause | /resume | /toggle_pause
- POST /playback/play
- POST /seek_abs
- POST /volume
- POST /stop

The wrapper remains defensive around timeouts and JSON parsing.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
_UPLOAD_CHUNK_SIZE = 1024 * 1024


class RelayTVApiError(HomeAssistantError):
    """Base error returned by the RelayTV API."""


class RelayTVConnectionError(RelayTVApiError):
    """RelayTV could not be reached."""


class RelayTVAuthError(RelayTVApiError):
    """RelayTV rejected the configured API token."""


class RelayTVResponseError(RelayTVApiError):
    """RelayTV returned an unsuccessful response."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"RelayTV request failed ({status}): {detail}")
        self.status = status
        self.detail = detail


class RelayTVEndpointNotFound(RelayTVResponseError):
    """RelayTV does not provide a compatibility endpoint."""


def _join(base: str, path: str) -> str:
    base = (base or "").rstrip("/")
    path = (path or "").lstrip("/")
    return f"{base}/{path}" if path else base


async def _iter_file_chunks(file_path: Path):
    file_obj = await asyncio.to_thread(file_path.open, "rb")
    try:
        while True:
            chunk = await asyncio.to_thread(file_obj.read, _UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        await asyncio.to_thread(file_obj.close)


@dataclass
class RelayTVApi:
    """Small wrapper around RelayTV HTTP endpoints."""

    session: aiohttp.ClientSession
    base_url: str
    api_token: str = ""
    timeout_s: float = 8.0
    upload_timeout_s: float = 3600.0
    on_auth_failure: Callable[[], None] | None = None

    def url_for(self, path: str) -> str:
        """Build an absolute RelayTV URL for a relative API path."""
        return _join(self.base_url, path)

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return bearer authentication headers when a token is configured."""
        token = str(self.api_token or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def _raise_response_error(self, resp: aiohttp.ClientResponse) -> None:
        try:
            payload = await resp.json(content_type=None)
            detail = payload.get("detail") if isinstance(payload, dict) else payload
        except Exception:
            detail = await resp.text()
        message = str(detail or resp.reason or "request failed")[:500]
        if resp.status in (401, 403):
            if self.on_auth_failure is not None:
                self.on_auth_failure()
            raise RelayTVAuthError("RelayTV rejected the configured API token")
        if resp.status in (404, 405):
            raise RelayTVEndpointNotFound(resp.status, message)
        raise RelayTVResponseError(resp.status, message)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = self.url_for(path)
        try:
            async with asyncio.timeout(self.timeout_s):
                async with self.session.request(method, url, json=json, headers=self.auth_headers) as resp:
                    if resp.status >= 400:
                        await self._raise_response_error(resp)
                    try:
                        payload = await resp.json(content_type=None)
                        return payload if isinstance(payload, dict) else {"result": payload}
                    except Exception:
                        return {}
        except RelayTVApiError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise RelayTVConnectionError(f"Unable to communicate with RelayTV at {self.base_url}") from err

    async def _upload_media(
        self,
        path: str,
        *,
        endpoint: str,
        title: str | None = None,
    ) -> Optional[dict[str, Any]]:
        file_path = Path(path)
        url = self.url_for(endpoint)
        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        form = aiohttp.FormData()
        if title:
            form.add_field("title", title)

        try:
            form.add_field("file", _iter_file_chunks(file_path), filename=filename, content_type=content_type)
            async with asyncio.timeout(self.upload_timeout_s):
                async with self.session.post(url, data=form, headers=self.auth_headers) as resp:
                    if resp.status >= 400:
                        await self._raise_response_error(resp)
                    try:
                        payload = await resp.json(content_type=None)
                        return payload if isinstance(payload, dict) else {"result": payload}
                    except Exception:
                        return {}
        except RelayTVApiError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise RelayTVConnectionError(f"Unable to upload media to RelayTV at {self.base_url}") from err

    async def get_status(self) -> dict[str, Any]:
        """Fetch current playback/status."""
        return await self._request_json("GET", "status")

    async def validate(self) -> None:
        """Validate connectivity and write authentication without changing state."""
        await self.get_status()
        try:
            await self._request_json("POST", "auth/check", json={})
        except RelayTVEndpointNotFound:
            # Servers predating /auth/check are valid when their write guard is
            # disabled. Protected older servers reject this before route lookup.
            return

    async def smart_url(self, url: str) -> bool:
        """RelayTV one-button behavior (POST /smart)."""
        await self._request_json("POST", "smart", json={"url": url})
        return True

    async def play(self, url: str, *, use_ytdlp: bool | None = None, cec: bool | None = None) -> bool:
        """Immediate play; clears queue (POST /play)."""
        payload: dict[str, Any] = {"url": url}
        if use_ytdlp is not None:
            payload["use_ytdlp"] = bool(use_ytdlp)
        if cec is not None:
            payload["cec"] = bool(cec)
        await self._request_json("POST", "play", json=payload)
        return True

    async def enqueue(self, url: str) -> bool:
        """Add an item to the end of the queue (POST /enqueue)."""
        await self._request_json("POST", "enqueue", json={"url": url})
        return True

    async def upload_media(self, path: str, *, title: str | None = None) -> Optional[dict[str, Any]]:
        """Upload local media without queueing or playing (POST /ingest/media)."""
        return await self._upload_media(path, endpoint="ingest/media", title=title)

    async def upload_media_play(self, path: str, *, title: str | None = None) -> Optional[dict[str, Any]]:
        """Upload local media and start playback (POST /ingest/media/play)."""
        return await self._upload_media(path, endpoint="ingest/media/play", title=title)

    async def upload_media_enqueue(self, path: str, *, title: str | None = None) -> Optional[dict[str, Any]]:
        """Upload local media and enqueue it (POST /ingest/media/enqueue)."""
        return await self._upload_media(path, endpoint="ingest/media/enqueue", title=title)

    async def play_temporary(
        self,
        *,
        url: str,
        timeout_sec: float | None = None,
        volume_override: float | None = None,
        resume: bool = True,
        resume_mode: str = "auto",
    ) -> bool:
        payload: dict[str, Any] = {"url": url, "resume": resume, "resume_mode": resume_mode}
        if timeout_sec is not None:
            payload["timeout_sec"] = float(timeout_sec)
        if volume_override is not None:
            payload["volume_override"] = float(volume_override)
        await self._request_json("POST", "play_temporary", json=payload)
        return True

    async def overlay(
        self,
        *,
        text: str | None = None,
        duration: float | None = None,
        position: str | None = None,
        image_url: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {}
        if text:
            payload["text"] = text
        if duration is not None:
            payload["duration"] = float(duration)
        if position:
            payload["position"] = position
        if image_url:
            payload["image_url"] = image_url
        await self._request_json("POST", "overlay", json=payload)
        return True

    async def play_at(self, *, url: str, start_at: float) -> bool:
        payload = {"url": url, "start_at": float(start_at)}
        await self._request_json("POST", "play_at", json=payload)
        return True

    async def snapshot(self) -> Optional[dict[str, Any]]:
        try:
            return await self._request_json("POST", "snapshot", json={})
        except RelayTVEndpointNotFound:
            return await self._request_json("GET", "snapshot")

    async def next(self) -> bool:
        """Skip to the next queued item (POST /next)."""
        await self._request_json("POST", "next", json={})
        return True

    async def previous(self) -> bool:
        """Go to the previous item (POST /previous)."""
        await self._request_json("POST", "previous", json={})
        return True

    async def pause(self) -> bool:
        await self._request_json("POST", "pause", json={})
        return True

    async def resume(self) -> bool:
        await self._request_json("POST", "resume", json={})
        return True

    async def toggle_pause(self) -> bool:
        await self._request_json("POST", "toggle_pause", json={})
        return True

    async def stop(self) -> bool:
        await self._request_json("POST", "stop", json={})
        return True

    async def playback_play(self) -> bool:
        """User-facing Play semantics (POST /playback/play).

        RelayTV's server implements "TV remote" behavior here:
          - if mpv is running: toggle pause
          - else if session is closed: resume
          - else: play next queued item

        If the endpoint is missing (older servers), fall back to ensure_playing().
        """
        try:
            await self._request_json("POST", "playback/play", json={})
            return True
        except RelayTVEndpointNotFound:
            return await self.ensure_playing()

    async def seek_abs(self, sec: float) -> bool:
        """Seek to an absolute position in seconds (POST /seek_abs)."""
        try:
            sec_f = float(sec)
        except Exception:
            return False
        await self._request_json("POST", "seek_abs", json={"sec": sec_f})
        return True

    async def set_volume(self, level: Any) -> bool:
        """Set volume from HA's 0.0-1.0 slider to RelayTV's 0-100 scale."""
        try:
            v = float(level)
        except Exception:
            return False

        # Normalize
        if v <= 1.0:
            pct = v * 100.0
        else:
            pct = v
        pct = max(0.0, min(200.0, float(pct)))

        await self._request_json("POST", "volume", json={"set": pct})
        return True

    async def mute(self, muted: bool) -> bool:
        """Set RelayTV's native mpv mute property."""
        await self._request_json("POST", "mute", json={"set": bool(muted)})
        return True

    async def ensure_playing(self) -> bool:
        """Best-effort play semantics for Home Assistant.

        Used as a compatibility fallback when /playback/play is unavailable.
        We emulate expected behavior:

        - If paused -> POST /resume
        - Else if already playing -> success (noop)
        - Else if queue has items -> POST /next
        """
        st = await self.get_status() or {}

        if bool(st.get("paused")):
            return await self.resume()
        if bool(st.get("playing")):
            return True

        try:
            if int(st.get("queue_length") or 0) > 0:
                return await self.next()
        except Exception:
            pass

        _LOGGER.debug("ensure_playing: nothing to resume or play")
        return False
