"""Tests for RelayTV media-player behavior."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relaytv.media_player import RelayTVMediaPlayer, _parse_status


def test_status_parser_preserves_zero_values() -> None:
    status = _parse_status(
        {
            "playing": True,
            "volume": 0,
            "position": 0,
            "pos": 25,
            "duration": 0,
            "len": 120,
            "mute": True,
        }
    )

    assert status.volume == 0
    assert status.position == 0
    assert status.duration == 0
    assert status.muted is True


async def test_media_player_exposes_device_and_native_mute(hass) -> None:
    entry = MockConfigEntry(
        domain="relaytv",
        title="Living Room",
        data={"base_url": "http://relaytv.local:8787", "name": "Living Room"},
    )
    coordinator = MagicMock()
    coordinator.data = {"playing": True, "volume": 25, "mute": False}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    api = MagicMock(base_url="http://relaytv.local:8787")
    api.mute = AsyncMock(return_value=True)
    player = RelayTVMediaPlayer(entry, coordinator, api)

    assert player.device_info["name"] == "Living Room"
    assert player.device_info["manufacturer"] == "RelayTV"
    assert player.volume_level == 0.25
    assert player.is_volume_muted is False
    assert player.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE

    await player.async_mute_volume(True)

    api.mute.assert_awaited_once_with(True)
    coordinator.async_request_refresh.assert_awaited_once_with()
