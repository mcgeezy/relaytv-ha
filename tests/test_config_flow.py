"""Tests for RelayTV configuration and authentication flows."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relaytv.const import CONF_API_TOKEN, CONF_BASE_URL, CONF_SERVER_NAME, DOMAIN


async def test_user_flow_validates_and_stores_token(hass, aioclient_mock) -> None:
    base_url = "http://relaytv.local:8787"
    aioclient_mock.get(f"{base_url}/status", json={"state": "idle"})
    aioclient_mock.post(f"{base_url}/auth/check", json={"ok": True, "token_required": True})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_BASE_URL: base_url,
            CONF_SERVER_NAME: "Living Room",
            CONF_API_TOKEN: "testing-token",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {
        CONF_BASE_URL: base_url,
        "name": "Living Room",
        CONF_API_TOKEN: "testing-token",
    }


async def test_user_flow_reports_invalid_auth(hass, aioclient_mock) -> None:
    base_url = "http://relaytv.local:8787"
    aioclient_mock.get(f"{base_url}/status", json={"state": "idle"})
    aioclient_mock.post(
        f"{base_url}/auth/check",
        status=401,
        json={"detail": "api token required"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_BASE_URL: base_url,
            CONF_SERVER_NAME: "Living Room",
            CONF_API_TOKEN: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_rejects_credentialed_url_without_request(hass, aioclient_mock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_BASE_URL: "http://user:password@relaytv.local:8787?token=secret",
            CONF_SERVER_NAME: "Living Room",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_base_url"}
    assert not aioclient_mock.mock_calls


async def test_user_flow_rejects_malformed_port_or_bracketed_host(hass, aioclient_mock) -> None:
    for invalid_url in ("http://relaytv.local:99999", "[relaytv.local]:8787"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_BASE_URL: invalid_url,
                CONF_SERVER_NAME: "Living Room",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_base_url"}
    assert not aioclient_mock.mock_calls


async def test_reauth_replaces_rejected_token(hass, aioclient_mock) -> None:
    base_url = "http://relaytv.local:8787"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={CONF_BASE_URL: base_url, "name": "Living Room", CONF_API_TOKEN: "old-token"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(f"{base_url}/status", json={"state": "idle"})
    aioclient_mock.post(f"{base_url}/auth/check", json={"ok": True, "token_required": True})
    with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "new-token"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "new-token"


async def test_reconfigure_updates_connection_and_title(hass, aioclient_mock) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        unique_id="http://old-relaytv.local:8787",
        data={CONF_BASE_URL: "http://old-relaytv.local:8787", "name": "Living Room"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    base_url = "https://new-relaytv.local:8787"
    aioclient_mock.get(f"{base_url}/status", json={"state": "idle"})
    aioclient_mock.post(f"{base_url}/auth/check", json={"ok": True, "token_required": False})
    with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: base_url,
                CONF_SERVER_NAME: "Theater",
                CONF_API_TOKEN: "",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Theater"
    assert entry.unique_id == base_url
    assert entry.data == {CONF_BASE_URL: base_url, "name": "Theater"}
