"""Tests for RelayTV config-entry setup."""

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relaytv import async_setup_entry
from custom_components.relaytv.const import CONF_API_TOKEN, CONF_BASE_URL, DOMAIN


async def test_setup_rejects_invalid_write_credentials(hass, aioclient_mock) -> None:
    base_url = "http://relaytv.local:8787"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={CONF_BASE_URL: base_url, "name": "Living Room", CONF_API_TOKEN: "wrong"},
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{base_url}/status", json={"state": "idle"})
    aioclient_mock.post(
        f"{base_url}/auth/check",
        status=401,
        json={"detail": "api token required"},
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, entry)
