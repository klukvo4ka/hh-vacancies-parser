import httpx

from src.config import HH_REQUEST_TIMEOUT, HH_TOKEN_URL, HH_USER_AGENT


class HHAuthError(RuntimeError):
    """Raised when HH credentials are misconfigured or an application token cannot be obtained."""


async def resolve_access_token(
    access_token: str | None,
    client_id: str | None,
    client_secret: str | None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """Pick the token for this run: explicit token, then application credentials, then anonymous (None)."""
    access_token = _blank_to_none(access_token)
    client_id = _blank_to_none(client_id)
    client_secret = _blank_to_none(client_secret)

    if access_token:
        return access_token
    if client_id and client_secret:
        return await get_application_token(client_id, client_secret, transport=transport)
    if client_id or client_secret:
        raise HHAuthError("Incomplete HH credentials: set both HH_CLIENT_ID and HH_CLIENT_SECRET")
    return None


async def get_application_token(
    client_id: str,
    client_secret: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Request a new application token (grant_type=client_credentials).

    HH revokes the previously issued application token on each new request
    and allows at most one request every 5 minutes.
    """
    form = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    async with httpx.AsyncClient(
        headers={"User-Agent": HH_USER_AGENT},
        timeout=HH_REQUEST_TIMEOUT,
        transport=transport,
    ) as http:
        try:
            response = await http.post(HH_TOKEN_URL, data=form)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HHAuthError("HH token request timed out") from exc
        except httpx.HTTPStatusError as exc:
            detail = _oauth_error(exc.response)
            suffix = f" ({detail})" if detail else ""
            raise HHAuthError(f"Failed to obtain HH application token: HTTP {exc.response.status_code}{suffix}") from exc
        except httpx.RequestError as exc:
            raise HHAuthError(f"Network error while requesting HH application token: {exc}") from exc

    if response.status_code != 200:
        raise HHAuthError(f"Failed to obtain HH application token: HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise HHAuthError("HH token response is not valid JSON") from exc

    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise HHAuthError("HH token response did not contain access_token")
    return token.strip()


def _oauth_error(response: httpx.Response) -> str:
    """Return HH's short OAuth error code/description (e.g. 'invalid_client') without the body."""
    try:
        data = response.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    parts = [data.get("error"), data.get("error_description")]
    return ": ".join(part for part in parts if isinstance(part, str) and part and len(part) <= 100)


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
