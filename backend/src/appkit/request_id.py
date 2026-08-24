"""Request-ID correlation — ContextVar, ASGI middleware, and logging filter, co-located.

There is deliberately no ``appkit.logging`` module (docs/CONTRACT.md §2 preamble, §4): the
``RequestIDFilter`` lives here, alongside the ``ContextVar`` and middleware it serves — exactly
how ``../base-scaffold/backend/config/logging.py`` co-locates all three in one file today. This
is a **port**, not a reimplementation: that file already worked out this module's sharp edges
over two phases, and docs/CONTRACT.md §2.4 freezes the behaviour below as contract.

No ``build_logging_config``, no ``structlog`` processor, no ``structlog`` dependency — log
rendering is host policy (docs/CONTRACT.md §4). Only the three names below are appkit's; a host
imports them into its own ``config/logging.py`` (docs/CONTRACT.md §8) and keeps everything else
about how logs are rendered exactly where it already is.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from asgiref.sync import markcoroutinefunction
from django.http import HttpRequest, HttpResponse

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Caps how much of an inbound X-Request-ID we trust, and restricts it to characters that
# can't inject newlines or control sequences into a log line.
_MAX_REQUEST_ID_LEN = 64
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]+$")


def _clean_request_id(raw: str | None) -> str:
    """Accept an inbound X-Request-ID if it looks safe, else mint a new one."""
    if raw and len(raw) <= _MAX_REQUEST_ID_LEN and _VALID_REQUEST_ID.match(raw):
        return raw
    return uuid.uuid4().hex


class RequestIDMiddleware:
    """Assigns/propagates a request ID for log correlation, and echoes it on the response.

    Implemented as an async middleware (``async_capable = True``, ``sync_capable = False``):
    a sync-only middleware would force Django to run the whole chain through a thread pool,
    quietly undoing the reason a host is on ASGI in the first place. Belongs near the top of
    ``MIDDLEWARE`` — after ``SecurityMiddleware``, before anything that logs
    (docs/CONTRACT.md §8, checked by :func:`appkit.checks.check_middleware_order`).
    """

    sync_capable = False
    async_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], Awaitable[HttpResponse]]) -> None:
        self.get_response = get_response
        # `sync_capable`/`async_capable` only tell Django's *own* `load_middleware` how to
        # build this middleware's wrapper — they say nothing to a generic
        # `inspect.iscoroutinefunction(instance)` check, which is what any middleware
        # WRAPPING this one (e.g. SecurityMiddleware, via django.utils.deprecation's
        # MiddlewareMixin) uses to decide whether to `await` it. Without this explicit
        # mark, an instance's `async def __call__` is invisible to that check — Django's
        # own `MiddlewareMixin` does this same marking internally; a raw, non-Mixin async
        # middleware has to do it itself, or every outer sync-style middleware calls this
        # one without awaiting it, crashing on the returned coroutine. Confirmed to break
        # every real request (ASGI and WSGI both) without this line.
        markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = _clean_request_id(request.headers.get("X-Request-ID"))
        # Always reset in `finally` — under ASGI concurrency, a set-without-reset leaks
        # this request's ID into whatever runs next on the same task (most visibly, a
        # Celery task enqueued mid-request, or an unrelated request if something goes wrong).
        # This also covers the view raising: `reset` still runs before the exception
        # propagates further up the middleware stack.
        token = request_id_var.set(request_id)
        try:
            response = await self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        return response


class RequestIDFilter(logging.Filter):
    """Stamps `record.request_id` from the contextvar, for any handler/formatter that reads
    the raw `LogRecord` rather than a structlog event dict (e.g. a plain %-style file handler).
    Never raises — logging outside a request cycle (management commands, Celery tasks, process
    startup) must still work, defaulting to "-". This contract is what
    :func:`appkit.checks.check_logging_filter` (``appkit.W005``) exists to catch a host
    forgetting to wire up, and what ``appkit.testing``'s ``frozen_request_id`` fixture makes
    directly assertable from a consuming app's own tests.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
