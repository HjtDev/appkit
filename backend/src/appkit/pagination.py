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
