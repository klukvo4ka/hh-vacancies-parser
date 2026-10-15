import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.api.client import HHApiClient, HHApiError
from src.config import HH_USER_AGENT
from tests.helpers import FakeHH

Handler = Callable[[httpx.Request], httpx.Response]
SEARCH_BODY = {"found": 2, "page": 0, "pages": 1, "per_page": 20, "items": [{"id": "1"}, {"id": "2"}]}


def search(handler: Handler, *args: Any, **kwargs: Any) -> dict[str, Any]:
    async def go() -> dict[str, Any]:
        async with HHApiClient(transport=httpx.MockTransport(handler)) as client:
            return await client.search_vacancies(*args, **kwargs)

    return asyncio.run(go())


def search_all(handler: Handler, text: str = "Python developer", **kwargs: Any) -> list[dict[str, Any]]:
    async def go() -> list[dict[str, Any]]:
        async with HHApiClient(transport=httpx.MockTransport(handler)) as client:
            return await client.search_all_vacancies(text, **kwargs)

    return asyncio.run(go())


def respond(status: int, **kwargs: Any) -> Handler:
    return lambda request: httpx.Response(status, **kwargs)


def raising(exc_type: type[httpx.RequestError], message: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc_type(message, request=request)

    return handler


class TestSearchVacancies:
    def test_request_shape(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=SEARCH_BODY)

        data = search(handler, "  Python developer ", page=2, per_page=50)

        request = seen[0]
        assert data == SEARCH_BODY
        assert request.method == "GET"
        assert str(request.url.copy_with(query=None)) == "https://api.hh.ru/vacancies"
        assert dict(request.url.params) == {"text": "Python developer", "page": "2", "per_page": "50"}
        assert request.headers["User-Agent"] == HH_USER_AGENT

    def test_zero_results_are_not_an_error(self) -> None:
        body = {"found": 0, "page": 0, "pages": 0, "per_page": 20, "items": []}
        assert search(respond(200, json=body), "nothing")["items"] == []

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"text": ""}, "must not be empty"),
            ({"text": "   "}, "must not be empty"),
            ({"text": "x", "page": -1}, "page must be >= 0"),
            ({"text": "x", "per_page": 0}, "between 1 and 100"),
            ({"text": "x", "per_page": 101}, "between 1 and 100"),
        ],
    )
    def test_invalid_arguments_raise_before_any_request(self, kwargs: dict[str, Any], message: str) -> None:
        fake = FakeHH(10)
        with pytest.raises(ValueError, match=message):
            search(fake, **kwargs)
        assert fake.requests == []

    @pytest.mark.parametrize(
        ("handler", "message", "cause"),
        [
            (respond(400, json={"errors": [{"type": "bad_argument"}]}), r"HTTP 400 for /vacancies \(bad_argument\)", httpx.HTTPStatusError),
            (respond(403, json={"errors": [{"type": "forbidden"}]}), r"HTTP 403 for /vacancies \(forbidden\)", httpx.HTTPStatusError),
            (respond(500, text="<html>oops</html>"), "HTTP 500 for /vacancies$", httpx.HTTPStatusError),
            (respond(204), "HTTP 204 for /vacancies$", None),
            (raising(httpx.ReadTimeout, "timed out"), "Request to /vacancies timed out", httpx.TimeoutException),
            (raising(httpx.ConnectError, "refused"), "Network error while requesting /vacancies: refused", httpx.ConnectError),
            (respond(200, text="<html>"), "invalid JSON", ValueError),
            (respond(200, json=[1, 2]), "unexpected JSON type", None),
            (respond(200, json={"found": 1}), "'items' list is missing", None),
            (respond(200, json={"items": {"a": 1}}), "'items' list is missing", None),
        ],
        ids=["400", "403", "500", "204", "timeout", "connect", "bad-json", "json-list", "no-items", "items-dict"],
    )
    def test_failures_become_hh_api_error(self, handler: Handler, message: str, cause: type | None) -> None:
        with pytest.raises(HHApiError, match=message) as excinfo:
            search(handler, "Python")
        if cause is not None:
            assert isinstance(excinfo.value.__cause__, cause)

    def test_error_message_does_not_dump_body(self) -> None:
        with pytest.raises(HHApiError) as excinfo:
            search(respond(500, text="x" * 5000), "Python")
        assert len(str(excinfo.value)) < 100

    def test_client_is_closed_after_context_even_on_error(self) -> None:
        client = HHApiClient(transport=httpx.MockTransport(raising(httpx.ConnectError, "down")))

        async def go() -> None:
            async with client:
                await client.search_vacancies("Python")

        with pytest.raises(HHApiError):
            asyncio.run(go())
        assert client._http.is_closed


