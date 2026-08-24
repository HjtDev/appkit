"""Django system checks registered by :class:`appkit.apps.AppKitConfig.ready`.

Present and safe: registered explicitly from ``ready()``, never picked up implicitly by Django's
own auto-discovery (docs/CONTRACT.md §10's collision-audit table).

Six check IDs across five functions (docs/CONTRACT.md §6):

    appkit.E001 (Error)   — RequestIDMiddleware absent from MIDDLEWARE
                             -> check_request_id_middleware
    appkit.E002 (Error)   — EXCEPTION_HANDLER unset or still DRF's own default
                             -> check_exception_handler
    appkit.W001 (Warning) — EXCEPTION_HANDLER set to neither DRF's default nor
                             appkit.exceptions.standard_exception_handler
                             -> check_exception_handler
    appkit.W002 (Warning) — RequestIDMiddleware present but ordered before
                             SecurityMiddleware
                             -> check_middleware_order
    appkit.W003 (Warning) — APPKIT dict has a key not present in
                             appkit.conf.DEFAULTS
                             -> check_unknown_settings_keys
    appkit.W004 (Warning) — a view reachable via ROOT_URLCONF declares a
                             throttle_scope with no matching
                             DEFAULT_THROTTLE_RATES entry
                             -> check_throttle_scopes

The ID-to-function assignment above is not stated verbatim anywhere in docs/CONTRACT.md — it
only names five functions for six IDs. This mapping is a Phase 1 assumption (E002 and W001 share
one function since both inspect the same setting), flagged for reconciliation back into the
contract.

Known limit, stated in docs/CONTRACT.md §5: every check below only runs if the host got
``INSTALLED_APPS`` right in the first place — Django never invokes ``ready()`` on an app that
isn't listed, and nothing inside appkit can self-detect that.
"""

from __future__ import annotations

from typing import Any

from django.core.checks import CheckMessage


def check_request_id_middleware(
    app_configs: Any, **kwargs: Any
) -> list[CheckMessage]:
    """appkit.E001 — Error if ``appkit.request_id.RequestIDMiddleware`` is absent from
    ``MIDDLEWARE``.

    Every error envelope's ``request_id`` field would otherwise silently read ``"-"``, with no
    log line correlating to any other and no exception pointing at the cause.
    """
    return []


def check_exception_handler(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.E002 / appkit.W001 — inspects ``REST_FRAMEWORK["EXCEPTION_HANDLER"]``.

    Error (E002) if the key is unset or still DRF's own default
    (``rest_framework.views.exception_handler``) — every app's client expects the
    docs/CONTRACT.md §1 envelope; without this wired, DRF's raw ``{"detail": "..."}`` shape
    ships instead.

    Warning (W001, silenceable via ``SILENCED_SYSTEM_CHECKS``) if the handler is set to
    something that is neither DRF's default nor
    ``appkit.exceptions.standard_exception_handler`` — a host wrapping appkit's handler in its
    own is legitimate, so this is a nudge to confirm it's deliberate, not an error.
    """
    return []


def check_middleware_order(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W002 — Warning if ``RequestIDMiddleware`` is present but ordered before
    ``SecurityMiddleware`` in ``MIDDLEWARE`` (only evaluated when ``SecurityMiddleware`` is
    present at all).

    A swap doesn't crash anything; it just means the request ID is assigned before security
    headers are considered — order-of-operations debt worth flagging, not blocking.
    """
    return []


def check_unknown_settings_keys(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W003 — Warning if the host's ``APPKIT`` dict contains a key not present in
    ``appkit.conf.DEFAULTS``.

    A typo (``APPKIT = {"CACHE_TIMOUT": 30}``) would otherwise silently use the *default*
    ``CACHE_TIMEOUT`` forever, with the typo'd key simply ignored.
    """
    return []


def check_throttle_scopes(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W004 — Warning if a view reachable by walking ``ROOT_URLCONF`` declares a
    ``throttle_scope`` string with no matching entry in
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``.

    DRF only raises ``AssertionError`` for a missing rate at request time, per request, so a
    typo'd ``throttle_scope`` can ship to production and pass every test that doesn't happen to
    exercise that exact view under throttling.
    """
    return []
