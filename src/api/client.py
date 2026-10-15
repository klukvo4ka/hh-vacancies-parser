from types import TracebackType
from typing import Any, Self

import httpx

from src.config import HH_API_BASE_URL, HH_MAX_PER_PAGE, HH_REQUEST_TIMEOUT, HH_USER_AGENT


class HHApiError(RuntimeError):
    """Raised when the HeadHunter API request fails or returns an unexpected response."""


class HHApiClient:
    def __init__(
        self,
        *,
        timeout: float = HH_REQUEST_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=HH_API_BASE_URL,
            headers={"User-Agent": HH_USER_AGENT},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def search_vacancies(
        self,
        text: str,
        *,
        page: int = 0,
        per_page: int = 20,
    ) -> dict[str, Any]:
        _validate_search_params(text, page, per_page)
        params = {"text": text.strip(), "page": page, "per_page": per_page}
        data = await self._get_json("/vacancies", params)

        if not isinstance(data.get("items"), list):
            raise HHApiError("Unexpected /vacancies response: 'items' list is missing")
        return data

    async def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http.get(path, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HHApiError(f"Request to {path} timed out") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _error_types(exc.response)
            suffix = f" ({detail})" if detail else ""
            raise HHApiError(f"HH API returned HTTP {status} for {path}{suffix}") from exc
        except httpx.RequestError as exc:
            raise HHApiError(f"Network error while requesting {path}: {exc}") from exc

        if response.status_code != 200:
            raise HHApiError(f"HH API returned HTTP {response.status_code} for {path}")

        try:
            data = response.json()
        except ValueError as exc:
            raise HHApiError(f"HH API returned invalid JSON for {path}") from exc

        if not isinstance(data, dict):
            raise HHApiError(f"HH API returned unexpected JSON type for {path}")
        return data


def _error_types(response: httpx.Response) -> str:
    """Extract HH error types such as 'bad_user_agent' without dumping the body."""
    try:
        errors = response.json().get("errors", [])
        return ", ".join(str(error["type"]) for error in errors if "type" in error)
    except (ValueError, AttributeError, TypeError):
        return ""


def _validate_search_params(text: str, page: int, per_page: int) -> None:
    if not text.strip():
        raise ValueError("Search text must not be empty")
    if page < 0:
        raise ValueError(f"page must be >= 0, got {page}")
    if not 1 <= per_page <= HH_MAX_PER_PAGE:
        raise ValueError(f"per_page must be between 1 and {HH_MAX_PER_PAGE}, got {per_page}")
