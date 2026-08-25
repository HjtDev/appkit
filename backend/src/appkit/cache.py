"""Cache namespace versioning, key building, get-or-set, and endpoint-level response caching.

Public surface (docs/CONTRACT.md §2.1), implemented in a later phase:

    namespace_version(namespace: str) -> int
        Opaque version number for a cache namespace. Seeds from ``int(time.time())``, not the
        literal ``1`` — the return value must be treated as opaque, never assumed to start at 1.

    invalidate_namespace(namespace: str) -> int
        Bumps a namespace's version, effectively invalidating every key built against it.

    build_cache_key(namespace: str, *parts: object) -> str
        Builds a cache key incorporating the namespace's current version.

    cached_call(key: str, timeout: int | None, producer: Callable[[], T]) -> T
        Get-or-set around an arbitrary producer callable. ``timeout`` accepts appkit.conf.UNSET
        to mean "use APPKIT['CACHE_TIMEOUT']" — resolved to avoid the ambiguity of a bare
        ``None`` meaning either "no timeout" or "use the default".

    cache_endpoint(*, namespace: str, timeout: int | None = UNSET, per_user: bool = True,
                   vary_headers: Sequence[str] = (), cache_statuses: Container[int] = (200,))
        Decorator for endpoint-level response caching. Raises ImproperlyConfigured at
        decoration time (import time) if ``namespace`` is empty. ``per_user`` exists
        specifically to prevent cross-user cache leakage.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Container, Sequence
from functools import wraps
from typing import Any, cast

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from rest_framework.request import Request
from rest_framework.response import Response

from appkit.conf import UNSET, _Unset, get_setting

__all__ = [
    "build_cache_key",
    "cache_endpoint",
    "cached_call",
    "invalidate_namespace",
    "namespace_version",
]

# Keeps generated keys short and free of characters the cache backend (or a log line) might
# treat specially, once a part gets long or contains something other than
# alphanumerics/dashes/underscores/periods.
#
# **Deviation from the scaffold's `_SAFE_PART`:** the scaffold's version includes `:` as a
# "safe" character for an individual *part*, which would defeat the segment-smuggling
# protection below — a part containing `:` (the join delimiter used one line down) would be
# embedded raw instead of hashed, letting it forge extra `namespace:version:...` segments.
# Excluding `:` here is what actually satisfies "a delimiter must never smuggle a second
# segment into the key". docs/CONTRACT.md §2.1's own notation (`[A-Za-z0-9\-_.]`) already
# excludes it too and states this exclusion explicitly — the two agree.
_MAX_RAW_PART_LEN = 40
_SAFE_PART = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _version_key(namespace: str) -> str:
    return f"{namespace}:version"


def namespace_version(namespace: str) -> int:
    """Returns the current version for `namespace`, seeding it on first use.

    **Changed from the scaffold:** seeds from `int(time.time())`, not the literal `1`
    (docs/CONTRACT.md §2.1). The scaffold's get-then-increment isn't atomic against Django's
    cache API; if the version key is evicted under memory pressure and reseeds at `1`, every key
    built against a *higher* version before the eviction becomes reachable again — silently
    resurrecting data an earlier `invalidate_namespace` call explicitly invalidated. Seeding from
    a wall-clock second makes any reseed monotonically ahead of every version that could
    plausibly have been issued before it. The return value is therefore **opaque** — never
    assume it starts at `1`. Never raises.
    """
    version = cache.get(_version_key(namespace))
    if version is None:
        # `add`, not `set`: two processes racing to seed the same namespace must not let the
        # second clobber the first's (very slightly later, but already-issued) timestamp.
        cache.add(_version_key(namespace), int(time.time()), timeout=None)
        version = cache.get(_version_key(namespace))
    return int(version)


def invalidate_namespace(namespace: str) -> int:
    """Bumps `namespace`'s version, invalidating every key previously built against it.

    Returns the new version — guaranteed strictly greater than what came before it in this
    process's view. Never raises (calls `namespace_version` first to guarantee the key exists
    before `cache.incr`).
    """
    namespace_version(namespace)  # ensure it exists before incrementing
    return cache.incr(_version_key(namespace))


def _normalize_part(part: object) -> str:
    raw = str(part)
    if len(raw) > _MAX_RAW_PART_LEN or not set(raw) <= _SAFE_PART:
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    return raw


def build_cache_key(namespace: str, *parts: object) -> str:
    """Builds a stable, namespace-versioned cache key.

    `namespace:version:part1:part2:...` — long or unsafe parts are hashed rather than embedded
    raw, so an arbitrary string (a user-supplied search query, say) can't blow up key length or
    smuggle a delimiter into the key. Never raises.
    """
    version = namespace_version(namespace)
    segments = [namespace, str(version), *(_normalize_part(p) for p in parts)]
    return ":".join(segments)


def cached_call[T](
    key: str,
    timeout: int | _Unset | None,
    producer: Callable[[], T],
) -> T:
    """Get-or-set: returns the cached value at `key`, computing and storing it via
    `producer()` on a miss. `producer` is called at most once per miss.

    `timeout=None` means "cache forever" (Django's own cache semantics) and therefore cannot
    double as "use the configured default" — pass `appkit.conf.UNSET` for that instead,
    resolved here to `APPKIT["CACHE_TIMEOUT"]` (docs/CONTRACT.md §2.1). `UNSET` is not part of
    this function's *documented* public type (`int | None`) — it renders in docs as "omit the
    argument" — but is accepted and typed here so `appkit.mixins`/`cache_endpoint` passing it
    through still type-checks.

    A `producer` that returns `None` is never actually cached — Django's cache API can't
    distinguish "miss" from "cached `None`" through `.get()`'s default. Fine for the typical use
    (caching a queryset result, a serialized dict), but don't reach for this to cache a value
    that's legitimately `None`. Never raises on its own; propagates whatever `producer` raises.
    """
    resolved_timeout = get_setting("CACHE_TIMEOUT") if timeout is UNSET else timeout
    value = cache.get(key)
    if value is None:
        value = producer()
        cache.set(key, value, timeout=resolved_timeout)
    return cast("T", value)


def _user_cache_token(request: Request, *, per_user: bool) -> str:
    """`per_user=False` shares one cache entry across every caller — valid only where the
    response is byte-identical for everyone, including anonymous. `per_user=True` isolates by
    the user's `pk`, falling back to a fixed `"anon"` bucket rather than folding an anonymous
    caller into whatever the *first* unauthenticated request happened to produce a falsy-looking
    identity for — an explicit `is None` check, not `pk or "anon"`, so a real user whose `pk`
    happens to be `0` is never treated as anonymous.
    """
    if not per_user:
        return "shared"
    pk = getattr(request.user, "pk", None)
    return str(pk) if pk is not None else "anon"


def cache_endpoint[F: Callable[..., Response]](
    *,
    namespace: str,
    timeout: int | _Unset | None = UNSET,
    per_user: bool = True,
    vary_headers: Sequence[str] = (),
    cache_statuses: Container[int] = (200,),
) -> Callable[[F], F]:
    """Decorator wrapping a DRF view method (`list`/`retrieve`/...) with response caching, the
    way `appkit.mixins.CachedListMixin` wraps `ListAPIView.list` — for views that aren't plain
    list views.

    `namespace` is **required, no default** — an unprefixed key is exactly the
    two-apps-collide scenario `APP-DESIGN.md` §1.3 exists to prevent, so there is no safe
    default to fall back to. Raises `ImproperlyConfigured` at decoration time (import time) if
    `namespace` is empty.

    `per_user=True` is the load-bearing default. **Non-obvious failure path:** with
    `per_user=False` on a permission-gated view, user A's response is served verbatim to user
    B — an authorization bypass via the cache layer, not a cache bug. `per_user=False` is valid
    *only* where the response is byte-identical for every caller including anonymous users.

    `vary_headers` folds additional request headers into the cache key (e.g. `Accept-Language`
    for a bilingual endpoint) beyond user + full path. `cache_statuses` restricts caching to
    responses whose status is in this set — a 403/404 is never cached by default, since caching
    an authorization failure can make it outlive the state that caused it. Caches
    `{"data": ..., "status": ...}`, never the `Response` object itself.
    """
    if not namespace:
        raise ImproperlyConfigured(
            "cache_endpoint() requires a non-empty `namespace` — an unprefixed cache key is "
            "exactly the two-apps-collide scenario APP-DESIGN.md §1.3 exists to prevent."
        )

    def decorator(view_method: F) -> F:
        @wraps(view_method)
        def wrapper(self: Any, request: Request, *args: Any, **kwargs: Any) -> Response:
            key_parts: list[object] = [
                _user_cache_token(request, per_user=per_user),
                request.get_full_path(),
                *(request.headers.get(header, "") for header in vary_headers),
            ]
            key = build_cache_key(namespace, *key_parts)

            cached = cache.get(key)
            if cached is not None:
                return Response(cached["data"], status=cached["status"])

            response = view_method(self, request, *args, **kwargs)
            if response.status_code in cache_statuses:
                resolved_timeout = get_setting("CACHE_TIMEOUT") if timeout is UNSET else timeout
                cache.set(
                    key,
                    {"data": response.data, "status": response.status_code},
                    timeout=resolved_timeout,
                )
            return response

        return cast("F", wrapper)

    return decorator
