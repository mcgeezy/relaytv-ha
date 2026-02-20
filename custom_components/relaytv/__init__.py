"""RelayTV integration.

This integration:
1) Registers a Home Assistant sidebar iframe panel that embeds the RelayTV web UI.
2) Exposes a RelayTV media_player entity backed by RelayTV's local HTTP API.
3) Provides services (e.g., relaytv.smart_url) for automations and mobile share flows.

The API layer is implemented defensively with endpoint fallbacks so it can be
adapted to RelayTV deployments that may differ slightly.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import frontend

from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_BASE_URL,
    CONF_PANEL_ICON,
    CONF_PANEL_PATH,
    CONF_PANEL_TITLE,
    DEFAULT_PANEL_ICON,
    DEFAULT_PANEL_PATH,
    DEFAULT_PANEL_TITLE,
    DATA_API,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
    SERVICE_SMART_URL,
    SERVICE_PLAY_NOW,
    SERVICE_ANNOUNCE,
)

from .relaytv_api import RelayTVApi
from .coordinator import RelayTVCoordinator

_LOGGER = logging.getLogger(__name__)


def _normalize_base_url(raw: str) -> str:
    """Normalize user input into a URL safe for iframe embedding."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Allow users to paste host:port, add scheme.
    if "://" not in raw:
        raw = f"http://{raw}"
    # Basic parse/normalize; keep path if user provided one.
    p = urlparse(raw)
    if not p.netloc:
        return raw
    # Remove trailing slash to avoid double slashes when HA appends.
    normalized = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
    if p.query:
        normalized += f"?{p.query}"
    return normalized


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RelayTV from a config entry."""
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    if not base_url:
        _LOGGER.error("RelayTV base URL is empty; panel will not be registered")
        return False

    # Store runtime objects
    hass.data.setdefault(DOMAIN, {})
    session = aiohttp_client.async_get_clientsession(hass)
    api = RelayTVApi(session=session, base_url=base_url)
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    hass.data[DOMAIN][entry.entry_id] = {DATA_API: api, DATA_COORDINATOR: coordinator}

    # Prime coordinator (non-fatal if it fails; entity will show unavailable).
    await coordinator.async_config_entry_first_refresh()

    title = entry.options.get(CONF_PANEL_TITLE, DEFAULT_PANEL_TITLE)
    icon = entry.options.get(CONF_PANEL_ICON, DEFAULT_PANEL_ICON)
    path = entry.options.get(CONF_PANEL_PATH, DEFAULT_PANEL_PATH)

    _register_panel(hass, path=path, title=title, icon=icon, url=base_url)

    # Register platforms/entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def _handle_smart_url(call):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        await api.smart_url(url)

    async def _handle_play_now(call):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        preserve_current = call.data.get("preserve_current", True)
        reason = call.data.get("reason")
        await api.play_now(url=url, preserve_current=preserve_current, reason=reason)
        await coordinator.async_request_refresh()

    async def _handle_announce(call):
        url = (call.data.get("url") or "").strip()
        if not url:
            return
        preserve_current = call.data.get("preserve_current", True)
        await api.play_now(url=url, preserve_current=preserve_current, reason="announcement")
        await coordinator.async_request_refresh()

    # Register services once (first config entry wins).
    if not hass.services.has_service(DOMAIN, SERVICE_SMART_URL):
        hass.services.async_register(DOMAIN, SERVICE_SMART_URL, _handle_smart_url)

    async def _handle_play_now(call):
        url = call.data.get("url") or ""
        preserve_current = call.data.get("preserve_current", True)
        reason = call.data.get("reason")
        title = call.data.get("title")
        thumbnail = call.data.get("thumbnail")
        if not url:
            return
        await api.play_now(url=url, preserve_current=preserve_current, reason=reason, title=title, thumbnail=thumbnail)
        await coordinator.async_request_refresh()

    async def _handle_announce(call):
        url = call.data.get("url") or ""
        preserve_current = call.data.get("preserve_current", True)
        if not url:
            return
        await api.play_now(url=url, preserve_current=preserve_current, reason="announcement")
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_NOW):
        hass.services.async_register(DOMAIN, SERVICE_PLAY_NOW, _handle_play_now)
    if not hass.services.has_service(DOMAIN, SERVICE_ANNOUNCE):
        hass.services.async_register(DOMAIN, SERVICE_ANNOUNCE, _handle_announce)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload RelayTV Web UI config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    path = entry.options.get(CONF_PANEL_PATH, DEFAULT_PANEL_PATH)
    try:
        frontend.async_remove_panel(hass, path)
    except Exception:  # pragma: no cover
        _LOGGER.debug("Panel removal failed (it may not exist)", exc_info=True)

    # Remove services only if this is the last entry.
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        try:
            hass.services.async_remove(DOMAIN, SERVICE_SMART_URL)
        except Exception:
            pass

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by re-registering the panel."""
    base_url = _normalize_base_url(entry.data.get(CONF_BASE_URL, ""))
    title = entry.options.get(CONF_PANEL_TITLE, DEFAULT_PANEL_TITLE)
    icon = entry.options.get(CONF_PANEL_ICON, DEFAULT_PANEL_ICON)
    path = entry.options.get(CONF_PANEL_PATH, DEFAULT_PANEL_PATH)

    try:
        frontend.async_remove_panel(hass, path)
    except Exception:
        pass

    _register_panel(hass, path=path, title=title, icon=icon, url=base_url)

    # Update API base_url if needed
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if store and base_url:
        store[DATA_API].base_url = base_url


def _register_panel(hass: HomeAssistant, *, path: str, title: str, icon: str, url: str) -> None:
    """Register the sidebar iframe panel."""
    # We use the built-in iframe panel. Keyword args protect against HA signature drift.
    frontend.async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=title,
        sidebar_icon=icon,
        frontend_url_path=path,
        config={"url": url},
        require_admin=False,
    )
    _LOGGER.info("Registered RelayTV Web UI panel at /%s → %s", path, url)