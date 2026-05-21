"""Exception hierarchy and HTTP-response → exception mapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class FieldError:
    """A single field-level validation error returned by the upstream API."""

    loc: tuple[str | int, ...]
    msg: str
    type: str

    @property
    def path(self) -> str:
        """Dotted path of the offending field (e.g. ``body.duration_days``)."""
        return ".".join(str(part) for part in self.loc)


class AskiiError(Exception):
    """Base class for every exception raised by the askii client."""


class AskiiTransportError(AskiiError):
    """Network-layer failure before a response was received."""


class AskiiConnectionError(AskiiTransportError):
    """The TCP/TLS connection failed or was reset."""


class AskiiTimeoutError(AskiiTransportError):
    """The request timed out before completing."""


class AskiiAPIError(AskiiError):
    """The server returned a non-2xx response."""

    def __init__(
        self,
        status: int,
        detail: Any,
        *,
        request_id: str | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        self.status = status
        self.detail = detail
        self.request_id = request_id
        self.response = response
        super().__init__(self._format())

    def _format(self) -> str:
        head = f"{self.__class__.__name__}: HTTP {self.status}"
        rid = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{head}{rid}: {self.detail!r}"


class AskiiAuthError(AskiiAPIError):
    """401 or 403 from the upstream API, or missing local credentials."""


class AskiiNotFoundError(AskiiAPIError):
    """404 from the upstream API."""


class AskiiValidationError(AskiiAPIError):
    """422 from the upstream API; ``field_errors`` carries the typed details."""

    def __init__(
        self,
        status: int,
        detail: Any,
        *,
        field_errors: list[FieldError],
        request_id: str | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        self.field_errors = field_errors
        super().__init__(status, detail, request_id=request_id, response=response)


class AskiiRateLimitError(AskiiAPIError):
    """429 from the upstream API; ``retry_after`` is seconds when known."""

    def __init__(
        self,
        status: int,
        detail: Any,
        *,
        retry_after: float | None = None,
        request_id: str | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(status, detail, request_id=request_id, response=response)


class AskiiServerError(AskiiAPIError):
    """5xx from the upstream API; retried by default."""


def _parse_field_errors(detail: Any) -> list[FieldError]:
    if not isinstance(detail, list):
        return []
    out: list[FieldError] = []
    for item in detail:
        if not isinstance(item, dict):
            continue
        loc = item.get("loc") or ()
        if isinstance(loc, list):
            loc_tuple = tuple(loc)
        elif isinstance(loc, tuple):
            loc_tuple = loc
        else:
            loc_tuple = (loc,)
        out.append(
            FieldError(
                loc=loc_tuple,
                msg=str(item.get("msg", "")),
                type=str(item.get("type", "")),
            )
        )
    return out


def _parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _request_id_from(response: httpx.Response) -> str | None:
    for header in ("x-request-id", "x-correlation-id", "request-id"):
        value: str | None = response.headers.get(header)
        if value:
            return value
    return None


def map_response_to_error(response: httpx.Response) -> AskiiAPIError:
    """Translate a non-2xx ``httpx.Response`` into the right typed exception."""
    status = response.status_code
    request_id = _request_id_from(response)
    try:
        body = response.json()
    except Exception:
        body = response.text
    detail = body.get("detail", body) if isinstance(body, dict) else body

    if status in (401, 403):
        return AskiiAuthError(status, detail, request_id=request_id, response=response)
    if status == 404:
        return AskiiNotFoundError(status, detail, request_id=request_id, response=response)
    if status == 422:
        return AskiiValidationError(
            status,
            detail,
            field_errors=_parse_field_errors(detail),
            request_id=request_id,
            response=response,
        )
    if status == 429:
        return AskiiRateLimitError(
            status,
            detail,
            retry_after=_parse_retry_after(response),
            request_id=request_id,
            response=response,
        )
    if 500 <= status < 600:
        return AskiiServerError(status, detail, request_id=request_id, response=response)
    return AskiiAPIError(status, detail, request_id=request_id, response=response)


__all__ = [
    "AskiiError",
    "AskiiTransportError",
    "AskiiConnectionError",
    "AskiiTimeoutError",
    "AskiiAPIError",
    "AskiiAuthError",
    "AskiiNotFoundError",
    "AskiiValidationError",
    "AskiiRateLimitError",
    "AskiiServerError",
    "FieldError",
    "map_response_to_error",
]
