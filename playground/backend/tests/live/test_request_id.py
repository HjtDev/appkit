"""Request-ID correlation under real concurrency — the one thing no unit test can prove, since
appkit.request_id.RequestIDMiddleware is async-only specifically so it works correctly under
real concurrent request handling (backend/src/appkit/request_id.py's own docstring).
"""

from __future__ import annotations

import re
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from tests.live.conftest import BACKEND_CONTAINER


def test_request_id_is_echoed_on_response(http_client: httpx.Client) -> None:
    r = http_client.get("/api/v1/demo/echo/")
    header_id = r.headers["X-Request-ID"]
    body_id = r.json()["request_id"]
    assert header_id == body_id
    assert re.fullmatch(r"[A-Za-z0-9-]+", header_id)


def test_inbound_request_id_is_honoured(http_client: httpx.Client) -> None:
    sent = f"live-{uuid.uuid4().hex}"
    r = http_client.get("/api/v1/demo/echo/", headers={"X-Request-ID": sent})
    assert r.headers["X-Request-ID"] == sent
    assert r.json()["request_id"] == sent


def test_malformed_inbound_request_id_is_replaced(http_client: httpx.Client) -> None:
    # Contains a space and exceeds the 64-char cap and the [A-Za-z0-9-]+ pattern
    # (backend/src/appkit/request_id.py) — must be discarded, never echoed back unsanitized.
    bad = "not valid!! " + ("x" * 100)
    r = http_client.get("/api/v1/demo/echo/", headers={"X-Request-ID": bad})
    assert r.headers["X-Request-ID"] != bad
    assert re.fullmatch(r"[A-Za-z0-9-]+", r.headers["X-Request-ID"])


def test_request_id_appears_in_backend_logs(http_client: httpx.Client) -> None:
    """Hits /errors/server/, not /echo/ — deliberately. A 200 response (like /echo/) produces
    NO Django log line at all by default, and the ONLY log line Django's own `django.request`
    auto-logger emits for a 4xx/5xx is structurally unable to carry the ID (see
    test_django_request_autologger_never_carries_the_id below) — a request handled inside
    application code and logged from there (appkit.exceptions.standard_exception_handler's own
    `logger.exception(...)` call, backend/src/appkit/exceptions.py:134) is the log line that
    actually proves correlation end-to-end.
    """
    import subprocess

    sent = f"live-logcheck-{uuid.uuid4().hex[:12]}"
    http_client.get("/api/v1/demo/errors/server/", headers={"X-Request-ID": sent})

    logs = subprocess.run(  # noqa: S603
        ["docker", "logs", "--tail", "200", BACKEND_CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    output = logs.stdout + logs.stderr
    exception_lines = [line for line in output.splitlines() if "appkit.exceptions" in line]
    assert exception_lines, "expected an appkit.exceptions log line from the 500 above"
    assert any(sent in line for line in exception_lines), (
        f"request ID {sent!r} never appeared in appkit.exceptions's own log line: {exception_lines}"
    )


def test_django_request_autologger_never_carries_the_id(http_client: httpx.Client) -> None:
    """Documents a real, structural gap (see playground/FINDINGS.md): django/core/handlers/
    base.py's OWN `get_response_async` awaits `self._middleware_chain(request)` to completion
    — meaning RequestIDMiddleware's `finally: request_id_var.reset(token)` has ALREADY run —
    before calling `log_response()` for any 4xx/5xx response. Django's built-in `django.request`
    warning/error logs are therefore ALWAYS stamped "-", regardless of MIDDLEWARE order. This
    is not a flake and not fixable by reordering middleware; it is structural to where Django's
    BaseHandler logs relative to the middleware chain it awaits.
    """
    import subprocess

    r = http_client.get("/api/v1/demo/errors/not-found/")
    assert r.status_code == 404
    my_id = r.headers["X-Request-ID"]

    logs = subprocess.run(  # noqa: S603
        ["docker", "logs", "--tail", "50", BACKEND_CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    output = logs.stdout + logs.stderr
    request_log_lines = [line for line in output.splitlines() if "django.request" in line]
    assert request_log_lines, "expected at least one django.request log line from the 404 above"
    assert not any(my_id in line for line in request_log_lines)
    assert any("[-]" in line for line in request_log_lines[-3:])


def test_no_id_bleed_under_concurrency(http_client: httpx.Client) -> None:
    """A dozen requests in parallel, each with its own X-Request-ID — the contextvar leak this
    guards against only manifests under real concurrent request handling, which is exactly what
    Django's synchronous test client (used everywhere else in this repo) can never provide.
    """
    sent_ids = [f"live-concurrent-{i}-{uuid.uuid4().hex[:8]}" for i in range(12)]

    def fetch(request_id: str) -> tuple[str, str]:
        r = http_client.get("/api/v1/demo/echo/", headers={"X-Request-ID": request_id})
        return request_id, r.json()["request_id"]

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(fetch, sent_ids))

    for sent, echoed in results:
        assert sent == echoed, f"ID bleed: sent {sent!r}, server echoed {echoed!r}"
