"""`appkit.media` — media URL absolutisation (docs/CONTRACT.md §2.11)."""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory

from appkit.media import absolute_url, file_url

factory = RequestFactory()


class _StubFieldFile:
    """Duck-types Django's `FieldFile`: `.url` raises `ValueError` when no file is set,
    exactly like the real thing does for an empty field.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = url

    @property
    def url(self) -> str:
        if self._url is None:
            raise ValueError("The 'x' attribute has no file associated with it.")
        return self._url


# ---------------------------------------------------------------- absolute_url


def test_absolute_url_of_none_is_none() -> None:
    assert absolute_url(None) is None


def test_absolute_url_of_empty_string_is_none() -> None:
    assert absolute_url("") is None


def test_absolute_url_already_absolute_passes_through_unchanged() -> None:
    url = "https://cdn.example.com/x.png"
    assert absolute_url(url) == url


def test_absolute_url_already_absolute_is_not_double_prefixed_even_with_a_request() -> None:
    request = factory.get("/")
    url = "https://cdn.example.com/x.png"
    assert absolute_url(url, request=request) == url


def test_absolute_url_uses_build_absolute_uri_when_request_given(settings: object) -> None:
    settings.ALLOWED_HOSTS = ["api.example.com"]  # type: ignore[attr-defined]
    request = factory.get("/", SERVER_NAME="api.example.com")
    result = absolute_url("/media/x.png", request=request)
    assert result == "http://api.example.com/media/x.png"


def test_absolute_url_falls_back_to_site_url_setting_without_a_request(settings: object) -> None:
    settings.APPKIT = {**settings.APPKIT, "SITE_URL": "https://cdn.example.com"}  # type: ignore[attr-defined]
    assert absolute_url("/media/x.png") == "https://cdn.example.com/media/x.png"


def test_absolute_url_raises_improperly_configured_naming_site_url_when_unset(
    settings: object,
) -> None:
    settings.APPKIT = {**settings.APPKIT, "SITE_URL": ""}  # type: ignore[attr-defined]
    with pytest.raises(ImproperlyConfigured, match="SITE_URL"):
        absolute_url("/media/x.png")


def test_absolute_url_respects_secure_proxy_ssl_header(settings: object) -> None:
    """Behind `--proxy-headers` + `SECURE_PROXY_SSL_HEADER`, the resolved URL must be
    `https://` — an `http://` result here means every production media URL is mixed content.
    """
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # type: ignore[attr-defined]
    settings.ALLOWED_HOSTS = ["api.example.com"]  # type: ignore[attr-defined]
    request = factory.get("/", SERVER_NAME="api.example.com", HTTP_X_FORWARDED_PROTO="https")
    result = absolute_url("/media/x.png", request=request)
    assert result is not None
    assert result.startswith("https://")


# ---------------------------------------------------------------- file_url


def test_file_url_of_none_is_none() -> None:
    assert file_url(None) is None


def test_file_url_of_empty_string_is_none() -> None:
    assert file_url("") is None


def test_file_url_of_an_empty_field_file_is_none() -> None:
    """Django's own `FieldFile.url` raises `ValueError` on an empty field — absorbed here."""
    assert file_url(_StubFieldFile()) is None


def test_file_url_of_a_string_path_is_absolutized(settings: object) -> None:
    settings.ALLOWED_HOSTS = ["api.example.com"]  # type: ignore[attr-defined]
    request = factory.get("/", SERVER_NAME="api.example.com")
    assert file_url("/media/x.png", request=request) == "http://api.example.com/media/x.png"


def test_file_url_of_a_field_file_is_absolutized(settings: object) -> None:
    settings.ALLOWED_HOSTS = ["api.example.com"]  # type: ignore[attr-defined]
    request = factory.get("/", SERVER_NAME="api.example.com")
    field_file = _StubFieldFile("/media/y.png")
    assert file_url(field_file, request=request) == "http://api.example.com/media/y.png"