class TestSearchAllVacancies:
    @pytest.mark.parametrize(
        ("found", "max_vacancies", "per_page", "expected_count", "expected_pages"),
        [
            (42, 500, 100, 42, [0]),
            (150, 500, 100, 150, [0, 1]),
            (300, 500, 100, 300, [0, 1, 2]),
            (230, 500, 100, 230, [0, 1, 2]),
            (1000, 7, 100, 7, [0]),
            (5000, 150, 100, 150, [0, 1]),
            (5000, 100, 50, 100, [0, 1]),
            (0, 500, 100, 0, [0]),
        ],
    )
    def test_stop_conditions_and_request_counts(
        self, found: int, max_vacancies: int, per_page: int, expected_count: int, expected_pages: list[int]
    ) -> None:
        fake = FakeHH(found)
        items = search_all(fake, max_vacancies=max_vacancies, per_page=per_page)
        assert len(items) == expected_count
        assert fake.pages_requested == expected_pages

    def test_returns_flat_list_in_page_order_trimmed_to_limit(self) -> None:
        items = search_all(FakeHH(5000), max_vacancies=150, per_page=100)
        assert [item["id"] for item in items] == [str(i) for i in range(150)]

    @pytest.mark.parametrize(("per_page", "expected_count", "expected_requests"), [(100, 2000, 20), (30, 1980, 66)])
    def test_never_requests_beyond_search_depth(self, per_page: int, expected_count: int, expected_requests: int) -> None:
        fake = FakeHH(10_000)
        items = search_all(fake, max_vacancies=50_000, per_page=per_page)
        assert len(items) == expected_count
        assert len(fake.requests) == expected_requests
        assert all((page + 1) * per_page <= 2000 for page in fake.pages_requested)

    @pytest.mark.parametrize(
        "metadata",
        [{"pages": None}, {"pages": 10**9}, {"pages": "lots", "page": None}, {"page": 0}],
    )
    def test_bad_metadata_cannot_cause_endless_paging(self, metadata: dict[str, Any]) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = {"found": 10**6, "page": 0, "pages": 10**4, "per_page": 100}
            body.update(metadata)
            body["items"] = [{"id": str(i)} for i in range(100)]  # same full page every time
            return httpx.Response(200, json=body)

        items = search_all(handler, max_vacancies=50_000)
        assert len(items) == 2000

    def test_mid_pagination_error_propagates_instead_of_partial_data(self) -> None:
        fake = FakeHH(500, fail_on_page=2)
        with pytest.raises(HHApiError, match="HTTP 503"):
            search_all(fake, max_vacancies=500)
        assert fake.pages_requested == [0, 1, 2]

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"max_vacancies": 0}, "max_vacancies must be >= 1"),
            ({"max_vacancies": -5}, "max_vacancies must be >= 1"),
            ({"per_page": 101}, "between 1 and 100"),
            ({"text": "  "}, "must not be empty"),
        ],
    )
    def test_invalid_arguments_make_no_requests(self, kwargs: dict[str, Any], message: str) -> None:
        fake = FakeHH(100)
        with pytest.raises(ValueError, match=message):
            search_all(fake, **kwargs)
        assert fake.requests == []
