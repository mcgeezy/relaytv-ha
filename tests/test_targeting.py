"""Tests for RelayTV service and sidebar targeting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relaytv import (
    _async_set_default_sidebar_target,
    _async_update_panel,
    _resolve_entry_ids_for_call,
)
from custom_components.relaytv.const import (
    CONF_PANEL_ENABLED,
    CONF_PANEL_TARGET_ENTRY_ID,
    DATA_API,
    DATA_PANEL_SETTINGS,
    DATA_STORE,
    DOMAIN,
)


def _add_entry(hass, title: str) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=title, data={"base_url": f"http://{title.lower()}:8787"})
    entry.add_to_hass(hass)
    return entry


async def test_explicit_non_relaytv_target_never_uses_fallback(hass) -> None:
    relay_entry = _add_entry(hass, "RelayTV")
    other_entry = MockConfigEntry(domain="test", title="Other", data={})
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    other_entity = registry.async_get_or_create(
        "media_player",
        "test",
        "other-player",
        config_entry=other_entry,
        suggested_object_id="other_player",
    )
    hass.data[DOMAIN] = {relay_entry.entry_id: {DATA_API: MagicMock()}}
    call = ServiceCall(hass, DOMAIN, "play_now", {"entity_id": other_entity.entity_id})

    with pytest.raises(ServiceValidationError, match="does not contain a loaded RelayTV"):
        _resolve_entry_ids_for_call(hass, call)


async def test_no_target_uses_saved_panel_target(hass) -> None:
    first = _add_entry(hass, "First")
    second = _add_entry(hass, "Second")
    hass.data[DOMAIN] = {
        first.entry_id: {DATA_API: MagicMock()},
        second.entry_id: {DATA_API: MagicMock()},
        DATA_PANEL_SETTINGS: {CONF_PANEL_TARGET_ENTRY_ID: second.entry_id},
    }

    call = ServiceCall(hass, DOMAIN, "play_now", {})

    assert _resolve_entry_ids_for_call(hass, call) == [second.entry_id]


async def test_setup_does_not_overwrite_saved_panel_target(hass) -> None:
    first = _add_entry(hass, "First")
    second = _add_entry(hass, "Second")
    store = MagicMock()
    store.async_save = AsyncMock()
    settings = {CONF_PANEL_ENABLED: True, CONF_PANEL_TARGET_ENTRY_ID: first.entry_id}
    hass.data[DOMAIN] = {DATA_STORE: store, DATA_PANEL_SETTINGS: settings}

    await _async_set_default_sidebar_target(hass, second)

    assert settings[CONF_PANEL_TARGET_ENTRY_ID] == first.entry_id
    store.async_save.assert_not_awaited()


async def test_panel_waits_for_saved_target_to_finish_loading(hass) -> None:
    selected = _add_entry(hass, "Selected")
    fallback = _add_entry(hass, "Fallback")
    store = MagicMock()
    store.async_save = AsyncMock()
    settings = {CONF_PANEL_ENABLED: True, CONF_PANEL_TARGET_ENTRY_ID: selected.entry_id}
    hass.data[DOMAIN] = {
        DATA_STORE: store,
        DATA_PANEL_SETTINGS: settings,
        fallback.entry_id: {DATA_API: MagicMock(base_url="http://fallback:8787")},
    }

    with (
        patch("custom_components.relaytv._async_unregister_panel") as unregister,
        patch("custom_components.relaytv._register_panel") as register,
    ):
        await _async_update_panel(hass)

    assert settings[CONF_PANEL_TARGET_ENTRY_ID] == selected.entry_id
    store.async_save.assert_not_awaited()
    unregister.assert_not_called()
    register.assert_not_called()
