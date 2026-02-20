"""RelayTV local HTTP API helper.

This is intentionally defensive: RelayTV deployments may expose slightly different
paths depending on version/build. We try a small set of common candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import asyncio
import logging

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
        url: str,
        *,
        json: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        try:
            async with asyncio.timeout(self.timeout_s):
                async with self.session.request(method, url, json=json) as resp:
                    if resp.status >= 400:
                        return None
                    # Some endpoints may return empty body.
                    try:
                        return await resp.json(content_type=None)
                    except Exception:
                        return {}
        except Exception:
            return None

    async def _first_success(
        self,
        method: str,
        paths: Iterable[str],
        *,
        json: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        for p in paths:
            url = _join(self.base_url, p)
            data = await self._request_json(method, url, json=json)
            if data is not None:
                return data
        return None

    async def get_status(self) -> Optional[dict[str, Any]]:
        """Fetch current playback/status."""
        return await self._first_success(
            "GET",
            (
                "status",
                "api/status",
                "v1/status",
                "player/status",
            ),
        )

    async def smart_url(self, url: str) -> bool:
        """Smart URL handler used by the HA service relaytv.smart_url.

        Goal:
          - If something is already playing, try to ENQUEUE (add to queue) first.
          - Otherwise, try the server's smart_url endpoint.
          - Only as a last resort, fall back to play-now style endpoints.
        """
        payload = {"url": url}

        status = await self.get_status() or {}

        # Determine "currently playing" as defensively as possible.
        state = str(status.get("state") or "").lower()
        playing_flag = bool(status.get("playing")) and not bool(status.get("paused"))
        is_playing = playing_flag or (state == "playing")

        if is_playing:
            data = await self._first_success(
                "POST",
                (
                    "queue/add",
                    "api/queue/add",
                    "v1/queue/add",
                    "enqueue",
                    "api/enqueue",
                    "v1/enqueue",
                    "queue",
                    "api/queue",
                    "v1/queue",
                ),
                json=payload,
            )
            if data is not None:
                return True

        # Prefer true smart endpoints next.
        data = await self._first_success(
            "POST",
            (
                "smart_url",
                "api/smart_url",
                "v1/smart_url",
                "cast/smart_url",
            ),
            json=payload,
        )
        if data is not None:
            return True

        # Last resort: endpoints that typically REPLACE current playback.
        data = await self._first_success(
            "POST",
            (
                "cast/url",
                "play",
                "api/play",
                "v1/play",
            ),
            json=payload,
        )
        return data is not None

    
    async def command(self, cmd: str, *, value: Optional[Any] = None) -> bool:
        """Send a player control command.

        This is aligned to the RelayTV server API:

        - Seek scrubber should be absolute: POST /seek_abs {"sec": <seconds>}
        - Volume slider should be absolute: POST /volume {"set": <0-100>}
        - Power on / play semantics: POST /playback/play {}

        We still keep a couple of legacy fallbacks for older builds.
        """
        cmd = (cmd or "").strip().lower()

        # Absolute seek (HA provides absolute seconds)
        if cmd == "seek" and value is not None:
            return await self.seek_abs(float(value))

        # Volume: HA provides 0.0-1.0
        if cmd == "volume" and value is not None:
            return await self.set_volume(value)

        # Preferred play semantics
        if cmd == "play":
            return await self.playback_play()

        # Simple direct endpoints for common commands
        direct_paths = {
            "pause": ("pause",),
            "toggle_pause": ("toggle_pause", "pause"),
            "stop": ("stop",),
            "close": ("close",),
            "next": ("next", "queue/next", "queue/skip"),
            "previous": ("previous",),
        }
        if cmd in direct_paths:
            data = await self._first_success("POST", direct_paths[cmd], json={})
            return data is not None

        # Legacy control-style fallback
        payload: dict[str, Any] = {"command": cmd}
        if value is not None:
            payload["value"] = value
        data = await self._first_success("POST", ("control", "api/control", "v1/control"), json=payload)
        if data is not None:
            return True

        # Legacy "POST /player/<cmd>" or "/<cmd>"
        data = await self._first_success("POST", (f"player/{cmd}", cmd), json={} if value is None else {"value": value})
        if data is not None:
            return True

        _LOGGER.debug("RelayTV command failed: %s value=%s", cmd, value)
        return False

    async def seek_abs(self, sec: float) -> bool:
        """Seek to an absolute position in seconds (RelayTV: POST /seek_abs)."""
        try:
            sec_f = float(sec)
        except Exception:
            return False
        data = await self._first_success("POST", ("seek_abs",), json={"sec": sec_f})
        if data is not None:
            return True
        # Very old fallback (some builds used /seek with sec as absolute)
        data = await self._first_success("POST", ("seek",), json={"sec": sec_f})
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

        # RelayTV expects {"set": <float>} (and supports {"delta": <float>} for relative changes)
        for val in (pct, round(pct), int(round(pct))):
            data = await self._first_success("POST", ("volume",), json={"set": val})
            if data is not None:
                return True
        # fallback via control (rare)
        data = await self._first_success("POST", ("control", "api/control", "v1/control"), json={"command": "volume", "set": pct})
        return data is not None

    async def playback_play(self) -> bool:
        """RelayTV's preferred 'Play' semantics: POST /playback/play."""
        data = await self._first_success("POST", ("playback/play",), json={})
        if data is not None:
            return True
        # fallback
        data = await self._first_success("POST", ("resume", "play"), json={})
        return data is not None

    async def previous(self) -> bool:
        """Go back (server decides restart vs history)."""
        data = await self._first_success("POST", ("previous",), json={})
        return data is not None

    async def play_now(
        self,
        url: str,
        preserve_current: bool = True,
        reason: Optional[str] = None,
        title: Optional[str] = None,
        thumbnail: Optional[str] = None,
    ) -> bool:
        """Interrupt-play a URL immediately, optionally preserving current into queue front."""
        payload: dict[str, Any] = {
            "url": url,
            "preserve_current": bool(preserve_current),
        }
        if reason:
            payload["reason"] = reason
        if title:
            payload["title"] = title
        if thumbnail:
            payload["thumbnail"] = thumbnail

        data = await self._first_success("POST", ("play_now",), json=payload)
        return data is not None
