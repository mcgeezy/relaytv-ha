"""Media player platform for RelayTV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any, Optional

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_API, DATA_COORDINATOR, DOMAIN


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _abs_url(base: str, maybe: Optional[str]) -> Optional[str]:
    if not maybe:
        return None
    s = str(maybe)
    # already absolute
    try:
        p = urlparse(s)
        if p.scheme in ("http", "https"):
            return s
    except Exception:
        pass
    base = (base or "").rstrip("/")
    s2 = s.lstrip("/")
    return f"{base}/{s2}" if base and s2 else (base or None)


@dataclass
class _StatusView:
    playing: bool = False
    paused: bool = False
    volume: Optional[float] = None  # 0..1
    muted: Optional[bool] = None
    position: Optional[float] = None
    duration: Optional[float] = None
    title: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None


def _parse_status(data: Optional[dict[str, Any]]) -> _StatusView:
    """Best-effort parse across possible RelayTV status shapes."""
    if not isinstance(data, dict):
        return _StatusView()

    # Common keys (based on RelayTV docs/API.md)
    playing = bool(data.get("playing") or data.get("is_playing") or data.get("play"))
    paused = bool(data.get("paused") or data.get("is_paused") or data.get("pause"))

    vol = data.get("volume")
    vol_f = _num(vol)
    # Some APIs use 0-100
    if vol_f is not None and vol_f > 1.0:
        vol_f = max(0.0, min(1.0, vol_f / 100.0))

    muted = data.get("muted")
    if muted is None:
        muted = data.get("mute")
    muted_b = None if muted is None else bool(muted)

    position = _num(data.get("position") or data.get("pos") or data.get("time"))
    duration = _num(data.get("duration") or data.get("len") or data.get("total"))

    np = data.get("now_playing") or data.get("media") or {}
    title = None
    url = None
    if isinstance(np, dict):
        title = np.get("title") or np.get("name")
        url = np.get("url") or np.get("input")
    title = title or data.get("title")
    url = url or data.get("url")

    # Prefer locally cached thumbnails when present (RelayTV serves /thumbs/<id>.jpg)
    thumb = None
    if isinstance(np, dict):
        thumb = (
            np.get("thumbnail_local")
            or np.get("thumbnail")
            or np.get("thumb")
            or np.get("image")
            or np.get("art")
            or np.get("poster")
        )
    thumb = (
        thumb
        or data.get("thumbnail_local")
        or data.get("thumbnail")
        or data.get("image")
        or data.get("art")
    )

    return _StatusView(
        playing=playing,
        paused=paused,
        volume=vol_f,
        muted=muted_b,
        position=position,
        duration=duration,
        title=title,
        url=url,
        thumbnail=thumb,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store[DATA_COORDINATOR]
    api = store[DATA_API]
    async_add_entities([RelayTVMediaPlayer(entry, coordinator, api)])


class RelayTVMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """RelayTV as a HA media_player."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, coordinator, api) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_player"
        self._attr_name = entry.data.get(CONF_NAME, entry.title)

        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SEEK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

    @property
    def state(self) -> Optional[MediaPlayerState]:
        v = _parse_status(self.coordinator.data)
        if v.playing and not v.paused:
            return MediaPlayerState.PLAYING
        if v.paused:
            return MediaPlayerState.PAUSED
        # If we have a title/url but not playing, treat as idle.
        if v.title or v.url:
            return MediaPlayerState.IDLE
        return MediaPlayerState.OFF

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def volume_level(self) -> Optional[float]:
        # HA expects 0.0-1.0. RelayTV reports 0-100 (or None when closed).
        v = _parse_status(self.coordinator.data).volume
        try:
            if v is None:
                return 0.0
            vf = float(v)
            if vf > 1.0:
                vf = vf / 100.0
            return max(0.0, min(1.0, vf))
        except Exception:
            return 0.0

    @property
    def is_volume_muted(self) -> Optional[bool]:
        # RelayTV doesn't currently expose mute as a dedicated API.
        return None

    @property
    def media_title(self) -> Optional[str]:
        return _parse_status(self.coordinator.data).title

    @property
    def media_content_id(self) -> Optional[str]:
        return _parse_status(self.coordinator.data).url

    @property
    def media_duration(self) -> Optional[float]:
        return _parse_status(self.coordinator.data).duration

    @property
    def media_position(self) -> Optional[float]:
        return _parse_status(self.coordinator.data).position

    @property
    def media_position_updated_at(self) -> Optional[datetime]:
        # Helps HA render a moving seek bar while playing.
        # Use coordinator timestamp if available; otherwise fall back to "now" (UTC).
        t = getattr(self.coordinator, "last_update_success_time", None)
        if t is None:
            return datetime.now(timezone.utc)
        # Ensure timezone-aware
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t

    @property
    def entity_picture(self) -> Optional[str]:
        v = _parse_status(self.coordinator.data)
        return _abs_url(self._entry.data.get("base_url", ""), v.thumbnail)

    async def async_media_play(self) -> None:
        # RelayTV provides /playback/play with "TV remote" semantics:
        # - toggle pause if playing
        # - resume closed session if available
        # - else play next in queue
        await self._api.playback_play()
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self._api.pause()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self._api.stop()
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        await self._api.next()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        await self._api.previous()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        await self._api.set_volume(max(0.0, min(1.0, float(volume))))
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        # Not supported by RelayTV API at this time.
        return

    async def async_turn_on(self) -> None:
        # Same behavior as PLAY.
        await self._api.playback_play()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        # Treat "turn off" as stop playback.
        await self._api.stop()
        await self.coordinator.async_request_refresh()

    async def async_media_seek(self, position: float) -> None:
        await self._api.seek_abs(float(position))
        await self.coordinator.async_request_refresh()
