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
