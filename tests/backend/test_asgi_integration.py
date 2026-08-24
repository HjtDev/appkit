"""Regression guard: `RequestIDMiddleware` once broke every real request because it never
marked itself coroutine-visible to the sync-style middleware wrapping it, and neither
`manage.py check` nor a unit-level middleware test dispatches a real request through the actual
`MIDDLEWARE` chain, so the bug shipped a full phase undetected upstream
(../base-scaffold/backend/config/tests/test_asgi_integration.py).

`django.test.AsyncClient` builds the same `settings.MIDDLEWARE` chain in async mode
(`load_middleware(is_async=True)`) that an ASGI server actually runs in production. Driving it
end-to-end here is what a unit test of `RequestIDMiddleware` in isolation, or a sync
`django.test.Client` request, cannot catch: either one sidesteps exactly the async-adjacency
failure that broke every endpoint upstream.

No async test plugin (pytest-asyncio/anyio) is configured, so the coroutine is driven explicitly
via `asyncio.run()` rather than an `async def` test function — matching the scaffold's own
approach. Unlike the scaffold's `/healthz/`, appkit's `/ping/` touches no model, so this test
needs no database and carries no `@pytest.mark.django_db`.
"""

from __future__ import annotations

import asyncio

from django.test import AsyncClient


def test_ping_200_through_the_real_async_middleware_chain() -> None:
    response = asyncio.run(AsyncClient().get("/ping/"))

    assert response.status_code == 200
    # Proves RequestIDMiddleware actually ran (and its response mutation actually reached the
    # client) rather than being silently dropped by a broken async adjacency upstream.
    request_id = response["X-Request-ID"]
    assert len(request_id) == 32  # uuid4().hex, minted since no header was sent
    assert all(c in "0123456789abcdef" for c in request_id)
