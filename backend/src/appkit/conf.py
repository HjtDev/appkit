"""Settings access layer for appkit's ``APPKIT`` settings dict.

Internal-but-stable (docs/CONTRACT.md §2.16): not re-exported from a top-level ``appkit``
namespace, but every module below reads its configuration through :func:`get_setting`, so its
shape is held to the same "don't break it silently" standard as a public module even though it
sits one layer down. Follows ``APP-DESIGN.md`` §3.5's ``conf.py`` pattern exactly.

Four settings keys, all optional at the Python level (docs/CONTRACT.md §7):

    APPKIT = {
        "CACHE_TIMEOUT": 60,                    # appkit.cache / appkit.mixins default
        "TRUSTED_PROXY_COUNT": 1,               # appkit.net's trusted X-Forwarded-For hops
        "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,   # appkit.files' semantic size cap
        "SITE_URL": "",                         # optional-but-conditionally-required —
                                                 # appkit.media raises ImproperlyConfigured
                                                 # naming this setting the first time
                                                 # file_url/absolute_url is called with
                                                 # request=None and this is still unset.
    }

Zero ``.env`` keys, required or optional, under any installed extra (docs/CONTRACT.md §7) —
every credential/secret appkit's surface ever touches is an app's own documented ``.env`` key,
never appkit's.
"""

from __future__ import annotations

from typing import Any, Final

from django.conf import settings

#: Sentinel distinguishing "no explicit value passed" from "pass None explicitly", used by
#: ``appkit.cache``, ``appkit.mixins``, and ``appkit.files`` to mean "fall back to the
#: documented ``APPKIT`` default" (docs/CONTRACT.md §2.1, §2.2, §2.9). Defined here because
#: falling back to a settings default is exactly conf.py's job, and defining it in any of the
#: three consuming modules would create an import cycle between them.
UNSET: Final = object()

DEFAULTS: Final[dict[str, Any]] = {
    "CACHE_TIMEOUT": 60,
    "TRUSTED_PROXY_COUNT": 1,
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,
    "SITE_URL": "",
}


def get_setting(key: str) -> Any:
    """Read an ``APPKIT`` setting, falling back to appkit's documented default.

    Reads ``settings.APPKIT.get(key, DEFAULTS[key])`` — a host omitting a key gets the
    documented default rather than a ``KeyError``/``AttributeError`` deep inside a view.

    Raises:
        KeyError: only for a ``key`` that isn't in :data:`DEFAULTS` at all — a programming
            error inside appkit itself, never a host-facing failure mode.
    """
    configured: dict[str, Any] = getattr(settings, "APPKIT", {})
    return configured.get(key, DEFAULTS[key])
