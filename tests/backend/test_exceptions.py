"""`appkit.exceptions` — the standard exception handler and the ten error codes
(docs/CONTRACT.md §1, §2.3)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.test import Client, override_settings
from rest_framework import exceptions as drf_exceptions

from appkit.exceptions import ERROR_CODES, _message_and_details, standard_exception_handler
from appkit.request_id import request_id_var


def test_error_codes_match_the_golden_fixture(golden: Callable[[str], Any]) -> None:
    assert list(ERROR_CODES) == golden("error-codes.json")


def test_message_and_details_falls_back_for_a_bare_scalar() -> None:
    """DRF's own `exception_handler` always wraps a non-list/non-dict `.detail` as
    `{"detail": ...}` before this function ever sees it, so this defensive fallback isn't
    reachable through a real DRF exception — exercised directly to prove it degrades sanely
    rather than raising if that assumption is ever violated.
    """
    message, details = _message_and_details(404, code="not_found")
    assert message == "404"
    assert details == {}


@pytest.mark.parametrize(
    ("exc", "expected_code", "expected_status"),
    [
        (drf_exceptions.ParseError(), "parse_error", 400),
        (drf_exceptions.NotAuthenticated(), "not_authenticated", 401),
        (drf_exceptions.AuthenticationFailed(), "authentication_failed", 401),
        (drf_exceptions.PermissionDenied(), "permission_denied", 403),
        (drf_exceptions.NotFound(), "not_found", 404),
        (drf_exceptions.MethodNotAllowed("POST"), "method_not_allowed", 405),
        (drf_exceptions.Throttled(wait=30), "throttled", 429),
        (drf_exceptions.UnsupportedMediaType("application/xml"), "error", 415),
        (drf_exceptions.NotAcceptable(), "error", 406),
    ],
)
def test_handler_maps_each_drf_exception_to_its_code(
    exc: Exception, expected_code: str, expected_status: int
) -> None:
    response = standard_exception_handler(exc, {})
    assert response is not None
    assert response.status_code == expected_status
    assert response.data["error"]["code"] == expected_code
    assert response.data["error"]["details"] == {}


def test_validation_error_nested_per_field_details_are_preserved() -> None:
    exc = drf_exceptions.ValidationError({"amount": ["This field is required."]})
    response = standard_exception_handler(exc, {})
    assert response is not None
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["details"] == {"amount": ["This field is required."]}
    assert response.data["error"]["message"] == "Validation failed."


def test_validation_error_flat_message_uses_non_field_errors() -> None:
    exc = drf_exceptions.ValidationError("Bad value.")
    response = standard_exception_handler(exc, {})
    assert response is not None
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["message"] == "Bad value."
    assert response.data["error"]["details"] == {"non_field_errors": ["Bad value."]}


def test_plain_http404_is_converted_to_not_found_not_the_catch_all() -> None:
    response = standard_exception_handler(Http404("missing"), {})
    assert response is not None
    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
    assert response.data["error"]["message"] == "missing"


def test_plain_django_permission_denied_is_converted_not_the_catch_all() -> None:
    response = standard_exception_handler(DjangoPermissionDenied("nope"), {})
    assert response is not None
    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_request_id_is_threaded_into_the_envelope() -> None:
    token = request_id_var.set("abc-123")
    try:
        response = standard_exception_handler(drf_exceptions.NotFound(), {})
    finally:
        request_id_var.reset(token)
    assert response is not None
    assert response.data["error"]["request_id"] == "abc-123"


@override_settings(DEBUG=True)
def test_unhandled_exception_with_debug_on_carries_the_real_message() -> None:
    response = standard_exception_handler(RuntimeError("boom"), {})
    assert response is not None
    assert response.status_code == 500
    assert response.data["error"]["code"] == "server_error"
    assert response.data["error"]["message"] == "boom"
    assert response.data["error"]["details"] == {}


@override_settings(DEBUG=False)
def test_unhandled_exception_with_debug_off_never_leaks_the_real_message() -> None:
    response = standard_exception_handler(RuntimeError("boom"), {})
    assert response is not None
    assert response.status_code == 500
    assert response.data["error"]["code"] == "server_error"
    assert response.data["error"]["message"] == "Internal server error."
    assert "boom" not in response.data["error"]["message"]


def test_unhandled_exception_is_logged_before_becoming_a_server_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("ERROR", logger="appkit.exceptions"):
        standard_exception_handler(RuntimeError("boom"), {})
    assert any("Unhandled exception in view" in record.message for record in caplog.records)
    assert any(record.exc_info for record in caplog.records)


def test_every_fixture_code_is_exercised_somewhere_in_this_module(
    golden: Callable[[str], Any],
) -> None:
    exercised = {
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
    }
    assert exercised == set(golden("error-codes.json"))


@override_settings(ROOT_URLCONF="tests.backend.urls_errors")
def test_retry_after_header_survives_a_throttled_response() -> None:
    """A header DRF itself sets — proof the handler rewrites only `response.data`."""
    client = Client()
    client.get("/throttled/", HTTP_ACCEPT="application/json")  # not throttled yet
    response = client.get("/throttled/", HTTP_ACCEPT="application/json")
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.json()["error"]["code"] == "throttled"


@override_settings(ROOT_URLCONF="tests.backend.urls_errors")
def test_www_authenticate_header_survives_a_401_response() -> None:
    """Set by `APIView.handle_exception` before our handler ever runs — proof it survives."""
    client = Client()
    response = client.get("/unauthenticated/", HTTP_ACCEPT="application/json")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate", "").startswith("Basic")
    assert response.json()["error"]["code"] == "not_authenticated"
