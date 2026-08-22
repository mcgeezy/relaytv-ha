"""Tests for RelayTV coordinator state and realtime delivery."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp

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


class FakeWebSocket:
    """Minimal aiohttp WebSocket context with a fixed message stream."""

    def __init__(self, messages, *, protocol: str = "relaytv.realtime.v1") -> None:
        self.messages = list(messages)
        self.protocol = protocol
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        await self.close()

    def __await__(self):
        async def _value():
            return self

        return _value().__await__()

    async def receive(self):
        return self.messages.pop(0)

    async def close(self) -> None:
        self.closed = True


def _ws_text(event: str, sequence: int, data: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type=aiohttp.WSMsgType.TEXT,
        data=json.dumps({"version": 1, "event": event, "sequence": sequence, "data": data}),
    )


def _coordinator_with_socket(hass, socket: FakeWebSocket, *, token: str = ""):
    session = MagicMock()
    session.ws_connect.return_value = socket
    api = MagicMock(
        base_url="http://relaytv.local:8787",
        auth_headers={"Authorization": f"Bearer {token}"} if token else {},
        session=session,
    )
    api.websocket_url_for.return_value = "ws://relaytv.local:8787/ui/ws"
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    coordinator._push_generation = 1
    coordinator.data = {"playing": False, "paused": False, "state": "idle"}
    coordinator._schedule_debounced_refresh = MagicMock()
    return coordinator, session


async def test_websocket_negotiates_hello_and_dispatches_playback(hass) -> None:
    socket = FakeWebSocket(
        [
            _ws_text("hello", 0, {"protocol_version": 1}),
            _ws_text("playback", 8, {"playing": True, "paused": False, "position": 12}),
            SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data=None),
        ]
    )
    coordinator, session = _coordinator_with_socket(hass, socket, token="secret")

    healthy = await coordinator._async_websocket_once(
        1,
        {"ui": "/ui/ws", "subprotocol": "relaytv.realtime.v1"},
    )

    assert healthy is True
    assert coordinator.data["playing"] is True
    assert coordinator.data["position"] == 12
    assert coordinator.active_transport is None
    assert coordinator._active_connection is None
    assert socket.closed is True
    assert session.ws_connect.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert "secret" not in session.ws_connect.call_args.args[0]


async def test_websocket_rejects_state_before_versioned_hello(hass) -> None:
    socket = FakeWebSocket([_ws_text("status", 1, {"state": "playing"})])
    coordinator, _session = _coordinator_with_socket(hass, socket)

    healthy = await coordinator._async_websocket_once(
        1,
        {"ui": "/ui/ws", "subprotocol": "relaytv.realtime.v1"},
    )

    assert healthy is False
    assert coordinator.data["state"] == "idle"
    assert coordinator.active_transport is None


async def test_sequence_gap_requests_authoritative_refresh_and_retired_generation_is_ignored(hass) -> None:
    coordinator = RelayTVCoordinator(hass=hass, api=MagicMock(base_url="http://relaytv.local:8787"))
    coordinator._push_generation = 2
    coordinator._schedule_debounced_refresh = MagicMock()
    coordinator.data = {"state": "idle"}

    coordinator._last_sequence = 4
    coordinator._record_sequence(7, generation=2)
    await coordinator._async_dispatch_event("status", {"state": "playing"}, generation=1)

    coordinator._schedule_debounced_refresh.assert_called_once_with()
    assert coordinator.data == {"state": "idle"}


async def test_sse_payload_uses_the_same_transport_independent_dispatcher(hass) -> None:
    coordinator = RelayTVCoordinator(hass=hass, api=MagicMock(base_url="http://relaytv.local:8787"))
    coordinator._push_generation = 3
    coordinator.data = {"playing": False, "paused": False, "state": "idle"}

    await coordinator._async_dispatch_sse(
        "playback",
        ['{"playing":true,"paused":false,"position":19}'],
        generation=3,
    )

    assert coordinator.data["playing"] is True
    assert coordinator.data["position"] == 19


async def test_push_loop_falls_back_from_websocket_to_sse(hass, monkeypatch) -> None:
    api = MagicMock(base_url="http://relaytv.local:8787")
    api.get_realtime_capabilities = AsyncMock(
        return_value={
            "protocol_version": 1,
            "websocket": {"enabled": True, "ui": "/ui/ws"},
            "sse": {"enabled": True, "ui": "/ui/events"},
        }
    )
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    coordinator._push_generation = 1
    coordinator._async_websocket_once = AsyncMock(return_value=False)
    coordinator._async_sse_once = AsyncMock(return_value=True)

    async def finish_cycle(_delay: float) -> None:
        coordinator._push_generation += 1

    monkeypatch.setattr(asyncio, "sleep", finish_cycle)
    await coordinator._async_push_loop(1)

    coordinator._async_websocket_once.assert_awaited_once()
    coordinator._async_sse_once.assert_awaited_once()
    assert coordinator._async_sse_once.call_args.kwargs["upgrade_after"] == 300


async def test_stop_retires_generation_and_closes_owned_connection(hass) -> None:
    api = MagicMock(base_url="http://relaytv.local:8787")
    coordinator = RelayTVCoordinator(hass=hass, api=api)
    coordinator._push_generation = 4
    coordinator._push_task = asyncio.create_task(asyncio.sleep(30))
    connection = SimpleNamespace(close=AsyncMock())
    coordinator._active_connection = connection

    await coordinator.async_stop()

    assert coordinator._push_generation == 5
    assert coordinator._active_connection is None
    connection.close.assert_awaited_once_with()
