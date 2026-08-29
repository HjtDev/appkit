"""Django system checks registered by :class:`appkit.apps.AppKitConfig.ready`.

Present and safe: registered explicitly from ``ready()``, never picked up implicitly by Django's
own auto-discovery (docs/CONTRACT.md §10's collision-audit table).

Seven functions, eight check IDs (docs/CONTRACT.md §6):

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
    appkit.W006 (Warning) — REST_FRAMEWORK["NUM_PROXIES"] disagrees with
                             APPKIT["TRUSTED_PROXY_COUNT"], or is unset while a
                             SimpleRateThrottle subclass is configured
                             -> check_num_proxies_throttle_agreement

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
        scopes, _throttle_classes = _collect_throttle_info()
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


def _collect_throttle_info() -> tuple[set[str], list[type]]:
    """Walk ``ROOT_URLCONF`` once and return every ``throttle_scope`` string AND every
    ``throttle_classes`` entry found on a reachable view.

    Shared by ``appkit.W004`` (``check_throttle_scopes``) and ``appkit.W006``
    (``check_num_proxies_throttle_agreement``) — one traversal of the URLconf serving both,
    rather than each check walking it separately. A view's ``throttle_classes`` is read as a
    resolved class list (DRF's ``APIView.throttle_classes`` is a class attribute, already
    Python objects by the time a view module is imported — never dotted strings needing
    ``import_string`` the way ``REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`` does), which is
    what lets this catch a view that sets ``throttle_classes`` itself with no global default
    configured at all — ``appkit.W006``'s per-view coverage gap the class-attribute default
    alone wouldn't close.

    Returns ``(set(), [])`` — never raises — if ``ROOT_URLCONF`` is unset, unimportable, or the
    walk otherwise fails; callers treat that identically to "nothing found".
    """
    from django.urls import URLResolver, get_resolver

    root_urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not root_urlconf:
        return set(), []

    resolver = get_resolver(root_urlconf)
    scopes: set[str] = set()
    throttle_classes: list[type] = []

    def _walk(patterns: Any) -> None:
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                _walk(pattern.url_patterns)
                continue
            callback = getattr(pattern, "callback", None)
            if callback is None:
                continue
            target = getattr(callback, "view_class", None) or getattr(callback, "cls", None)
            if target is None:
                continue
            scope = getattr(target, "throttle_scope", None)
            if isinstance(scope, str) and scope:
                scopes.add(scope)
            classes = getattr(target, "throttle_classes", None)
            if classes:
                throttle_classes.extend(cls for cls in classes if isinstance(cls, type))

    _walk(resolver.url_patterns)
    return scopes, throttle_classes


def check_num_proxies_throttle_agreement(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """appkit.W006 — two independent conditions about ``REST_FRAMEWORK["NUM_PROXIES"]``, both
    warned about because DRF's ``SimpleRateThrottle.get_ident()`` does its own
    ``X-Forwarded-For`` parsing that appkit has no way to inject
    :func:`appkit.net.client_ip`'s trusted-hop logic into.

    With ``NUM_PROXIES`` unset (DRF's own default, ``None``), ``get_ident()`` joins the
    **entire** ``X-Forwarded-For`` header into one string and uses that as the throttle bucket
    key — not the untrusted leftmost entry, not the trusted rightmost one, the whole chain. A
    client prepending fake hops gets a fresh bucket key on every request, making the throttle a
    no-op for exactly the client it exists to slow down.

    Two conditions, both reported at this ID, with distinct messages because the fixes differ:

    - **Unset** — ``NUM_PROXIES`` is ``None`` (whether omitted entirely or set to ``None``
      explicitly — both behave identically in DRF) while any ``SimpleRateThrottle`` subclass is
      configured, either globally via ``REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`` or on any
      view reachable via ``ROOT_URLCONF`` through its own ``throttle_classes``. Fix: set
      ``NUM_PROXIES`` to the same value as ``APPKIT["TRUSTED_PROXY_COUNT"]``.
    - **Disagreement** — ``NUM_PROXIES`` is set to a value that differs from
      ``APPKIT["TRUSTED_PROXY_COUNT"]``. Fires regardless of which throttle classes are
      configured: :func:`appkit.net.client_ip` and ``get_ident()`` would trust a different
      number of proxy hops and disagree about who the client is, even though both are
      individually "configured" rather than one being unset.

    Detection is defensive throughout, matching every check in this module:

    - A throttle class only counts if ``get_ident`` is the one it inherited from
      ``BaseThrottle``/``SimpleRateThrottle`` — a subclass overriding ``get_ident()`` does its
      own parsing, and warning about it would be a false positive this check cannot resolve
      without re-implementing that subclass's own logic.
    - Throttle classes are gathered two ways: the raw
      ``REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`` setting (dotted strings, resolved via
      ``import_string``), and each view's own ``throttle_classes`` attribute, walked via
      ``ROOT_URLCONF`` (:func:`_collect_throttle_info`, shared with ``appkit.W004``). A throttle
      wired up some other way — ``get_throttles()`` overridden at runtime, a permission class
      doing its own rate limiting — is invisible to this check; a clean run is not proof one
      doesn't exist somewhere, the same limit ``appkit.W004`` already documents.
    - ``rest_framework.throttling`` is imported **inside** this function, not at module scope:
      ``SimpleRateThrottle`` reads ``api_settings.DEFAULT_THROTTLE_RATES`` at class-definition
      time, which would raise if this module were ever imported before Django settings are
      configured.
    - Any unimportable class path, or a failed ``ROOT_URLCONF`` walk, contributes nothing from
      that source rather than raising — never lets this check crash ``manage.py``, see the
      module docstring.
    """
    drf_settings = getattr(settings, "REST_FRAMEWORK", None) or {}
    num_proxies = drf_settings.get("NUM_PROXIES")
    trusted_proxy_count = conf.get_setting("TRUSTED_PROXY_COUNT")

    if num_proxies is not None and num_proxies != trusted_proxy_count:
        return [
            Warning(
                f"REST_FRAMEWORK['NUM_PROXIES'] ({num_proxies!r}) disagrees with "
                f"APPKIT['TRUSTED_PROXY_COUNT'] ({trusted_proxy_count!r}).",
                hint=(
                    "appkit.net.client_ip() and DRF's SimpleRateThrottle.get_ident() will "
                    "trust a different number of X-Forwarded-For hops and disagree about who "
                    "the client is. Set REST_FRAMEWORK['NUM_PROXIES'] to the same value as "
                    "APPKIT['TRUSTED_PROXY_COUNT'] — docs/CONTRACT.md §6."
                ),
                id="appkit.W006",
            )
        ]

    if num_proxies is None and _has_unguarded_simple_rate_throttle():
        return [
            Warning(
                "REST_FRAMEWORK['NUM_PROXIES'] is unset while a rate-limiting throttle class "
                "is configured.",
                hint=(
                    "With NUM_PROXIES unset, DRF's SimpleRateThrottle.get_ident() joins the "
                    "entire X-Forwarded-For header into the throttle bucket key instead of "
                    "just the trusted rightmost hop — a client prepending fake hops gets a "
                    "fresh bucket on every request. Set REST_FRAMEWORK['NUM_PROXIES'] = "
                    "APPKIT['TRUSTED_PROXY_COUNT'] — docs/CONTRACT.md §6."
                ),
                id="appkit.W006",
            )
        ]

    return []


def _has_unguarded_simple_rate_throttle() -> bool:
    """True if any throttle class gathered by :func:`_configured_throttle_classes` is a
    ``SimpleRateThrottle`` subclass that has **not** overridden ``get_ident`` — i.e. one that
    would actually hit the ``NUM_PROXIES``-unset hazard ``appkit.W006`` warns about. Never
    raises; see :func:`check_num_proxies_throttle_agreement`.
    """
    try:
        from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
    except Exception:
        # DRF itself unimportable is a much bigger problem than this check can meaningfully
        # report — treat it as "nothing to warn about" rather than crash manage.py.
        logger.debug(
            "appkit.checks._has_unguarded_simple_rate_throttle: could not import DRF throttling",
            exc_info=True,
        )
        return False

    for cls in _configured_throttle_classes():
        if not issubclass(cls, SimpleRateThrottle):
            continue
        if cls.get_ident is not BaseThrottle.get_ident:
            # Overrides get_ident() itself — DRF's whole-header-join behaviour isn't in play.
            continue
        return True
    return False


def _configured_throttle_classes() -> set[type]:
    """Every throttle class reachable two ways: ``REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]``
    (dotted strings, resolved via ``import_string``) and each view's own ``throttle_classes``
    attribute, walked via ``ROOT_URLCONF`` (:func:`_collect_throttle_info`, shared with
    ``appkit.W004``). Never raises: an unimportable class path or a failed URLconf walk
    contributes nothing from that source rather than propagating.
    """
    classes: set[type] = set()

    drf_settings = getattr(settings, "REST_FRAMEWORK", None) or {}
    for path in drf_settings.get("DEFAULT_THROTTLE_CLASSES") or []:
        try:
            resolved = import_string(path) if isinstance(path, str) else path
        except Exception:
            logger.debug(
                "appkit.checks._configured_throttle_classes: could not import %r",
                path,
                exc_info=True,
            )
            continue
        if isinstance(resolved, type):
            classes.add(resolved)

    try:
        _scopes, view_throttle_classes = _collect_throttle_info()
    except Exception:
        # Never let this check crash manage.py — see module docstring.
        logger.debug(
            "appkit.checks._configured_throttle_classes: failed to walk ROOT_URLCONF",
            exc_info=True,
        )
        view_throttle_classes = []
    classes.update(view_throttle_classes)

    return classes


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
