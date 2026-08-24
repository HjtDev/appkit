"""File-location/URL formatting — absolutizing media URLs.

Kept as a separate module from appkit.net despite both starting life as "URL-ish"
(docs/CONTRACT.md §2 preamble). This is where the media-URL helper lives precisely *because*
appkit ships no ``urlpatterns`` — see docs/CONTRACT.md §10; there is no ``appkit.urls``.

Public surface (docs/CONTRACT.md §2.11), implemented in a later phase:

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
