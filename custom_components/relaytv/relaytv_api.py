"""RelayTV local HTTP API helper.

This integration targets the RelayTV server API documented in relaytv/docs/API.md.
We intentionally prefer the canonical endpoints:

- GET  /status
- POST /play
- POST /smart
- POST /enqueue
- POST /next
- POST /pause | /resume | /toggle_pause
- POST /seek_abs
- POST /volume
- POST /stop

The wrapper remains defensive around timeouts and JSON parsing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)


def _join(base: str, path: str) -> str:
    base = (base or "").rstrip("/")
    path = (path or "").lstrip("/")
    return f"{base}/{path}" if path else base


@dataclass
class RelayTVApi:
    """Small wrapper around RelayTV HTTP endpoints."""

    session: aiohttp.ClientSession
    base_url: str
    timeout_s: float = 8.0

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        url = _join(self.base_url, path)
        try:
            async with asyncio.timeout(self.timeout_s):
                async with self.session.request(method, url, json=json) as resp:
                    if resp.status >= 400:
                        return None
                    try:
                        return await resp.json(content_type=None)
                    except Exception:
                        return {}
        except Exception:
            return None

    async def get_status(self) -> Optional[dict[str, Any]]:
        """Fetch current playback/status."""
        return await self._request_json("GET", "status")

    async def smart_url(self, url: str) -> bool:
        """RelayTV one-button behavior (POST /smart)."""
        data = await self._request_json("POST", "smart", json={"url": url})
        return data is not None

    async def play(self, url: str, *, use_ytdlp: bool | None = None, cec: bool | None = None) -> bool:
        """Immediate play; clears queue (POST /play)."""
        payload: dict[str, Any] = {"url": url}
        if use_ytdlp is not None:
            payload["use_ytdlp"] = bool(use_ytdlp)
        if cec is not None:
            payload["cec"] = bool(cec)
        data = await self._request_json("POST", "play", json=payload)
        return data is not None

    async def enqueue(self, url: str) -> bool:
        """Add an item to the end of the queue (POST /enqueue)."""
        data = await self._request_json("POST", "enqueue", json={"url": url})
        return data is not None

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
        return (await self._request_json("POST", "play_temporary", json=payload)) is not None

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
        return (await self._request_json("POST", "overlay", json=payload)) is not None

    async def play_at(self, *, url: str, start_at: float) -> bool:
        payload = {"url": url, "start_at": float(start_at)}
        return (await self._request_json("POST", "play_at", json=payload)) is not None

    async def snapshot(self) -> Optional[dict[str, Any]]:
        data = await self._request_json("POST", "snapshot", json={})
        if data is not None:
            return data
        return await self._request_json("GET", "snapshot")

    async def next(self) -> bool:
        """Skip to the next queued item (POST /next)."""
        data = await self._request_json("POST", "next", json={})
        return data is not None

    async def previous(self) -> bool:
        """Go to the previous item (POST /previous)."""
        data = await self._request_json("POST", "previous", json={})
        return data is not None

    async def pause(self) -> bool:
        return (await self._request_json("POST", "pause", json={})) is not None

    async def resume(self) -> bool:
        return (await self._request_json("POST", "resume", json={})) is not None

    async def toggle_pause(self) -> bool:
        return (await self._request_json("POST", "toggle_pause", json={})) is not None

    async def stop(self) -> bool:
        return (await self._request_json("POST", "stop", json={})) is not None

    async def playback_play(self) -> bool:
        """User-facing Play semantics (POST /playback/play).

        RelayTV's server implements "TV remote" behavior here:
          - if mpv is running: toggle pause
          - else if session is closed: resume
          - else: play next queued item

        If the endpoint is missing (older servers), fall back to ensure_playing().
        """
        data = await self._request_json("POST", "playback/play", json={})
        if data is not None:
            return True
        return await self.ensure_playing()

    async def seek_abs(self, sec: float) -> bool:
        """Seek to an absolute position in seconds (POST /seek_abs)."""
        try:
            sec_f = float(sec)
        except Exception:
            return False
        data = await self._request_json("POST", "seek_abs", json={"sec": sec_f})
        return data is not None

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

        # RelayTV expects {"set": <number>}
        for val in (pct, round(pct), int(round(pct))):
            data = await self._request_json("POST", "volume", json={"set": val})
            if data is not None:
                return True
        return False

    async def ensure_playing(self) -> bool:
        """Best-effort play semantics for Home Assistant.

        RelayTV does not currently expose a single "resume session or play next" endpoint.
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
