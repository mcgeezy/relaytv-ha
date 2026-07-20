"""Tests for RelayTV coordinator state deduplication."""

from unittest.mock import MagicMock

from custom_components.relaytv.coordinator import RelayTVCoordinator, _material_state_view


def test_idle_snapshots_ignore_stale_audio_properties() -> None:
    compact_idle = {"playing": False, "paused": False, "volume": 80, "mute": True}
    full_idle = {"playing": False, "paused": False, "volume": None, "mute": None}

    assert _material_state_view(compact_idle) == _material_state_view(full_idle)


def test_playing_snapshots_track_audio_properties() -> None:
    first = {"playing": True, "paused": False, "volume": 80, "mute": False}
    second = {"playing": True, "paused": False, "volume": 30, "mute": True}

    assert _material_state_view(first) != _material_state_view(second)


async def test_note_position_update_stamps_only_position_changes(hass) -> None:
    coordinator = RelayTVCoordinator(hass=hass, api=MagicMock(base_url="http://relaytv.local:8787"))
    assert coordinator.position_updated_at is None

    coordinator.note_position_update({"playing": True, "paused": False, "position": 10.0})
    first_stamp = coordinator.position_updated_at
    assert first_stamp is not None

    coordinator.note_position_update({"playing": True, "paused": False, "position": 10.0, "volume": 50})
    assert coordinator.position_updated_at == first_stamp

    coordinator.note_position_update({"playing": True, "paused": False, "position": 25.0})
    assert coordinator.position_updated_at is not None
    assert coordinator.position_updated_at >= first_stamp
