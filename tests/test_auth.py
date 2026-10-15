import asyncio
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from src.api.auth import HHAuthError, get_application_token, resolve_access_token
from src.api.client import HHApiClient
from src.config import HH_USER_AGENT, env_value
from tests.helpers import FakeHH

Handler = Callable[[httpx.Request], httpx.Response]

FAKE_TOKEN = "fake-access-token-for-tests"
FAKE_APP_TOKEN = "fake-application-token-for-tests"
FAKE_CLIENT_ID = "fake-client-id"
FAKE_SECRET = "fake-client-secret-do-not-leak"


class TokenEndpoint:
    """Fake POST https://api.hh.ru/token that records requests."""

    def __init__(self, status: int = 200, **response: Any) -> None:
        self.status = status
        self.response = response or {"json": {"access_token": FAKE_APP_TOKEN, "token_type": "bearer"}}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, **self.response)


def request_token(handler: Handler) -> str:
    return asyncio.run(get_application_token(FAKE_CLIENT_ID, FAKE_SECRET, transport=httpx.MockTransport(handler)))


def resolve(access_token: str | None, client_id: str | None, client_secret: str | None, handler: Handler) -> str | None:
    return asyncio.run(
        resolve_access_token(access_token, client_id, client_secret, transport=httpx.MockTransport(handler))
    )


class TestEnvironmentConfig:
    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_blank_values_are_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("HH_TEST_VALUE", value)
        assert env_value("HH_TEST_VALUE") is None

    def test_values_are_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HH_TEST_VALUE", "  abc  ")
        assert env_value("HH_TEST_VALUE") == "abc"

    def test_missing_variable_is_none(self) -> None:
        assert env_value("HH_SURELY_NOT_SET_12345") is None


class TestResolveAccessToken:
    def test_nothing_configured_means_anonymous(self) -> None:
        endpoint = TokenEndpoint()
        assert resolve(None, None, None, endpoint) is None
        assert endpoint.requests == []

    def test_access_token_is_used_directly(self) -> None:
        endpoint = TokenEndpoint()
        assert resolve(FAKE_TOKEN, None, None, endpoint) == FAKE_TOKEN
        assert endpoint.requests == []

    def test_client_credentials_request_application_token(self) -> None:
        endpoint = TokenEndpoint()
        assert resolve(None, FAKE_CLIENT_ID, FAKE_SECRET, endpoint) == FAKE_APP_TOKEN
        assert len(endpoint.requests) == 1

    def test_access_token_wins_over_client_credentials(self) -> None:
        endpoint = TokenEndpoint()
        assert resolve(FAKE_TOKEN, FAKE_CLIENT_ID, FAKE_SECRET, endpoint) == FAKE_TOKEN
        assert endpoint.requests == []

    @pytest.mark.parametrize(
        ("client_id", "client_secret"),
        [(FAKE_CLIENT_ID, None), (None, FAKE_SECRET), (FAKE_CLIENT_ID, "  "), ("", FAKE_SECRET)],
    )
    def test_half_configured_credentials_are_an_error(self, client_id: str | None, client_secret: str | None) -> None:
        endpoint = TokenEndpoint()
        with pytest.raises(HHAuthError, match="set both HH_CLIENT_ID and HH_CLIENT_SECRET"):
            resolve(None, client_id, client_secret, endpoint)
        assert endpoint.requests == []

    def test_blank_strings_are_treated_as_absent(self) -> None:
        endpoint = TokenEndpoint()
        assert resolve("  ", "", " ", endpoint) is None
        assert resolve("", FAKE_CLIENT_ID, FAKE_SECRET, endpoint) == FAKE_APP_TOKEN


