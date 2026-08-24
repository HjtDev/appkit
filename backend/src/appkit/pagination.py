"""The shared default pagination class.

Public surface (docs/CONTRACT.md §2.7), implemented in a later phase:

    class DefaultPagination(PageNumberPagination):
        page_size = 25
        page_size_query_param = "page_size"
        max_page_size = 100

A host wiring appkit needs no REST_FRAMEWORK["PAGE_SIZE"] — DefaultPagination carries its own
page_size (docs/CONTRACT.md §8).
"""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination

__all__ = ["DefaultPagination"]


class DefaultPagination(PageNumberPagination):
    """Shared default so every app avoids re-declaring the same three numbers. A view that can
    return unbounded data sets this (or its own) `pagination_class` explicitly per
    `APP-DESIGN.md` §4, rather than relying on a host's `DEFAULT_PAGINATION_CLASS`, which the
    app can't know.
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100  # caps ?page_size= so a client can't defeat pagination entirely
