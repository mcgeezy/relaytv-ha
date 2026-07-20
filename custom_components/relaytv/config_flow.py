"""Config flow for RelayTV Web UI panel."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BASE_URL,
    CONF_API_TOKEN,
    CONF_PANEL_ENABLED,
    CONF_PANEL_TARGET_ENTRY_ID,
    CONF_SENSOR_STREAM_MAPPINGS,
    CONF_SERVER_NAME,
    DATA_PANEL_SETTINGS,
    DATA_STORE,
    DEFAULT_PANEL_TITLE,
    DOMAIN,
)
from .relaytv_api import RelayTVApi, RelayTVAuthError, RelayTVConnectionError

_LOGGER = logging.getLogger(__name__)

_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)


def _normalize_base_url(raw: str) -> str:
    """Normalize user input into a URL safe for iframe embedding."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return normalized


def _connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}
    schema: dict[Any, Any] = {
        vol.Required(CONF_BASE_URL, default=values.get(CONF_BASE_URL, "http://localhost:8787")): str,
        vol.Required(CONF_SERVER_NAME, default=values.get(CONF_SERVER_NAME, DEFAULT_PANEL_TITLE)): str,
    }
    token = values.get(CONF_API_TOKEN)
    marker = vol.Optional(CONF_API_TOKEN, default=token) if token else vol.Optional(CONF_API_TOKEN)
    schema[marker] = _PASSWORD_SELECTOR
    return vol.Schema(schema)


async def _async_validate_input(hass, data: dict[str, Any]) -> None:
    session = aiohttp_client.async_get_clientsession(hass)
    api = RelayTVApi(
        session=session,
        base_url=data[CONF_BASE_URL],
        api_token=str(data.get(CONF_API_TOKEN) or ""),
    )
    await api.validate()


def _entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    base_url = _normalize_base_url(user_input.get(CONF_BASE_URL, ""))
    name = str(user_input.get(CONF_SERVER_NAME) or "").strip()
    result: dict[str, Any] = {CONF_BASE_URL: base_url, CONF_NAME: name}
    token = str(user_input.get(CONF_API_TOKEN) or "").strip()
    if token:
        result[CONF_API_TOKEN] = token
    return result


class RelayTVWebUIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RelayTV Web UI panel."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            data = _entry_data(user_input)
            base_url = data[CONF_BASE_URL]
            name = data[CONF_NAME]
            if not base_url:
                errors["base"] = "invalid_base_url"
            elif not name:
                errors["base"] = "missing_name"
            else:
                try:
                    await _async_validate_input(self.hass, data)
                except RelayTVAuthError:
                    errors["base"] = "invalid_auth"
                except RelayTVConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating RelayTV")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(base_url)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Start reauthentication after a rejected write request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Validate and save a replacement API token."""
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = dict(entry.data)
            token = str(user_input.get(CONF_API_TOKEN) or "").strip()
            if token:
                data[CONF_API_TOKEN] = token
            else:
                data.pop(CONF_API_TOKEN, None)
            try:
                await _async_validate_input(self.hass, data)
            except RelayTVAuthError:
                errors["base"] = "invalid_auth"
            except RelayTVConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error reauthenticating RelayTV")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): _PASSWORD_SELECTOR}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Update server connection details."""
        errors = {}
        entry = self._get_reconfigure_entry()
        defaults = {
            CONF_BASE_URL: entry.data.get(CONF_BASE_URL, ""),
            CONF_SERVER_NAME: entry.data.get(CONF_NAME, entry.title),
            CONF_API_TOKEN: entry.data.get(CONF_API_TOKEN, ""),
        }
        if user_input is not None:
            data = _entry_data(user_input)
            if not data[CONF_BASE_URL]:
                errors["base"] = "invalid_base_url"
            elif not data[CONF_NAME]:
                errors["base"] = "missing_name"
            else:
                try:
                    await _async_validate_input(self.hass, data)
                except RelayTVAuthError:
                    errors["base"] = "invalid_auth"
                except RelayTVConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error reconfiguring RelayTV")
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=data[CONF_BASE_URL],
                        title=data[CONF_NAME],
                        data=data,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(user_input or defaults),
            errors=errors,
        )

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
