"""Media player platform for RelayTV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Optional

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_API, DATA_APP_INFO, DATA_COORDINATOR, DATA_LAST_SNAPSHOT_URL, DOMAIN
from .url_utils import sanitize_url


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
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
    content_id: Optional[str] = None
    thumbnail: Optional[str] = None
    provider: Optional[str] = None
    is_live: Optional[bool] = None
    dvr: Optional[dict[str, Any]] = None


def _parse_status(data: Optional[dict[str, Any]]) -> _StatusView:
    """Best-effort parse across possible RelayTV status shapes."""
    if not isinstance(data, dict):
        return _StatusView()

    # Common keys (based on RelayTV docs/API.md)
    playing = bool(data.get("playing") or data.get("is_playing") or data.get("play"))
    paused = bool(data.get("paused") or data.get("is_paused") or data.get("pause"))

    vol = data.get("volume")
    vol_f = _num(vol)
    # RelayTV always reports volume on a 0-100 scale (a raw 1 means 1%,
    # not full volume), so convert unconditionally.
    if vol_f is not None:
        vol_f = max(0.0, min(1.0, vol_f / 100.0))

    muted = data.get("muted")
    if muted is None:
        muted = data.get("mute")
    muted_b = None if muted is None else bool(muted)

    position = _num(_first_present(data, "position", "pos", "time"))
    duration = _num(_first_present(data, "duration", "len", "total"))

    np = data.get("now_playing") or data.get("media") or {}
    title = None
    url = None
    fallback_id = None
    provider = None
    is_live = None
    if isinstance(np, dict):
        title = np.get("title") or np.get("name")
        url = np.get("url") or np.get("input")
        fallback_id = np.get("iptv_channel_id") or np.get("plex_rating_key") or np.get("jellyfin_item_id")
        if np.get("provider"):
            provider = str(np.get("provider")).strip() or None
        if np.get("is_live") is not None:
            is_live = bool(np.get("is_live"))
    title = title or data.get("title")
    url = url or data.get("url")
    content_id = sanitize_url(url) or (str(fallback_id).strip() if fallback_id else None)

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

    raw_dvr = data.get("dvr")
    dvr = raw_dvr if isinstance(raw_dvr, dict) else None

    return _StatusView(
        playing=playing,
        paused=paused,
        volume=vol_f,
        muted=muted_b,
        position=position,
        duration=duration,
        title=title,
        url=url,
        content_id=content_id,
        thumbnail=thumb,
        provider=provider,
        is_live=is_live,
        dvr=dvr,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store[DATA_COORDINATOR]
    api = store[DATA_API]
    app_info = store.get(DATA_APP_INFO)
    async_add_entities([RelayTVMediaPlayer(entry, coordinator, api, app_info=app_info)])


class RelayTVMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """RelayTV as a HA media_player."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, coordinator, api, *, app_info: dict[str, Any] | None = None) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_player"
        sw_version = None
        if isinstance(app_info, dict):
            raw_ver = app_info.get("release_version") or app_info.get("version")
            if raw_ver:
                sw_version = str(raw_ver)
        device_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, entry.title),
            "manufacturer": "RelayTV",
            "model": "RelayTV server",
            "configuration_url": api.base_url,
        }
        if sw_version:
            device_kwargs["sw_version"] = sw_version
        self._attr_device_info = DeviceInfo(**device_kwargs)

        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SEEK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
            | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        )

    @property
    def state(self) -> Optional[MediaPlayerState]:
        v = _parse_status(self.coordinator.data)
        if v.playing and not v.paused:
            return MediaPlayerState.PLAYING
        if v.paused:
            return MediaPlayerState.PAUSED
        # If we have a title/url/content_id but not playing, treat as idle.
        if v.title or v.url or v.content_id:
            return MediaPlayerState.IDLE
        return MediaPlayerState.OFF

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def volume_level(self) -> Optional[float]:
        # HA expects 0.0-1.0. RelayTV reports 0-100 (or None when closed).
        v = _parse_status(self.coordinator.data).volume
        return v

    @property
    def is_volume_muted(self) -> Optional[bool]:
        return _parse_status(self.coordinator.data).muted

    @property
    def media_title(self) -> Optional[str]:
        return _parse_status(self.coordinator.data).title

    @property
    def media_content_id(self) -> Optional[str]:
        return _parse_status(self.coordinator.data).content_id

    @property
    def media_duration(self) -> Optional[float]:
        return _parse_status(self.coordinator.data).duration

    @property
    def media_position(self) -> Optional[float]:
        return _parse_status(self.coordinator.data).position

    @property
    def media_position_updated_at(self) -> Optional[datetime]:
        # The coordinator stamps this whenever the reported position changes
        # (SSE and poll paths both), letting HA extrapolate the seek bar
        # between updates.
        return self.coordinator.position_updated_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.hass is not None:
            store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
            snapshot_url = store.get(DATA_LAST_SNAPSHOT_URL)
            if snapshot_url:
                attrs["snapshot_url"] = snapshot_url
        v = _parse_status(self.coordinator.data)
        if v.provider:
            attrs["provider"] = v.provider
        if v.is_live is not None:
            attrs["is_live"] = v.is_live
        if v.dvr:
            attrs["dvr"] = v.dvr
        return attrs

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
        await self._api.mute(mute)
        await self.coordinator.async_request_refresh()

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

    async def async_clear_playlist(self) -> None:
        await self._api.clear_queue()
        await self.coordinator.async_request_refresh()

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        target_url = (media_id or "").strip()
        if not target_url:
            return

        if self.hass is not None and media_source.is_media_source_id(target_url):
            resolved = await media_source.async_resolve_media(self.hass, target_url, self.entity_id)
            if resolved.path is not None:
                local_path = str(resolved.path)
                is_file = await self.hass.async_add_executor_job(Path(local_path).is_file)
                if is_file:
                    if not announce and enqueue in (None, MediaPlayerEnqueue.REPLACE):
                        await self._api.upload_media_play(local_path)
                        await self.coordinator.async_request_refresh()
                        return
                    uploaded = await self._api.upload_media(local_path)
                    uploaded_url = uploaded.get("url") if isinstance(uploaded, dict) else None
                    if not isinstance(uploaded_url, str) or not uploaded_url.strip():
                        raise ServiceValidationError("RelayTV media upload did not return a playable URL")
                    target_url = _abs_url(self._api.base_url, uploaded_url)
                else:
                    target_url = async_process_play_media_url(self.hass, resolved.url)
            else:
                target_url = async_process_play_media_url(self.hass, resolved.url)

        if announce:
            await self._api.play_temporary(url=target_url)
        elif enqueue == MediaPlayerEnqueue.ADD:
            await self._api.enqueue(target_url, position="end")
        elif enqueue == MediaPlayerEnqueue.NEXT:
            await self._api.enqueue(target_url, position="next")
        elif enqueue == MediaPlayerEnqueue.PLAY:
            await self._api.play_now(target_url, preserve_current=True)
        else:
            await self._api.play(target_url)
        await self.coordinator.async_request_refresh()
