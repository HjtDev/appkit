"""`appkit.pagination` — the shared default pagination class (docs/CONTRACT.md §2.7)."""

from __future__ import annotations

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from appkit.exceptions import standard_exception_handler
from appkit.pagination import DefaultPagination

factory = APIRequestFactory()


def _drf_request(query_string: str = "") -> Request:
    path = f"/items/?{query_string}" if query_string else "/items/"
    return Request(factory.get(path))


def test_default_page_size_is_twenty_five() -> None:
    page = DefaultPagination().paginate_queryset(list(range(100)), _drf_request())
    assert page is not None
    assert len(page) == 25


def test_explicit_page_size_override_is_honoured() -> None:
    page = DefaultPagination().paginate_queryset(list(range(100)), _drf_request("page_size=10"))
    assert page is not None
    assert len(page) == 10


def test_page_size_is_capped_at_max_page_size() -> None:
    page = DefaultPagination().paginate_queryset(list(range(300)), _drf_request("page_size=1000"))
    assert page is not None
    assert len(page) == 100  # max_page_size, not the requested 1000


def test_out_of_range_page_produces_a_not_found_envelope_through_the_handler() -> None:
    request = _drf_request("page=99")
    with pytest.raises(NotFound) as exc_info:
        DefaultPagination().paginate_queryset(list(range(10)), request)

    response = standard_exception_handler(exc_info.value, {})
    assert response is not None
    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
