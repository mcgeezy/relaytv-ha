"""Tests for RelayTV coordinator state deduplication."""

from custom_components.relaytv.coordinator import _material_state_view


def test_idle_snapshots_ignore_stale_audio_properties() -> None:
    compact_idle = {"playing": False, "paused": False, "volume": 80, "mute": True}
    full_idle = {"playing": False, "paused": False, "volume": None, "mute": None}

    assert _material_state_view(compact_idle) == _material_state_view(full_idle)


def test_playing_snapshots_track_audio_properties() -> None:
    first = {"playing": True, "paused": False, "volume": 80, "mute": False}
    second = {"playing": True, "paused": False, "volume": 30, "mute": True}

    assert _material_state_view(first) != _material_state_view(second)
