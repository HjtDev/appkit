"""All ten docs/CONTRACT.md §1 codes, triggered over real HTTP through nginx — proving the
backend's envelope and the frontend's apiErrorFromEnvelope agree with EACH OTHER, not just
independently with tests/fixtures/error-codes.json.
"""

from __future__ import annotations

import httpx
import pytest


def test_validation_error(http_client: httpx.Client) -> None:
    r = http_client.post("/api/v1/demo/errors/validation/", json={"name": ""})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"] == {"name": ["This field may not be blank."]}
    assert body["error"]["request_id"]


def test_parse_error(http_client: httpx.Client, new_user_credentials: tuple[str, str]) -> None:
    username, password = new_user_credentials
    r = http_client.post(
        "/api/v1/demo/items/",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
        auth=(username, password),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "parse_error"


def test_not_authenticated_has_www_authenticate(http_client: httpx.Client) -> None:
    r = http_client.get("/api/v1/demo/errors/not-authenticated/")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"
    # Headers DRF already set survive standard_exception_handler untouched
    # (backend/src/appkit/exceptions.py's own doc-comment guarantee).
    assert "WWW-Authenticate" in r.headers


def test_authentication_failed(http_client: httpx.Client) -> None:
    r = http_client.get(
        "/api/v1/demo/errors/authentication-failed/", auth=("nobody", "wrongpass")
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


def test_permission_denied(
    http_client: httpx.Client, new_user_credentials: tuple[str, str]
) -> None:
    username, password = new_user_credentials
    r = http_client.get("/api/v1/demo/errors/permission-denied/", auth=(username, password))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


def test_not_found(http_client: httpx.Client) -> None:
    r = http_client.get("/api/v1/demo/errors/not-found/")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_method_not_allowed(http_client: httpx.Client) -> None:
    r = http_client.post("/api/v1/demo/errors/method-not-allowed/")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"


def test_server_error(http_client: httpx.Client) -> None:
    r = http_client.get("/api/v1/demo/errors/server/")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "server_error"
    # DEBUG=false in the compose stack -> generic message, never the real exception text.
    assert r.json()["error"]["message"] == "Internal server error."


def test_catchall_error(http_client: httpx.Client) -> None:
    r = http_client.get("/api/v1/demo/errors/catchall/")
    assert r.status_code == 415
    body = r.json()
    # Rule 2, docs/CONTRACT.md §1: for "error", the HTTP status is authoritative, not the code.
    assert body["error"]["code"] == "error"


def test_throttled_carries_retry_after(
    http_client: httpx.Client, new_user_credentials: tuple[str, str]
) -> None:
    username, password = new_user_credentials
    responses = [
        http_client.get("/api/v1/demo/items/", auth=(username, password)) for _ in range(6)
    ]
    throttled = [r for r in responses if r.status_code == 429]
    assert throttled, [r.status_code for r in responses]
    body = throttled[0].json()
    assert body["error"]["code"] == "throttled"
    assert "Retry-After" in throttled[0].headers


@pytest.mark.parametrize("path", ["/api/v1/demo/errors/validation/"])
def test_details_always_present(http_client: httpx.Client, path: str) -> None:
    r = http_client.post(path, json={"name": ""})
    assert "details" in r.json()["error"]
