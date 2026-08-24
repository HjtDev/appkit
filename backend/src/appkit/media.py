"""File-location/URL formatting — absolutizing media URLs.

Kept as a separate module from ``appkit.net`` despite both starting life as "URL-ish"
(docs/CONTRACT.md §2 preamble). This is where the media-URL helper lives precisely *because*
appkit ships no ``urlpatterns`` — see docs/CONTRACT.md §10; there is no ``appkit.urls``.

Public surface (docs/CONTRACT.md §2.11):

    def file_url(
        value: FieldFile | str | None, *, request: HttpRequest | Request | None = None
    ) -> str | None: ...

    def absolute_url(
        url: str | None, *, request: HttpRequest | Request | None = None
    ) -> str | None: ...

Both raise ImproperlyConfigured only when ``request is None`` AND ``APPKIT['SITE_URL']`` is
unset — a host that never renders a media URL outside an active request cycle never needs
SITE_URL at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from appkit.conf import get_setting

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile
    from django.http import HttpRequest
    from rest_framework.request import Request

__all__ = ["absolute_url", "file_url"]


def _is_absolute(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def file_url(
    value: FieldFile | str | None, *, request: HttpRequest | Request | None = None
) -> str | None:
    """Absolutizes a `FieldFile`/URL string, or `None` for an unset value.

    `None` and an empty `FieldFile` (Django's own `FieldFile.url` raises `ValueError` on an
    empty field — absorbed here) both return `None`, so a serializer calling this on every
    optional `ImageField`/`FileField` doesn't need to guard the field itself. Never raises on
    that path; see `absolute_url` for the one path that does.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if not value:
            return None
        return absolute_url(value, request=request)

    try:
        url = value.url
    except ValueError:
        return None
    return absolute_url(url, request=request)


def absolute_url(url: str | None, *, request: HttpRequest | Request | None = None) -> str | None:
    """Absolutizes `url` against `request` (or `APPKIT["SITE_URL"]` when there is none).

    `None`/`""` return `None`. An already-absolute URL (a non-empty `scheme` and `netloc`,
    e.g. an S3/CDN-backed `FieldFile`, or an off-host `MEDIA_URL`) passes through unchanged —
    never double-prefixed.

    With `request`, uses `request.build_absolute_uri(...)`, which already respects Django's
    `SECURE_PROXY_SSL_HEADER` handling — correct in dev, staging, and prod (behind
    `--proxy-headers`) with zero extra configuration. Without `request` (a Celery task, a
    management command, an email template), falls back to `APPKIT["SITE_URL"]`.

    Raises:
        ImproperlyConfigured: only when `request is None` **and** `APPKIT["SITE_URL"]` is
            unset (the default, `""`) — naming `APPKIT["SITE_URL"]` as the fix. Silently
            returning a relative URL in that case is exactly how a broken image link ends up in
            a Celery-rendered email nobody notices until a customer complains.
    """
    if not url:
        return None
    if _is_absolute(url):
        return url

    if request is not None:
        return request.build_absolute_uri(url)

    site_url = get_setting("SITE_URL")
    if not site_url:
        raise ImproperlyConfigured(
            "appkit.media needs APPKIT['SITE_URL'] set to absolutize a URL with no request in "
            "scope (e.g. from a Celery task or management command). Add APPKIT['SITE_URL'] to "
            "your settings, or call this with a request when one is available."
        )
    path = url if url.startswith("/") else f"/{url}"
    return f"{site_url.rstrip('/')}{path}"
