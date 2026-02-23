"""RelayTV integration."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BASE_URL,
    CONF_PANEL_ENABLED,
    CONF_PANEL_TARGET_ENTRY_ID,
    DATA_API,
    DATA_COORDINATOR,
    DATA_PANEL_SETTINGS,
    DATA_STORE,
    DEFAULT_PANEL_ICON,
    DEFAULT_PANEL_PATH,
    DEFAULT_PANEL_TITLE,
    DOMAIN,
    PLATFORMS,
    SERVICE_ANNOUNCE,
    SERVICE_PLAY_NOW,
    SERVICE_SMART_URL,
)
from .coordinator import RelayTVCoordinator
from .relaytv_api import RelayTVApi

_LOGGER = logging.getLogger(__name__)


def _normalize_base_url(raw: str) -> str:
    """Normalize user input into a URL safe for iframe embedding."""
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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the RelayTV domain."""
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


def _get_entry_data(hass: HomeAssistant, entry_id: str) -> dict | None:
    return hass.data.get(DOMAIN, {}).get(entry_id)


def _fallback_entry_id(hass: HomeAssistant) -> str | None:
    for entry_id, value in hass.data.get(DOMAIN, {}).items():
        if isinstance(value, dict) and DATA_API in value:
            return entry_id
    return None


def _resolve_entry_id_for_call(hass: HomeAssistant, call: ServiceCall) -> str | None:
    entity_ids: list[str] = []
    raw_entity = call.data.get(CONF_ENTITY_ID)
    if isinstance(raw_entity, str):
        entity_ids = [raw_entity]
    elif isinstance(raw_entity, list):
        entity_ids = [item for item in raw_entity if isinstance(item, str)]

    registry = er.async_get(hass)

    if not entity_ids:
        device_id = call.data.get("device_id")
        device_ids = [device_id] if isinstance(device_id, str) else device_id
        if isinstance(device_ids, list):
            for item in device_ids:
                if not isinstance(item, str):
                    continue
                for reg_entry in er.async_entries_for_device(registry, item):
                    if reg_entry.entity_id.startswith("media_player."):
                        entity_ids.append(reg_entry.entity_id)

    for entity_id in entity_ids:
        reg_entry = registry.async_get(entity_id)
        if reg_entry and _get_entry_data(hass, reg_entry.config_entry_id):
            return reg_entry.config_entry_id

    panel_target = hass.data.get(DOMAIN, {}).get(DATA_PANEL_SETTINGS, {}).get(CONF_PANEL_TARGET_ENTRY_ID)
    if panel_target and _get_entry_data(hass, panel_target):
        return panel_target
    return _fallback_entry_id(hass)


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
    _register_panel(
        hass,
        path=DEFAULT_PANEL_PATH,
        title=DEFAULT_PANEL_TITLE,
        icon=DEFAULT_PANEL_ICON,
        url=url,
    )
    _LOGGER.info("Registered RelayTV panel to entry %s (%s)", target_entry_id, url)


async def _async_set_default_sidebar_target(hass: HomeAssistant, entry: ConfigEntry) -> None:
    settings = await _async_ensure_settings(hass)
    settings[CONF_PANEL_TARGET_ENTRY_ID] = entry.entry_id
    await _async_save_settings(hass)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RelayTV from a config entry."""
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    if not base_url:
        _LOGGER.error("RelayTV base URL is empty")
        return False

    await _async_ensure_settings(hass)

    session = aiohttp_client.async_get_clientsession(hass)
    api = RelayTVApi(session=session, base_url=base_url)
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_API: api, DATA_COORDINATOR: coordinator}

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_set_default_sidebar_target(hass, entry)
    await _async_update_panel(hass)

    async def _handle_smart_url(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        entry_id = _resolve_entry_id_for_call(hass, call)
        store = _get_entry_data(hass, entry_id) if entry_id else None
        if not store:
            return
        await store[DATA_API].smart_url(url)
        await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_play_now(call: ServiceCall):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        entry_id = _resolve_entry_id_for_call(hass, call)
        store = _get_entry_data(hass, entry_id) if entry_id else None
        if not store:
            return
        await store[DATA_API].play(
            url=url,
            use_ytdlp=call.data.get("use_ytdlp"),
            cec=call.data.get("cec"),
        )
        await store[DATA_COORDINATOR].async_request_refresh()

    async def _handle_announce(call: ServiceCall):
        await _handle_play_now(call)

    if not hass.services.has_service(DOMAIN, SERVICE_SMART_URL):
        hass.services.async_register(DOMAIN, SERVICE_SMART_URL, _handle_smart_url)
    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_NOW):
        hass.services.async_register(DOMAIN, SERVICE_PLAY_NOW, _handle_play_now)
    if not hass.services.has_service(DOMAIN, SERVICE_ANNOUNCE):
        hass.services.async_register(DOMAIN, SERVICE_ANNOUNCE, _handle_announce)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload RelayTV entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    settings = await _async_ensure_settings(hass)
    if settings.get(CONF_PANEL_TARGET_ENTRY_ID) == entry.entry_id:
        replacement_id = _fallback_entry_id(hass)
        settings[CONF_PANEL_TARGET_ENTRY_ID] = replacement_id
        await _async_save_settings(hass)
        _LOGGER.info(
            "RelayTV sidebar target removed (%s); switched to %s",
            entry.entry_id,
            replacement_id,
        )

    if not any(cfg_entry.entry_id in hass.data.get(DOMAIN, {}) for cfg_entry in hass.config_entries.async_entries(DOMAIN)):
        _async_unregister_panel(hass)
        for service_name in (SERVICE_SMART_URL, SERVICE_PLAY_NOW, SERVICE_ANNOUNCE):
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
        return unload_ok

    await _async_update_panel(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle entry updates."""
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    store = _get_entry_data(hass, entry.entry_id)
    if store and base_url:
        store[DATA_API].base_url = base_url
    await _async_update_panel(hass)
