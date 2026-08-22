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
