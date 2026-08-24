"""Django system checks registered by :class:`appkit.apps.AppKitConfig.ready`.

Present and safe: registered explicitly from ``ready()``, never picked up implicitly by Django's
own auto-discovery (docs/CONTRACT.md §10's collision-audit table).

Six functions, seven check IDs (docs/CONTRACT.md §6):

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
    appkit.W005 (Warning) — LOGGING is configured but no handler references a
                             filter resolving to appkit.request_id.RequestIDFilter
                             -> check_logging_filter

Every function below is defensive by construction: a system check that raises breaks
``manage.py`` entirely, including the commands someone would use to fix the thing it's
complaining about. Each walks host-provided structures (``MIDDLEWARE``, ``REST_FRAMEWORK``,
``ROOT_URLCONF``, ``LOGGING``) that may be malformed, partially configured, or reference
something unimportable, and every one of those is treated as "nothing to report", never a crash.

Known limit, stated in docs/CONTRACT.md §5: every check below only runs if the host got
``INSTALLED_APPS`` right in the first place — Django never invokes ``ready()`` on an app that
isn't listed, and nothing inside appkit can self-detect that.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning
from django.utils.module_loading import import_string

from appkit import conf
from appkit.request_id import RequestIDFilter

logger = logging.getLogger(__name__)

_REQUEST_ID_MIDDLEWARE = "appkit.request_id.RequestIDMiddleware"
_SECURITY_MIDDLEWARE = "django.middleware.security.SecurityMiddleware"
_DRF_DEFAULT_EXCEPTION_HANDLER = "rest_framework.views.exception_handler"
_APPKIT_EXCEPTION_HANDLER = "appkit.exceptions.standard_exception_handler"


def check_request_id_middleware(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.E001 — Error if ``appkit.request_id.RequestIDMiddleware`` is absent from
    ``MIDDLEWARE``.

    Every error envelope's ``request_id`` field would otherwise silently read ``"-"``, with no
    log line correlating to any other and no exception pointing at the cause.
    """
    middleware = getattr(settings, "MIDDLEWARE", None) or []
    if _REQUEST_ID_MIDDLEWARE in middleware:
        return []
    return [
        Error(
            "appkit.request_id.RequestIDMiddleware is not in MIDDLEWARE.",
            hint=(
                'Add "appkit.request_id.RequestIDMiddleware" to MIDDLEWARE, '
                "right after SecurityMiddleware — docs/CONTRACT.md §8."
            ),
            id="appkit.E001",
        )
    ]


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

    Reads the raw ``REST_FRAMEWORK`` dict rather than DRF's resolved ``api_settings``, and
    compares dotted strings without importing ``appkit.exceptions`` — so "unset" and "set to
    DRF's default" stay distinguishable, and this module never depends on a sibling appkit
    module that isn't itself required for the check to run.
    """
    drf_settings = getattr(settings, "REST_FRAMEWORK", None) or {}
    handler = drf_settings.get("EXCEPTION_HANDLER")

    if handler is None or handler == _DRF_DEFAULT_EXCEPTION_HANDLER:
        return [
            Error(
                "REST_FRAMEWORK['EXCEPTION_HANDLER'] is not set to appkit's handler.",
                hint=(
                    "Set REST_FRAMEWORK['EXCEPTION_HANDLER'] = "
                    f'"{_APPKIT_EXCEPTION_HANDLER}" — docs/CONTRACT.md §8.'
                ),
                id="appkit.E002",
            )
        ]

    if handler != _APPKIT_EXCEPTION_HANDLER:
        return [
            Warning(
                "REST_FRAMEWORK['EXCEPTION_HANDLER'] is set to neither DRF's default nor "
                "appkit.exceptions.standard_exception_handler.",
                hint=(
                    "If this wraps appkit's handler deliberately (e.g. to add a field to the "
                    "envelope), this warning can be silenced via SILENCED_SYSTEM_CHECKS. "
                    f'Otherwise set it to "{_APPKIT_EXCEPTION_HANDLER}" — docs/CONTRACT.md §8.'
                ),
                id="appkit.W001",
            )
        ]

    return []


def check_middleware_order(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W002 — Warning if ``RequestIDMiddleware`` is present but ordered before
    ``SecurityMiddleware`` in ``MIDDLEWARE`` (only evaluated when ``SecurityMiddleware`` is
    present at all).

    A swap doesn't crash anything; it just means the request ID is assigned before security
    headers are considered — order-of-operations debt worth flagging, not blocking.
    """
    middleware = getattr(settings, "MIDDLEWARE", None) or []
    if _REQUEST_ID_MIDDLEWARE not in middleware or _SECURITY_MIDDLEWARE not in middleware:
        return []

    if middleware.index(_REQUEST_ID_MIDDLEWARE) < middleware.index(_SECURITY_MIDDLEWARE):
        return [
            Warning(
                "appkit.request_id.RequestIDMiddleware is ordered before SecurityMiddleware.",
                hint=(
                    "Move it to right after django.middleware.security.SecurityMiddleware in "
                    "MIDDLEWARE — docs/CONTRACT.md §8."
                ),
                id="appkit.W002",
            )
        ]
    return []


