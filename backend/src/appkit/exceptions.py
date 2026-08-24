"""The single DRF exception handler producing the standard error envelope.

Envelope shape, verbatim (docs/CONTRACT.md §1)::

    {"error": {"code": "validation_error", "message": "...", "details": {}, "request_id": "..."}}

``details`` is always present (``{}`` when nothing is field-level). ``request_id`` is the same
correlation ID :data:`appkit.request_id.request_id_var` carries. Headers DRF already sets
(``Retry-After`` on ``throttled``, ``WWW-Authenticate`` on ``not_authenticated``/
``authentication_failed``) are untouched — the handler only ever rewrites ``response.data``.

The code set is TEN, not nine (docs/CONTRACT.md §1's documented drift correction) — ``"error"``
is the documented catch-all for any ``APIException`` DRF resolved to a response but that isn't
one of the other nine specific types. For ``"error"``, the HTTP status is authoritative, not the
code.

Public surface, implemented in a later phase:

    ERROR_CODES: Final[tuple[str, ...]]
        The ten codes, in this exact order:
        validation_error, parse_error, not_authenticated, authentication_failed,
        permission_denied, not_found, method_not_allowed, throttled, server_error, error.
        Pinned against tests/fixtures/error-codes.json (docs/CONTRACT.md §19), not hand-verified
        against the frontend's ApiErrorCode union directly.

    standard_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None
        A plain Django Http404/PermissionDenied is converted to its DRF equivalent before code
        lookup. An unhandled exception (DRF's handler returns None) is logged via
        logger.exception before being turned into a server_error envelope. Three own
        user-facing strings — "Validation failed.", "Request failed.", "Internal server
        error." — are wrapped in gettext_lazy.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from appkit.request_id import request_id_var

__all__ = ["ERROR_CODES", "standard_exception_handler"]

logger = logging.getLogger(__name__)

#: The ten codes, in the exact order given in docs/CONTRACT.md §1 — pinned against
#: tests/fixtures/error-codes.json rather than hand-verified against the frontend's
#: ApiErrorCode union directly (docs/CONTRACT.md §19).
ERROR_CODES: Final[tuple[str, ...]] = (
    "validation_error",
    "parse_error",
    "not_authenticated",
    "authentication_failed",
    "permission_denied",
    "not_found",
    "method_not_allowed",
    "throttled",
    "server_error",
    "error",
)

# Ordered most-specific-first: several of these subclass one another, so isinstance order
# matters — this is a straight port of the scaffold's list (docs/CONTRACT.md §1, §2.3).
_CODE_BY_EXCEPTION: list[tuple[type[Exception], str]] = [
    (drf_exceptions.ValidationError, "validation_error"),
    (drf_exceptions.ParseError, "parse_error"),
    (drf_exceptions.NotAuthenticated, "not_authenticated"),
    (drf_exceptions.AuthenticationFailed, "authentication_failed"),
    (drf_exceptions.PermissionDenied, "permission_denied"),
    (drf_exceptions.NotFound, "not_found"),
    (drf_exceptions.MethodNotAllowed, "method_not_allowed"),
    (drf_exceptions.Throttled, "throttled"),
]


def _code_for(exc: Exception) -> str:
    for exc_type, code in _CODE_BY_EXCEPTION:
        if isinstance(exc, exc_type):
            return code
    return "error"  # the documented catch-all — some other APIException DRF already resolved


def _message_and_details(data: Any, *, code: str) -> tuple[str, dict[str, Any]]:
    """Splits DRF's raw `response.data` into a flat message plus a details dict.

    A nested per-field dict (a serializer's validation errors) is passed through as `details`
    intact — the naive flat-message collapse used below must not fire for this case, or which
    field each message belongs to is lost.
    """
    if isinstance(data, dict) and set(data) == {"detail"}:
        return str(data["detail"]), {}
    if isinstance(data, list):
        return "; ".join(str(item) for item in data), {"non_field_errors": data}
    if isinstance(data, dict):
        message = (
            str(_("Validation failed."))
            if code == "validation_error"
            else str(_("Request failed."))
        )
        return message, data
    return str(data), {}


def standard_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF `EXCEPTION_HANDLER` producing the envelope described in this module's docstring.

    Delegates to DRF's own `exception_handler` first and rewrites only `response.data` —
    never rebuilds the `Response` from scratch — so headers DRF already set (`Retry-After`
    on a throttled response, `WWW-Authenticate` on a 401) survive untouched.
    """
    # DRF's own exception_handler converts a plain Django Http404/PermissionDenied into its
    # DRF equivalent internally, on a *new* exception object it builds and discards — it never
    # hands that conversion back to us. Without redoing it here, _code_for(exc) below would see
    # the original Http404/PermissionDenied, match nothing, and fall through to "error".
    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound(*exc.args)
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exceptions.PermissionDenied(*exc.args)

    response = drf_exception_handler(exc, context)

    if response is None:
        # DRF returns None for anything that isn't an APIException/Http404/PermissionDenied —
        # a genuinely unhandled exception. That would otherwise propagate to Django's own error
        # handling (which is what triggers `django.request` logging and Sentry capture) —
        # returning a 500 envelope here instead swallows that unless we log explicitly first.
        logger.exception("Unhandled exception in view", exc_info=exc)
        message = str(exc) if settings.DEBUG else str(_("Internal server error."))
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": message,
                    "details": {},
                    "request_id": request_id_var.get(),
                }
            },
            status=500,
        )

    code = _code_for(exc)
    message, details = _message_and_details(response.data, code=code)
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id_var.get(),
        }
    }
    return response
