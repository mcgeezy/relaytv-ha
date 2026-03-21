"""RelayTV integration."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BASE_URL,
    CONF_PANEL_ENABLED,
    CONF_PANEL_TARGET_ENTRY_ID,
    CONF_RESUME_POSITIONS,
    CONF_SENSOR_STREAM_MAPPINGS,
    DATA_API,
    DATA_COORDINATOR,
    DATA_LAST_SNAPSHOT_URL,
    DATA_PANEL_SETTINGS,
    DATA_STORE,
    DEFAULT_PANEL_ICON,
    DEFAULT_PANEL_PATH,
    DEFAULT_PANEL_TITLE,
    DOMAIN,
    PLATFORMS,
    SERVICE_ANNOUNCE,
    SERVICE_OVERLAY,
    SERVICE_PLAY_NOW,
    SERVICE_PLAY_SYNCED,
    SERVICE_PLAY_TEMPORARY,
    SERVICE_PLAY_WITH_RESUME,
    SERVICE_SMART_URL,
    SERVICE_SNAPSHOT,
)
from .coordinator import RelayTVCoordinator
from .relaytv_api import RelayTVApi

_LOGGER = logging.getLogger(__name__)
RUNTIME_STORE_KEY = f"{DOMAIN}_runtime"


def _normalize_base_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        return raw
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def _absolute_url(base_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    value = str(maybe_url).strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in ("http", "https"):
        return value
    base = (base_url or "").rstrip("/")
    tail = value.lstrip("/")
    if not base or not tail:
        return None
    return f"{base}/{tail}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def _async_ensure_settings(hass: HomeAssistant) -> dict:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_STORE not in domain_data:
        domain_data[DATA_STORE] = Store(hass, 1, f"{DOMAIN}_panel_settings")
    if DATA_PANEL_SETTINGS not in domain_data:
        domain_data[DATA_PANEL_SETTINGS] = await domain_data[DATA_STORE].async_load() or {
            CONF_PANEL_ENABLED: True,
            CONF_PANEL_TARGET_ENTRY_ID: None,
        }
    return domain_data[DATA_PANEL_SETTINGS]


async def _async_save_settings(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    await data[DATA_STORE].async_save(data[DATA_PANEL_SETTINGS])


async def _async_load_runtime_data(hass: HomeAssistant) -> dict:
    data = hass.data.setdefault(DOMAIN, {})
    if "runtime_store" not in data:
        data["runtime_store"] = Store(hass, 1, RUNTIME_STORE_KEY)
    if "runtime_data" not in data:
        data["runtime_data"] = await data["runtime_store"].async_load() or {CONF_RESUME_POSITIONS: {}}
    data["runtime_data"].setdefault(CONF_RESUME_POSITIONS, {})
    return data["runtime_data"]


async def _async_save_runtime_data(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    await data["runtime_store"].async_save(data["runtime_data"])


def _get_entry_data(hass: HomeAssistant, entry_id: str) -> dict | None:
    return hass.data.get(DOMAIN, {}).get(entry_id)


def _fallback_entry_id(hass: HomeAssistant) -> str | None:
    for entry_id, value in hass.data.get(DOMAIN, {}).items():
        if isinstance(value, dict) and DATA_API in value:
            return entry_id
    return None


def _target_entity_ids_for_call(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    entity_ids: list[str] = []
    raw_entity = call.data.get(CONF_ENTITY_ID)
    if isinstance(raw_entity, str):
        entity_ids.append(raw_entity)
    elif isinstance(raw_entity, list):
        entity_ids.extend(item for item in raw_entity if isinstance(item, str))

    registry = er.async_get(hass)
    device_id = call.data.get("device_id")
    device_ids = [device_id] if isinstance(device_id, str) else device_id
    if isinstance(device_ids, list):
        for item in device_ids:
            if not isinstance(item, str):
                continue
            for reg_entry in er.async_entries_for_device(registry, item):
                if reg_entry.entity_id.startswith("media_player."):
                    entity_ids.append(reg_entry.entity_id)

    return list(dict.fromkeys(entity_ids))


def _resolve_entry_ids_for_call(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    registry = er.async_get(hass)
    entry_ids: list[str] = []
    for entity_id in _target_entity_ids_for_call(hass, call):
        reg_entry = registry.async_get(entity_id)
        if reg_entry and _get_entry_data(hass, reg_entry.config_entry_id):
            entry_ids.append(reg_entry.config_entry_id)

    if entry_ids:
        return list(dict.fromkeys(entry_ids))

    panel_target = hass.data.get(DOMAIN, {}).get(DATA_PANEL_SETTINGS, {}).get(CONF_PANEL_TARGET_ENTRY_ID)
    if panel_target and _get_entry_data(hass, panel_target):
        return [panel_target]

    fallback = _fallback_entry_id(hass)
    return [fallback] if fallback else []


def _resolve_entry_id_for_call(hass: HomeAssistant, call: ServiceCall) -> str | None:
    entry_ids = _resolve_entry_ids_for_call(hass, call)
    return entry_ids[0] if entry_ids else None


def _resolve_entries_for_entities(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    registry = er.async_get(hass)
    result: list[str] = []
    for entity_id in entity_ids:
        reg_entry = registry.async_get(entity_id)
        if reg_entry and _get_entry_data(hass, reg_entry.config_entry_id):
            result.append(reg_entry.config_entry_id)
    return list(dict.fromkeys(result))


def _register_panel(hass: HomeAssistant, *, path: str, title: str, icon: str, url: str) -> None:
    frontend.async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=title,
        sidebar_icon=icon,
        frontend_url_path=path,
        config={"url": url},
        require_admin=False,
    )


def _async_unregister_panel(hass: HomeAssistant) -> None:
    try:
        frontend.async_remove_panel(hass, DEFAULT_PANEL_PATH)
    except Exception:
        _LOGGER.debug("Panel removal failed (it may not exist)", exc_info=True)


async def _async_update_panel(hass: HomeAssistant) -> None:
    settings = await _async_ensure_settings(hass)
    _async_unregister_panel(hass)
    if not settings.get(CONF_PANEL_ENABLED, True):
        return

    target_entry_id = settings.get(CONF_PANEL_TARGET_ENTRY_ID)
    target = _get_entry_data(hass, target_entry_id) if target_entry_id else None
    if target is None:
        fallback_id = _fallback_entry_id(hass)
        if not fallback_id:
            return
        settings[CONF_PANEL_TARGET_ENTRY_ID] = fallback_id
        await _async_save_settings(hass)
        target = _get_entry_data(hass, fallback_id)
        target_entry_id = fallback_id

    if not target:
        return

    url = target[DATA_API].base_url
    _register_panel(hass, path=DEFAULT_PANEL_PATH, title=DEFAULT_PANEL_TITLE, icon=DEFAULT_PANEL_ICON, url=url)
    _LOGGER.info("Registered RelayTV panel to entry %s (%s)", target_entry_id, url)


async def _async_set_default_sidebar_target(hass: HomeAssistant, entry: ConfigEntry) -> None:
    settings = await _async_ensure_settings(hass)
    settings[CONF_PANEL_TARGET_ENTRY_ID] = entry.entry_id
    await _async_save_settings(hass)


def _entry_mappings(entry: ConfigEntry) -> list[dict]:
    mappings = entry.options.get(CONF_SENSOR_STREAM_MAPPINGS, [])
    if not isinstance(mappings, list):
        return []
    valid: list[dict] = []
    for item in mappings:
        if not isinstance(item, dict):
            continue
        sensor = item.get("sensor_entity_id")
        url = item.get("url")
        if isinstance(sensor, str) and isinstance(url, str) and sensor and url:
            valid.append({"sensor_entity_id": sensor, "url": url})
    return valid


def _setup_mapping_listeners(hass: HomeAssistant, entry: ConfigEntry) -> list:
    entry_data = _get_entry_data(hass, entry.entry_id)
    if not entry_data:
        return []

    unsubscribers = []
    for mapping in _entry_mappings(entry):
        sensor_entity_id = mapping["sensor_entity_id"]
        url = mapping["url"]

        @callback
        def _listener(event, sensor_entity_id=sensor_entity_id, url=url):
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            if old_state is not None and old_state.state == "on":
                return
            if new_state.state != "on":
                return
            hass.async_create_task(entry_data[DATA_API].play_temporary(url=url))

        unsubscribers.append(async_track_state_change_event(hass, [sensor_entity_id], _listener))

    return unsubscribers


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    if not base_url:
        _LOGGER.error("RelayTV base URL is empty")
        return False

    await _async_ensure_settings(hass)
    await _async_load_runtime_data(hass)

    session = aiohttp_client.async_get_clientsession(hass)
    api = RelayTVApi(session=session, base_url=base_url)
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
        DATA_LAST_SNAPSHOT_URL: None,
        "mapping_unsubs": [],
    }

    @callback
    def _save_resume_position() -> None:
        status = coordinator.data if isinstance(coordinator.data, dict) else {}
        url = status.get("url") or (status.get("now_playing") or {}).get("url")
        position = status.get("position")
        duration = status.get("duration")
        if not isinstance(url, str) or not url:
            return
        try:
            pos = float(position)
        except Exception:
            return
        try:
            dur = float(duration) if duration is not None else 0.0
        except Exception:
            dur = 0.0
        if pos < 60.0 or dur < 120.0:
            return

        async def _save() -> None:
            runtime = await _async_load_runtime_data(hass)
            runtime[CONF_RESUME_POSITIONS][url] = pos
            await _async_save_runtime_data(hass)

        hass.async_create_task(_save())

    coordinator.async_add_listener(_save_resume_position)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id]["mapping_unsubs"] = _setup_mapping_listeners(hass, entry)

    await _async_set_default_sidebar_target(hass, entry)
    await _async_update_panel(hass)

    async def _handle_smart_url(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].smart_url(url)
            await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_play_now(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].play(url=url, use_ytdlp=call.data.get("use_ytdlp"), cec=call.data.get("cec"))
            await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_announce(call: ServiceCall):
        await _handle_play_now(call)

    async def _handle_play_temporary(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].play_temporary(
                url=url,
                timeout_sec=call.data.get("timeout"),
                volume_override=call.data.get("volume"),
            )
            await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_overlay(call: ServiceCall):
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].overlay(
                text=call.data.get("text"),
                duration=call.data.get("duration"),
                position=call.data.get("position"),
                image_url=call.data.get("image_url"),
            )

    async def _handle_play_synced(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        delay = float(call.data.get("delay_buffer_sec") or 2)
        start_at = time.time() + delay
        targets = call.data.get("target_entities")
        entry_ids: list[str] = []
        if isinstance(targets, str):
            targets = [targets]
        if isinstance(targets, list):
            entry_ids = _resolve_entries_for_entities(hass, [e for e in targets if isinstance(e, str)])
        if not entry_ids:
            entry_ids = _resolve_entry_ids_for_call(hass, call)
        for entry_id in entry_ids:
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].play_at(url=url, start_at=start_at)
            await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_snapshot(call: ServiceCall):
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            data = await store[DATA_API].snapshot() or {}
            snapshot_url = data.get("image_url") if isinstance(data, dict) else None
            snapshot_url = _absolute_url(store[DATA_API].base_url, snapshot_url)
            if snapshot_url:
                store[DATA_LAST_SNAPSHOT_URL] = snapshot_url
                await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_play_with_resume(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        runtime = await _async_load_runtime_data(hass)
        resume_position = runtime.get(CONF_RESUME_POSITIONS, {}).get(url)
        for entry_id in _resolve_entry_ids_for_call(hass, call):
            store = _get_entry_data(hass, entry_id)
            if not store:
                continue
            await store[DATA_API].play(url=url, use_ytdlp=call.data.get("use_ytdlp"), cec=call.data.get("cec"))
            if resume_position is not None:
                await store[DATA_API].seek_abs(float(resume_position))
            await store[DATA_COORDINATOR].async_request_refresh()

    for service_name, handler in (
        (SERVICE_SMART_URL, _handle_smart_url),
        (SERVICE_PLAY_NOW, _handle_play_now),
        (SERVICE_ANNOUNCE, _handle_announce),
        (SERVICE_PLAY_TEMPORARY, _handle_play_temporary),
        (SERVICE_OVERLAY, _handle_overlay),
        (SERVICE_PLAY_SYNCED, _handle_play_synced),
        (SERVICE_SNAPSHOT, _handle_snapshot),
        (SERVICE_PLAY_WITH_RESUME, _handle_play_with_resume),
    ):
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(DOMAIN, service_name, handler)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data:
        for unsub in entry_data.get("mapping_unsubs", []):
            unsub()

    settings = await _async_ensure_settings(hass)
    if settings.get(CONF_PANEL_TARGET_ENTRY_ID) == entry.entry_id:
        replacement_id = _fallback_entry_id(hass)
        settings[CONF_PANEL_TARGET_ENTRY_ID] = replacement_id
        await _async_save_settings(hass)

    if not any(cfg_entry.entry_id in hass.data.get(DOMAIN, {}) for cfg_entry in hass.config_entries.async_entries(DOMAIN)):
        _async_unregister_panel(hass)
        for service_name in (
            SERVICE_SMART_URL,
            SERVICE_PLAY_NOW,
            SERVICE_ANNOUNCE,
            SERVICE_PLAY_TEMPORARY,
            SERVICE_OVERLAY,
            SERVICE_PLAY_SYNCED,
            SERVICE_SNAPSHOT,
            SERVICE_PLAY_WITH_RESUME,
        ):
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
        return unload_ok

    await _async_update_panel(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    store = _get_entry_data(hass, entry.entry_id)
    if store and base_url:
        store[DATA_API].base_url = base_url
        for unsub in store.get("mapping_unsubs", []):
            unsub()
        store["mapping_unsubs"] = _setup_mapping_listeners(hass, entry)
    await _async_update_panel(hass)