def check_unknown_settings_keys(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W003 — Warning if the host's ``APPKIT`` dict contains a key not present in
    ``appkit.conf.DEFAULTS``.

    A typo (``APPKIT = {"CACHE_TIMOUT": 30}``) would otherwise silently use the *default*
    ``CACHE_TIMEOUT`` forever, with the typo'd key simply ignored.
    """
    configured = getattr(settings, "APPKIT", None) or {}
    unknown = sorted(set(configured) - set(conf.DEFAULTS))
    if not unknown:
        return []
    return [
        Warning(
            f"APPKIT contains unrecognised key(s): {', '.join(unknown)}.",
            hint=(
                f"Known APPKIT keys: {', '.join(sorted(conf.DEFAULTS))} "
                "(docs/CONTRACT.md §7). A typo'd key is silently ignored — its value is never "
                "read."
            ),
            id="appkit.W003",
        )
    ]


def check_throttle_scopes(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W004 — Warning if a view reachable by walking ``ROOT_URLCONF`` declares a
    ``throttle_scope`` string with no matching entry in
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``.

    DRF only raises ``AssertionError`` for a missing rate at request time, per request, so a
    typo'd ``throttle_scope`` can ship to production and pass every test that doesn't happen to
    exercise that exact view under throttling.

    Detection scope (docs/CONTRACT.md §6): reliably finds a ``throttle_scope`` class attribute
    on a class-based view reached via ``callback.view_class``/``.cls`` (which covers
    ``@api_view``-decorated function views too, since DRF wraps those in a real class). Does
    **not** detect a scope assigned at runtime inside ``initial()``/``get_throttles()``, a
    viewset choosing a scope per-action, or a scope on a plain function view with no DRF
    wrapper — a clean run is not proof those don't exist somewhere.

    The whole walk is defensive: resolving ``ROOT_URLCONF`` or recursing through
    ``include()``-nested patterns can raise for reasons entirely outside this check's control
    (an unrelated import error in a host's ``urls.py``), and a system check raising breaks
    ``manage.py`` outright — so any failure here is treated as "nothing to report" rather than
    propagated.
    """
    try:
        scopes = _collect_throttle_scopes()
    except Exception:
        # Never let this check crash manage.py — see docstring. Logged, not silent: an
        # unwalkable URLconf is itself worth knowing about, just not at Error severity here.
        logger.debug(
            "appkit.checks.check_throttle_scopes: failed to walk ROOT_URLCONF", exc_info=True
        )
        return []

    if not scopes:
        return []

    drf_settings = getattr(settings, "REST_FRAMEWORK", None) or {}
    known_rates = set((drf_settings.get("DEFAULT_THROTTLE_RATES") or {}).keys())
    missing = sorted(scopes - known_rates)
    if not missing:
        return []

    return [
        Warning(
            f"throttle_scope {scope!r} has no matching "
            "REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] entry.",
            hint=(
                f"Add {scope!r} to REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], or fix the typo "
                "on the view that declares it. DRF only raises at request time for a missing "
                "rate, per request — this can otherwise ship silently."
            ),
            id="appkit.W004",
        )
        for scope in missing
    ]


def _collect_throttle_scopes() -> set[str]:
    """Walk ``ROOT_URLCONF`` and return every ``throttle_scope`` string found on a reachable
    view. Returns an empty set (never raises) if ``ROOT_URLCONF`` is unset, unimportable, or
    the walk otherwise fails — callers treat that identically to "no scopes found".
    """
    from django.urls import URLResolver, get_resolver

    root_urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not root_urlconf:
        return set()

    resolver = get_resolver(root_urlconf)
    scopes: set[str] = set()

    def _walk(patterns: Any) -> None:
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                _walk(pattern.url_patterns)
                continue
            callback = getattr(pattern, "callback", None)
            if callback is None:
                continue
            target = getattr(callback, "view_class", None) or getattr(callback, "cls", None)
            scope = getattr(target, "throttle_scope", None) if target is not None else None
            if isinstance(scope, str) and scope:
                scopes.add(scope)

    _walk(resolver.url_patterns)
    return scopes


def check_logging_filter(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W005 — Warning if ``settings.LOGGING`` is configured but no handler in it
    references a filter resolving to ``appkit.request_id.RequestIDFilter`` (or a subclass).

    Skipped entirely when ``LOGGING`` is unset/empty, or when ``LOGGING_CONFIG is None`` (a
    host managing logging entirely outside Django's ``dictConfig`` integration). Middleware
    running and the contextvar being set doesn't help if nothing ever reads ``record.request_id``
    — any handler stamping the raw ``LogRecord`` (a plain ``%``-style file handler, a
    mail-admins handler) would otherwise log ``request_id="-"`` forever, discovered only while
    correlating a real incident.

    Resolves each filter by what it actually points at, not by name: a host may register
    ``RequestIDFilter`` (or a subclass of it, e.g. to add a field) under any key it likes, so a
    string match on a literal name would both miss legitimate configurations and be trivially
    defeated by a rename. Only warns when **no** handler references a matching filter — a host
    deliberately omitting it from one handler (e.g. mail-admins) is not itself a problem.
    """
    if getattr(settings, "LOGGING_CONFIG", "logging.config.dictConfig") is None:
        return []

    logging_config = getattr(settings, "LOGGING", None) or {}
    if not logging_config:
        return []

    filters = logging_config.get("filters") or {}
    request_id_filter_keys: set[str] = set()
    for name, filter_def in filters.items():
        target = filter_def.get("()") if isinstance(filter_def, dict) else None
        if target is None:
            continue
        try:
            resolved = import_string(target) if isinstance(target, str) else target
        except Exception:
            # An unimportable path is the host's own misconfiguration to discover elsewhere —
            # not a reason for this check to crash. Logged so it isn't silent either.
            logger.debug(
                "appkit.checks.check_logging_filter: could not import filter %r",
                target,
                exc_info=True,
            )
            continue
        if _resolves_to_request_id_filter(resolved):
            request_id_filter_keys.add(name)

    if not request_id_filter_keys:
        return [_missing_filter_warning()]

    handlers = logging_config.get("handlers") or {}
    for handler_def in handlers.values():
        handler_filters = set(handler_def.get("filters") or [])
        if handler_filters & request_id_filter_keys:
            return []

    return [_missing_filter_warning()]


def _resolves_to_request_id_filter(resolved: Any) -> bool:
    if resolved is RequestIDFilter:
        return True
    if isinstance(resolved, type):
        return issubclass(resolved, RequestIDFilter)
    return isinstance(resolved, RequestIDFilter)


def _missing_filter_warning() -> Warning:
    return Warning(
        "LOGGING is configured, but no handler references a filter resolving to "
        "appkit.request_id.RequestIDFilter.",
        hint=(
            'Add \'"request_id": {"()": "appkit.request_id.RequestIDFilter"}\' under '
            "LOGGING['filters'], and \"request_id\" to the relevant handler's "
            '"filters" list — docs/CONTRACT.md §8.'
        ),
        id="appkit.W005",
    )