class TestApplicationTokenRequest:
    def test_request_shape(self) -> None:
        endpoint = TokenEndpoint()
        assert request_token(endpoint) == FAKE_APP_TOKEN

        request = endpoint.requests[0]
        assert request.method == "POST"
        assert str(request.url) == "https://api.hh.ru/token"
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert request.headers["User-Agent"] == HH_USER_AGENT
        assert "Authorization" not in request.headers
        assert parse_qs(request.content.decode()) == {
            "grant_type": ["client_credentials"],
            "client_id": [FAKE_CLIENT_ID],
            "client_secret": [FAKE_SECRET],
        }
        assert FAKE_SECRET not in str(request.url)

    @pytest.mark.parametrize(
        ("endpoint", "message"),
        [
            (
                TokenEndpoint(400, json={"error": "invalid_client", "error_description": "account not found"}),
                r"HTTP 400 \(invalid_client: account not found\)",
            ),
            (TokenEndpoint(403, json={"errors": [{"type": "forbidden"}]}), "HTTP 403$"),
            (TokenEndpoint(500, text="<html>" + "x" * 5000), "HTTP 500$"),
            (TokenEndpoint(204), "HTTP 204$"),
            (TokenEndpoint(200, text="not json"), "not valid JSON"),
            (TokenEndpoint(200, json=["token"]), "did not contain access_token"),
            (TokenEndpoint(200, json={"token_type": "bearer"}), "did not contain access_token"),
            (TokenEndpoint(200, json={"access_token": "", "token_type": "bearer"}), "did not contain access_token"),
            (TokenEndpoint(200, json={"access_token": 12345}), "did not contain access_token"),
        ],
        ids=["400", "403", "500", "204", "bad-json", "json-list", "missing", "empty", "not-string"],
    )
    def test_failures_raise_hh_auth_error(self, endpoint: TokenEndpoint, message: str) -> None:
        with pytest.raises(HHAuthError, match=message):
            request_token(endpoint)

    @pytest.mark.parametrize(
        ("exc_type", "message"),
        [(httpx.ReadTimeout, "HH token request timed out"), (httpx.ConnectError, "Network error while requesting HH application token")],
    )
    def test_network_failures_raise_hh_auth_error(self, exc_type: type[httpx.RequestError], message: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise exc_type("boom", request=request)

        with pytest.raises(HHAuthError, match=message) as excinfo:
            request_token(handler)
        assert isinstance(excinfo.value.__cause__, exc_type)

    @pytest.mark.parametrize(
        "response",
        [
            {"status": 400, "json": {"error": "invalid_client", "error_description": FAKE_SECRET + "x" * 100}},
            {"status": 400, "json": {"error": "invalid_request", "client_secret": FAKE_SECRET}},
            {"status": 200, "json": {"token": FAKE_APP_TOKEN}},
            {"status": 500, "text": f"secret={FAKE_SECRET}"},
        ],
    )
    def test_error_messages_never_contain_secrets(self, response: dict[str, Any]) -> None:
        status = response.pop("status")
        with pytest.raises(HHAuthError) as excinfo:
            request_token(TokenEndpoint(status, **response))
        message = str(excinfo.value)
        assert FAKE_SECRET not in message and FAKE_APP_TOKEN not in message and FAKE_CLIENT_ID not in message


class TestApiClientAuthorization:
    def search_all(self, fake: FakeHH, access_token: str | None) -> None:
        async def go() -> None:
            async with HHApiClient(access_token=access_token, transport=httpx.MockTransport(fake)) as client:
                await client.search_all_vacancies("Python", max_vacancies=300)

        asyncio.run(go())

    def test_anonymous_client_sends_no_authorization_header(self) -> None:
        fake = FakeHH(500)
        self.search_all(fake, None)
        assert all("Authorization" not in request.headers for request in fake.requests)

    @pytest.mark.parametrize("token", ["", None])
    def test_empty_token_is_anonymous(self, token: str | None) -> None:
        fake = FakeHH(10)
        self.search_all(fake, token)
        assert "Authorization" not in fake.requests[0].headers

    def test_bearer_header_on_every_page_and_user_agent_unchanged(self) -> None:
        fake = FakeHH(500)
        self.search_all(fake, FAKE_TOKEN)
        assert len(fake.requests) == 3
        for request in fake.requests:
            assert request.headers["Authorization"] == f"Bearer {FAKE_TOKEN}"
            assert request.headers["User-Agent"] == HH_USER_AGENT
