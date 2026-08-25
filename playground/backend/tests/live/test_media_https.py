"""appkit.media.absolute_url behind TLS-terminating nginx — must yield https:// through the
:8443 listener and http:// through :8080, WITH the correct port, or every media URL in a real
deployment on non-standard ports is broken or mixed content.
"""

from __future__ import annotations

import httpx


def test_absolute_url_is_http_on_plain_listener(http_client: httpx.Client) -> None:
    body = http_client.get("/api/v1/demo/echo/").json()
    assert body["media_url"].startswith("http://")
    assert not body["is_secure"]


def test_absolute_url_is_https_on_tls_listener(https_client: httpx.Client) -> None:
    body = https_client.get("/api/v1/demo/echo/").json()
    assert body["media_url"].startswith("https://")
    assert body["is_secure"]
