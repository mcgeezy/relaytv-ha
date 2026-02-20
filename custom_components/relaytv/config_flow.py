"""Config flow for RelayTV Web UI panel."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_BASE_URL,
    CONF_PANEL_ICON,
    CONF_PANEL_PATH,
    CONF_PANEL_TITLE,
    DEFAULT_PANEL_ICON,
    DEFAULT_PANEL_PATH,
    DEFAULT_PANEL_TITLE,
    DOMAIN,
)


class RelayTVWebUIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RelayTV Web UI panel."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            base_url = (user_input.get(CONF_BASE_URL) or "").strip()
            if not base_url:
                errors["base"] = "missing_base_url"
            else:
                # Single instance is usually sufficient; users can duplicate by cloning the folder/domain if needed.
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_PANEL_TITLE, data={CONF_BASE_URL: base_url})

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
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
        # NOTE: In modern Home Assistant, OptionsFlow exposes a read-only
        # `config_entry` property, so we cannot assign to it.
        # Store it on a private attribute instead.
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PANEL_TITLE,
                    default=self._config_entry.options.get(CONF_PANEL_TITLE, DEFAULT_PANEL_TITLE),
                ): str,
                vol.Optional(
                    CONF_PANEL_ICON,
                    default=self._config_entry.options.get(CONF_PANEL_ICON, DEFAULT_PANEL_ICON),
                ): str,
                vol.Optional(
                    CONF_PANEL_PATH,
                    default=self._config_entry.options.get(CONF_PANEL_PATH, DEFAULT_PANEL_PATH),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
