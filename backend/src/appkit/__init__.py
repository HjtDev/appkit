"""appkit — the shared Django + DRF foundation every app package and host in this ecosystem
depends on.

Not an installable feature; it is what ``backend/tools/`` (cache, mixins, crypto) and
``config/logging.py``'s request-ID plumbing move into once this package exists
(``BASE-DESIGN.md`` §3). Every other app package declares appkit as a dependency and imports
its helpers instead of reimplementing them.

This module intentionally re-exports nothing. Each submodule below is its own public surface —
import from ``appkit.<module>`` directly (e.g. ``from appkit.cache import cached_call``), never
from ``appkit`` itself. ``appkit.conf`` is explicitly *not* re-exported here even internally
(docs/CONTRACT.md §2.16: "not re-exported from a top-level ``appkit`` namespace").

Public modules (docs/CONTRACT.md §2):
    ``appkit.cache``        — cache namespace versioning, key building, endpoint caching
    ``appkit.mixins``       — ``CachedListMixin``, a DRF list-view response caching mixin
    ``appkit.exceptions``   — the standard DRF exception handler and the ten error codes
    ``appkit.request_id``   — the request-ID ContextVar, ASGI middleware, and logging filter
    ``appkit.crypto``       — Fernet encryption taking its key at call time (``crypto`` extra)
    ``appkit.permissions``  — shared DRF permission classes
    ``appkit.pagination``   — the shared default pagination class
    ``appkit.validation``   — query-param validation, HTML sanitisation, an ORM lookup allowlist
    ``appkit.files``        — upload/image validation via magic-byte sniffing (``images`` extra)
    ``appkit.net``          — trust-boundary real client IP extraction
    ``appkit.media``        — media URL absolutisation (never ``appkit.urls`` — see below)
    ``appkit.text``         — truncation and digit normalisation shared with the frontend half
    ``appkit.dates``        — Gregorian <-> Jalali conversion using stdlib types only
    ``appkit.money``        — integer money parsing/formatting shared with the frontend half
    ``appkit.throttling``   — DRF throttle-scope string construction
    ``appkit.testing``      — the opt-in pytest plugin (``-p appkit.testing``)

Internal-but-stable (docs/CONTRACT.md §2.16):
    ``appkit.conf``         — the ``APPKIT`` settings-dict accessor and its ``DEFAULTS``

appkit ships no ``urlpatterns`` and is never ``include()``d anywhere, by any host — there is no
``appkit.urls``, deliberately (docs/CONTRACT.md §10). appkit ships no models, no migrations, no
admin, no ``services.py``, no ``signals.py``, and no Celery/``django.tasks`` integration
(docs/CONTRACT.md §0, §10).
"""
