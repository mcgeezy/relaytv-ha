"""Config flow for RelayTV Web UI panel."""

from __future__ import annotations

from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BASE_URL,
    CONF_PANEL_ENABLED,
    CONF_PANEL_TARGET_ENTRY_ID,
    CONF_SENSOR_STREAM_MAPPINGS,
    CONF_SERVER_NAME,
    DATA_PANEL_SETTINGS,
    DATA_STORE,
    DEFAULT_PANEL_TITLE,
    DOMAIN,
)


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


class RelayTVWebUIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RelayTV Web UI panel."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            base_url = _normalize_base_url(user_input.get(CONF_BASE_URL, ""))
            name = (user_input.get(CONF_SERVER_NAME) or "").strip()
            if not base_url:
                errors["base"] = "missing_base_url"
            elif not name:
                errors["base"] = "missing_name"
            else:
                await self.async_set_unique_id(base_url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={CONF_BASE_URL: base_url, CONF_NAME: name},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default="http://localhost:8787"): str,
                vol.Required(CONF_SERVER_NAME, default=DEFAULT_PANEL_TITLE): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RelayTVWebUIOptionsFlow(config_entry)


class RelayTVWebUIOptionsFlow(config_entries.OptionsFlow):
    """Handle options for RelayTV Web UI panel."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        settings_store = Store(self.hass, 1, f"{DOMAIN}_panel_settings")
        settings = await settings_store.async_load() or {}

        entries = self.hass.config_entries.async_entries(DOMAIN)
        choices = {entry.entry_id: entry.title for entry in entries}

        current_target = settings.get(CONF_PANEL_TARGET_ENTRY_ID)
        if current_target not in choices and choices:
            current_target = entries[-1].entry_id

        if user_input is not None:
            chosen_target = user_input.get(CONF_PANEL_TARGET_ENTRY_ID)
            if chosen_target not in choices and choices:
                chosen_target = entries[-1].entry_id

            updated = {
                CONF_PANEL_ENABLED: bool(user_input.get(CONF_PANEL_ENABLED, True)),
                CONF_PANEL_TARGET_ENTRY_ID: chosen_target,
            }
            await settings_store.async_save(updated)
            self.hass.data.setdefault(DOMAIN, {})[DATA_STORE] = settings_store
            self.hass.data[DOMAIN][DATA_PANEL_SETTINGS] = updated

            mappings = user_input.get(CONF_SENSOR_STREAM_MAPPINGS, [])
            if not isinstance(mappings, list):
                mappings = []
            clean_mappings = []
            for item in mappings:
                if not isinstance(item, dict):
                    continue
                sensor = item.get("sensor_entity_id")
                url = item.get("url")
                if isinstance(sensor, str) and isinstance(url, str) and sensor and url:
                    clean_mappings.append({"sensor_entity_id": sensor, "url": url})

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                options={CONF_SENSOR_STREAM_MAPPINGS: clean_mappings},
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PANEL_ENABLED,
                    default=settings.get(CONF_PANEL_ENABLED, True),
                ): bool,
                vol.Required(
                    CONF_PANEL_TARGET_ENTRY_ID,
                    default=current_target,
                ): vol.In(choices),
                vol.Optional(
                    CONF_SENSOR_STREAM_MAPPINGS,
                    default=self._config_entry.options.get(CONF_SENSOR_STREAM_MAPPINGS, []),
                ): selector.ObjectSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
