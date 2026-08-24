"""DRF list-view response caching mixin.

Public surface (docs/CONTRACT.md §2.2), implemented in a later phase:

    class CachedListMixin:
        cache_namespace: str    # REQUIRED — no default. Raises ImproperlyConfigured at first
                                 # list() call if empty.
        cache_timeout: int = UNSET   # appkit.conf.UNSET — falls back to APPKIT['CACHE_TIMEOUT']

        def list(self, request, *args, **kwargs) -> Response: ...
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from rest_framework.response import Response

from appkit.cache import _user_cache_token, build_cache_key, cached_call
from appkit.conf import UNSET, _Unset

__all__ = ["CachedListMixin"]


class CachedListMixin:
    """Caches a `ListAPIView`'s serialized data per user and querystring.

    Set `cache_namespace` (required — no default) and optionally `cache_timeout` (seconds,
    falls back to `APPKIT["CACHE_TIMEOUT"]` when left `UNSET`) on the view. Caches
    `response.data`, not the `Response` object itself: a DRF `Response` carries
    renderer/request state that isn't meant to be pickled into a cache backend, where a plain
    list of serialized dicts is.

    **`cache_namespace` has no class-name-derived fallback**, unlike the scaffold this is
    ported from — two apps each shipping a `NotificationListView` would collide in the host's
    one shared Redis instance, precisely the collision `APP-DESIGN.md` §1.3 exists to prevent.
    Raises `ImproperlyConfigured` at first `list()` call if left empty.

    Usage: `class MyListView(CachedListMixin, generics.ListAPIView): ...` — the mixin must
    precede the generic view in the MRO so it wraps `list()`.
    """

    cache_namespace: str = ""  # REQUIRED — no default; empty raises at first list() call
    cache_timeout: int | _Unset = UNSET

    def _cache_key(self, request: Any) -> str:
        if not self.cache_namespace:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.cache_namespace is required and must be non-empty — "
                "an unprefixed cache key is exactly the two-apps-collide scenario "
                "APP-DESIGN.md §1.3 exists to prevent."
            )
        return build_cache_key(
            self.cache_namespace,
            _user_cache_token(request, per_user=True),
            request.get_full_path(),
        )

    def list(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        def build() -> Any:
            # This mixin is only ever combined with generics.ListAPIView (see the class
            # docstring), which is where `list()` actually comes from — mypy can't see that
            # from this class's own bases, since a plain mixin has none.
            return super(CachedListMixin, self).list(request, *args, **kwargs).data  # type: ignore[misc]

        data = cached_call(self._cache_key(request), self.cache_timeout, build)
        return Response(data)
