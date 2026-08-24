"""Wraps urls_throttling.py behind one level of `include()`, so
appkit.checks.check_throttle_scopes's recursion into a nested `URLResolver` is exercised, not
just its flat-pattern path. Scratch-only, mounted the same way as urls_throttling.py.
"""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("nested/", include("tests.backend.urls_throttling")),
]
