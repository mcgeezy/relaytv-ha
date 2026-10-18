"""Tests for RelayTV HTTP error and authentication behavior."""

from typing import Any

import pytest

from custom_components.relaytv.relaytv_api import (
    RelayTVApi,
    RelayTVAuthError,
    RelayTVResponseError,
)


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self.payload = payload
        self.reason = "test response"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def json(self, **_kwargs):
        return self.payload

    async def text(self) -> str:
        return str(self.payload)


class FakeSession:
    """Record requests and return predefined responses."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.mark.asyncio
async def test_validate_sends_bearer_token() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"state": "idle"}),
            FakeResponse(200, {"ok": True, "token_required": True}),
        ]
    )
    api = RelayTVApi(session, "http://relaytv.local:8787", api_token="testing-token")

    await api.validate()

    assert [request["headers"] for request in session.requests] == [
        {"Authorization": "Bearer testing-token"},
        {"Authorization": "Bearer testing-token"},
    ]


@pytest.mark.asyncio
async def test_auth_failure_raises_and_requests_reauth() -> None:
    auth_failures: list[bool] = []
    session = FakeSession([FakeResponse(401, {"detail": "api token required"})])
    api = RelayTVApi(
        session,
        "http://relaytv.local:8787",
        api_token="wrong",
        on_auth_failure=lambda: auth_failures.append(True),
    )

    with pytest.raises(RelayTVAuthError):
        await api.pause()

    assert auth_failures == [True]


@pytest.mark.asyncio
async def test_server_error_does_not_trigger_playback_fallback() -> None:
    session = FakeSession([FakeResponse(503, {"detail": "backend unavailable"})])
    api = RelayTVApi(session, "http://relaytv.local:8787")

    with pytest.raises(RelayTVResponseError) as err:
        await api.playback_play()

    assert err.value.status == 503
    assert len(session.requests) == 1


@pytest.mark.asyncio
async def test_mute_sets_explicit_boolean() -> None:
    session = FakeSession([FakeResponse(200, {"ok": True, "mute": True})])
    api = RelayTVApi(session, "http://relaytv.local:8787")

    await api.mute(True)

    assert session.requests[0]["url"] == "http://relaytv.local:8787/mute"
    assert session.requests[0]["json"] == {"set": True}


@pytest.mark.asyncio
async def test_realtime_capabilities_fall_back_to_legacy_sse_on_404() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "not found"})])
    api = RelayTVApi(session, "http://relaytv.local:8787", api_token="testing-token")

    capabilities = await api.get_realtime_capabilities()

    assert capabilities["protocol_version"] == 0
    assert capabilities["websocket"] == {"enabled": False}
    assert capabilities["sse"] == {"enabled": True, "ui": "/ui/events"}
    assert session.requests[0]["headers"] == {"Authorization": "Bearer testing-token"}


@pytest.mark.asyncio
async def test_realtime_capabilities_preserve_supported_transport_contract() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "protocol_version": 1,
                    "preferred_transport": "websocket",
                    "websocket": {
                        "enabled": True,
                        "ui": "/ui/ws",
                        "subprotocol": "relaytv.realtime.v1",
                    },
                    "sse": {"enabled": True, "ui": "/ui/events"},
                    "heartbeat_sec": 5,
                    "replay": False,
                },
            )
        ]
    )
    api = RelayTVApi(session, "http://relaytv.local:8787")

    capabilities = await api.get_realtime_capabilities()

    assert capabilities["preferred_transport"] == "websocket"
    assert capabilities["websocket"]["subprotocol"] == "relaytv.realtime.v1"
    assert capabilities["sse"]["ui"] == "/ui/events"


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://relaytv.local:8787", "ws://relaytv.local:8787/ui/ws"),
        ("https://tv.example/relaytv", "wss://tv.example/relaytv/ui/ws"),
    ],
)
def test_websocket_url_uses_matching_secure_scheme_without_credentials(base_url: str, expected: str) -> None:
    api = RelayTVApi(FakeSession([]), base_url, api_token="must-not-leak")

    assert api.websocket_url_for("ui/ws") == expected
    assert "must-not-leak" not in api.websocket_url_for("ui/ws")


@pytest.mark.asyncio
async def test_smart_play_now_and_enqueue_pass_playlist_and_preserve_options() -> None:
    session = FakeSession(
        [
            FakeResponse(202, {"ok": True, "action": "playlist_import_started"}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    api = RelayTVApi(session, "http://relaytv.local:8787")

    await api.smart_url(
        "https://youtube.com/watch?v=1&list=PL123",
        use_ytdlp=True,
        cec=True,
        playlist_mode="playlist",
    )
    await api.play_now(
        "https://media.example/video.mp4",
        preserve_current=True,
        preserve_to="next",
        resume_current=True,
        playlist_mode="video",
    )
    await api.enqueue(
        "https://media.example/next.mp4",
        position="next",
        playlist_mode="auto",
    )

    assert session.requests[0]["url"] == "http://relaytv.local:8787/smart"
    assert session.requests[0]["json"] == {
        "url": "https://youtube.com/watch?v=1&list=PL123",
        "use_ytdlp": True,
        "cec": True,
        "playlist_mode": "playlist",
    }
    assert session.requests[1]["url"] == "http://relaytv.local:8787/play_now"
    assert session.requests[1]["json"] == {
        "url": "https://media.example/video.mp4",
        "preserve_current": True,
        "preserve_to": "next",
        "resume_current": True,
        "playlist_mode": "video",
    }
    assert session.requests[2]["url"] == "http://relaytv.local:8787/enqueue"
    assert session.requests[2]["json"] == {
        "url": "https://media.example/next.mp4",
        "position": "next",
        "playlist_mode": "auto",
    }


@pytest.mark.asyncio
async def test_play_now_falls_back_to_play_on_404_and_overlay_normalizes_center() -> None:
    session = FakeSession(
        [
            FakeResponse(404, {"detail": "not found"}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"ok": True}),
            FakeResponse(200, {"release_version": "0.11.2"}),
        ]
    )
    api = RelayTVApi(session, "http://relaytv.local:8787")

    await api.play_now("https://media.example/video.mp4", use_ytdlp=False, preserve_current=True)
    await api.overlay(text="Doorbell", position="center")
    await api.clear_queue()
    await api.cancel_temporary_playback()
    await api.jump_to_live()
    info = await api.get_app_info()

    assert session.requests[0]["url"] == "http://relaytv.local:8787/play_now"
    assert session.requests[1]["url"] == "http://relaytv.local:8787/play"
    assert session.requests[1]["json"] == {"url": "https://media.example/video.mp4", "use_ytdlp": False}
    assert session.requests[2]["json"] == {"text": "Doorbell", "position": "top-center"}
    assert session.requests[3]["url"] == "http://relaytv.local:8787/clear"
    assert session.requests[4]["url"] == "http://relaytv.local:8787/play_temporary/cancel"
    assert session.requests[5]["url"] == "http://relaytv.local:8787/playback/live"
    assert info == {"release_version": "0.11.2"}
