"""Tests for RelayTV config-entry setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import relaytv
from custom_components.relaytv import async_setup_entry
from custom_components.relaytv.const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    DATA_API,
    DATA_COORDINATOR,
    DOMAIN,
)


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


async def test_reconfigure_stops_old_transport_before_mutating_connection(hass, monkeypatch) -> None:
    api = SimpleNamespace(base_url="http://old.local:8787", api_token="old-token")
    coordinator = MagicMock()
    timeline: list[tuple[str, str]] = []

    async def stop() -> None:
        timeline.append(("stop", api.base_url))

    async def start() -> None:
        timeline.append(("start", api.base_url))

    coordinator.async_stop = AsyncMock(side_effect=stop)
    coordinator.async_start = AsyncMock(side_effect=start)
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={CONF_BASE_URL: "http://new.local:8787", CONF_API_TOKEN: "new-token"},
    )
    hass.data[DOMAIN] = {
        "entry-id": {
            DATA_API: api,
            DATA_COORDINATOR: coordinator,
            "mapping_unsubs": [],
        }
    }
    monkeypatch.setattr(relaytv, "_setup_mapping_listeners", lambda *_args: [])
    monkeypatch.setattr(relaytv, "_async_update_panel", AsyncMock())

    await relaytv._async_update_listener(hass, entry)

    assert timeline == [
        ("stop", "http://old.local:8787"),
        ("start", "http://new.local:8787"),
    ]
    assert api.api_token == "new-token"
