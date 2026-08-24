"""`appkit.net` — trust-boundary `X-Forwarded-For` parsing (docs/CONTRACT.md §2.10)."""

from __future__ import annotations

import pytest
from rest_framework.test import APIRequestFactory

from appkit.net import client_ip

factory = APIRequestFactory()


def _request(*, xff: str | None = None, remote_addr: str = "10.0.0.1") -> object:
    extra = {"REMOTE_ADDR": remote_addr}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return factory.get("/", **extra)


def test_trusts_the_rightmost_entry_by_default(settings: object) -> None:
    settings.APPKIT = {**settings.APPKIT, "TRUSTED_PROXY_COUNT": 1}  # type: ignore[attr-defined]
    request = _request(xff="203.0.113.7")
    assert client_ip(request) == "203.0.113.7"


def test_ignores_client_prepended_fake_hops_and_counts_from_the_right(settings: object) -> None:
    """Mandatory test: a client pre-pending fake hops must not move the answer — proving the
    logic counts from the right, not from the left with extra steps.
    """
    settings.APPKIT = {**settings.APPKIT, "TRUSTED_PROXY_COUNT": 1}  # type: ignore[attr-defined]
    request = _request(xff="1.2.3.4, 9.9.9.9, 203.0.113.7")
    assert client_ip(request) == "203.0.113.7"


def test_trusted_proxy_count_two_resolves_second_from_right(settings: object) -> None:
    settings.APPKIT = {**settings.APPKIT, "TRUSTED_PROXY_COUNT": 2}  # type: ignore[attr-defined]
    request = _request(xff="1.2.3.4, 9.9.9.9, 203.0.113.7")
    assert client_ip(request) == "9.9.9.9"


def test_ipv6_candidate_is_accepted() -> None:
    request = _request(xff="2001:db8::1")
    assert client_ip(request) == "2001:db8::1"


def test_ipv6_bracketed_with_port_is_stripped() -> None:
    request = _request(xff="[2001:db8::1]:8443")
    assert client_ip(request) == "2001:db8::1"


def test_ipv4_host_port_form_is_stripped() -> None:
    request = _request(xff="203.0.113.7:8080")
    assert client_ip(request) == "203.0.113.7"


def test_malformed_candidate_falls_back_to_remote_addr() -> None:
    request = _request(xff="not-an-ip", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_absent_header_falls_back_to_remote_addr() -> None:
    request = _request(xff=None, remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_empty_header_falls_back_to_remote_addr() -> None:
    request = _request(xff="", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_fewer_entries_than_trusted_proxy_count_falls_back(settings: object) -> None:
    settings.APPKIT = {**settings.APPKIT, "TRUSTED_PROXY_COUNT": 3}  # type: ignore[attr-defined]
    request = _request(xff="1.2.3.4, 9.9.9.9", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


@pytest.mark.parametrize("count", [0, -1])
def test_non_positive_trusted_proxy_count_falls_back_rather_than_returning_the_leftmost_entry(
    settings: object, count: int
) -> None:
    """A misconfigured `TRUSTED_PROXY_COUNT<=0` must never resolve to `parts[-0] == parts[0]` —
    the client-controlled leftmost entry.
    """
    settings.APPKIT = {**settings.APPKIT, "TRUSTED_PROXY_COUNT": count}  # type: ignore[attr-defined]
    request = _request(xff="1.2.3.4, 9.9.9.9, 203.0.113.7", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_empty_candidate_after_a_trailing_comma_falls_back() -> None:
    """`X-Forwarded-For: 1.2.3.4,` — an empty trailing entry after stripping whitespace."""
    request = _request(xff="1.2.3.4,", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_unclosed_ipv6_bracket_falls_back() -> None:
    request = _request(xff="[2001:db8::1", remote_addr="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_drf_request_wrapper_is_supported() -> None:
    """`client_ip` must accept both a plain Django `HttpRequest` and a DRF `Request`."""
    from rest_framework.request import Request

    django_request = _request(xff="203.0.113.7")
    assert client_ip(Request(django_request)) == "203.0.113.7"
