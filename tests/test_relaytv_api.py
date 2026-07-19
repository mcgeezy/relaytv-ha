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
