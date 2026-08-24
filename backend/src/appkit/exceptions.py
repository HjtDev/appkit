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
