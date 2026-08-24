"""Request-ID correlation — ContextVar, ASGI middleware, and logging filter, co-located.

There is deliberately no ``appkit.logging`` module (docs/CONTRACT.md §2 preamble): the
``RequestIDFilter`` lives here, alongside the ``ContextVar`` and middleware it serves — exactly
how the scaffold co-locates all three in one file today.

Public surface (docs/CONTRACT.md §2.4), implemented in a later phase:

    request_id_var: ContextVar[str]
        Default "-".

    class RequestIDMiddleware:
        sync_capable = False
        async_capable = True

        def __init__(self, get_response: Callable[[HttpRequest], Awaitable[HttpResponse]]): ...
        async def __call__(self, request: HttpRequest) -> HttpResponse: ...

        Inbound X-Request-ID is length-capped at 64 chars and matched against
        ``^[A-Za-z0-9-]+$``; otherwise a fresh uuid4().hex is generated. Echoed back via
        ``response["X-Request-ID"]``. Resets request_id_var to "-" (or the prior value) in a
        finally block on the way out — this reset-in-finally contract is what
        appkit.testing's frozen_request_id fixture asserts.

    class RequestIDFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool: ...
"""

from __future__ import annotations
