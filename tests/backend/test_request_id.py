"""`appkit.request_id` — the contextvar, the ASGI middleware, and the logging filter.

Ported from ../base-scaffold/backend/config/tests/test_logging.py's request-ID tests, minus its
build_logging_config tests (no such function exists here — docs/CONTRACT.md §4). Extended with
the one case the scaffold's own suite doesn't cover: the contextvar resetting after a view that
*raises*, not only after a 200 — that's the failure mode `finally` exists to close.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from appkit.request_id import RequestIDFilter, RequestIDMiddleware, request_id_var

factory = RequestFactory()


async def _stub_get_response(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


async def _raising_get_response(request: HttpRequest) -> HttpResponse:
    raise ValueError("boom")


def _run_middleware(request: HttpRequest) -> HttpResponse:
    middleware = RequestIDMiddleware(_stub_get_response)
    return asyncio.run(middleware(request))


def test_mints_an_id_when_no_header_is_present() -> None:
    response = _run_middleware(factory.get("/"))
    request_id = response["X-Request-ID"]
    assert len(request_id) == 32
    assert all(c in "0123456789abcdef" for c in request_id)  # uuid4().hex


def test_propagates_a_valid_inbound_request_id() -> None:
    response = _run_middleware(factory.get("/", HTTP_X_REQUEST_ID="abc-123"))
    assert response["X-Request-ID"] == "abc-123"


def test_replaces_a_malformed_inbound_request_id() -> None:
    response = _run_middleware(factory.get("/", HTTP_X_REQUEST_ID="bad id; with spaces"))
    assert response["X-Request-ID"] != "bad id; with spaces"
    assert len(response["X-Request-ID"]) == 32


def test_replaces_an_over_length_inbound_request_id() -> None:
    too_long = "a" * 65
    response = _run_middleware(factory.get("/", HTTP_X_REQUEST_ID=too_long))
    assert response["X-Request-ID"] != too_long
    assert len(response["X-Request-ID"]) == 32


def test_resets_the_contextvar_after_a_successful_response() -> None:
    _run_middleware(factory.get("/", HTTP_X_REQUEST_ID="reset-check"))
    assert request_id_var.get() == "-"


def test_resets_the_contextvar_after_the_view_raises() -> None:
    """docs/CONTRACT.md §2.4's non-obvious failure path: a view that raises must still reset
    the contextvar via the `finally` block, not only the success path.
    """
    middleware = RequestIDMiddleware(_raising_get_response)
    request = factory.get("/", HTTP_X_REQUEST_ID="raise-check")

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(middleware(request))

    assert request_id_var.get() == "-"


def test_request_id_filter_defaults_to_dash_outside_a_request_cycle() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
    assert RequestIDFilter().filter(record) is True
    assert record.request_id == "-"  # type: ignore[attr-defined]


def test_request_id_filter_reads_the_contextvar_when_set() -> None:
    token = request_id_var.set("filter-check")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
        assert RequestIDFilter().filter(record) is True
        assert record.request_id == "filter-check"  # type: ignore[attr-defined]
    finally:
        request_id_var.reset(token)
