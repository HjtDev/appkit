"""DRF list-view response caching mixin.

Public surface (docs/CONTRACT.md §2.2), implemented in a later phase:

    class CachedListMixin:
        cache_namespace: str    # REQUIRED — no default. Raises ImproperlyConfigured at first
                                 # list() call if empty.
        cache_timeout: int = UNSET   # appkit.conf.UNSET — falls back to APPKIT['CACHE_TIMEOUT']

        def list(self, request, *args, **kwargs) -> Response: ...
"""

from __future__ import annotations
