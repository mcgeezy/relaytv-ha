"""Tests for RelayTV media-player behavior."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.media_player import MediaPlayerEnqueue
from homeassistant.components.media_player.const import MediaPlayerEntityFeature, MediaPlayerState
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


def test_status_parser_reads_volume_on_percent_scale() -> None:
    # RelayTV reports 0-100; a raw 1 is 1%, not full volume.
    assert _parse_status({"volume": 1}).volume == 0.01
    assert _parse_status({"volume": 100}).volume == 1.0


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
    player = RelayTVMediaPlayer(entry, coordinator, api, app_info={"release_version": "0.11.2"})

    assert player.device_info["name"] == "Living Room"
    assert player.device_info["manufacturer"] == "RelayTV"
    assert player.device_info["sw_version"] == "0.11.2"
    assert player.volume_level == 0.25
    assert player.is_volume_muted is False
    assert player.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE
    assert player.supported_features & MediaPlayerEntityFeature.PLAY_MEDIA
    assert player.supported_features & MediaPlayerEntityFeature.CLEAR_PLAYLIST

    await player.async_mute_volume(True)

    api.mute.assert_awaited_once_with(True)
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_media_player_handles_iptv_live_stream_without_url_and_play_media(hass) -> None:
    entry = MockConfigEntry(
        domain="relaytv",
        title="Living Room",
        data={"base_url": "http://relaytv.local:8787", "name": "Living Room"},
    )
    coordinator = MagicMock()
    coordinator.data = {
        "playing": True,
        "paused": False,
        "now_playing": {
            "provider": "iptv",
            "title": "Local News",
            "is_live": True,
            "iptv_source_id": "src-1",
            "iptv_channel_id": "chan-42",
        },
        "dvr": {"active": True, "at_live_edge": False, "behind_live_sec": 18.0},
    }
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    api = MagicMock(base_url="http://relaytv.local:8787")
    api.play = AsyncMock(return_value=True)
    api.play_now = AsyncMock(return_value=True)
    api.enqueue = AsyncMock(return_value=True)
    api.play_temporary = AsyncMock(return_value=True)
    api.clear_queue = AsyncMock(return_value=True)
    player = RelayTVMediaPlayer(entry, coordinator, api)
    player.hass = hass

    assert player.state == MediaPlayerState.PLAYING
    assert player.media_title == "Local News"
    assert player.media_content_id == "chan-42"
    assert player.extra_state_attributes == {
        "provider": "iptv",
        "is_live": True,
        "dvr": {"active": True, "at_live_edge": False, "behind_live_sec": 18.0},
    }

    await player.async_play_media("video", "https://media.example/a.mp4")
    api.play.assert_awaited_once_with("https://media.example/a.mp4")

    await player.async_play_media("video", "https://media.example/b.mp4", enqueue=MediaPlayerEnqueue.ADD)
    api.enqueue.assert_awaited_once_with("https://media.example/b.mp4", position="end")

    await player.async_play_media("video", "https://media.example/c.mp4", enqueue=MediaPlayerEnqueue.NEXT)
    api.enqueue.assert_awaited_with("https://media.example/c.mp4", position="next")

    await player.async_play_media("video", "https://media.example/d.mp4", enqueue=MediaPlayerEnqueue.PLAY)
    api.play_now.assert_awaited_once_with("https://media.example/d.mp4", preserve_current=True)

    await player.async_play_media("audio", "https://media.example/chime.mp3", announce=True)
    api.play_temporary.assert_awaited_once_with(url="https://media.example/chime.mp3")

    await player.async_clear_playlist()
    api.clear_queue.assert_awaited_once_with()
