"""Scratch URLconf for appkit.checks.check_throttle_scopes (appkit.W004) tests only.

Mounted exclusively via ``override_settings(ROOT_URLCONF="tests.backend.urls_throttling")``
inside test_checks.py — never the default test-tree URLconf. A view with a missing throttle
rate mounted permanently would make appkit's own ``manage.py check`` emit appkit.W004 forever,
training everyone to ignore a warning that exists to be actionable.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import path
from rest_framework.views import APIView


class _ScopedView(APIView):
    """Declares a throttle_scope with (deliberately) no matching DEFAULT_THROTTLE_RATES entry."""

    throttle_scope = "missing-scope"

    def get(self, request: object) -> HttpResponse:
        return HttpResponse("ok")


class _KnownScopeView(APIView):
    """Declares a throttle_scope that IS covered by the test settings' DEFAULT_THROTTLE_RATES."""

    throttle_scope = "known-scope"

    def get(self, request: object) -> HttpResponse:
        return HttpResponse("ok")


class _UnscopedView(APIView):
    """No throttle_scope at all — must never appear in check_throttle_scopes's findings."""

    def get(self, request: object) -> HttpResponse:
        return HttpResponse("ok")


urlpatterns = [
    path("scoped/", _ScopedView.as_view()),
    path("known-scope/", _KnownScopeView.as_view()),
    path("unscoped/", _UnscopedView.as_view()),
]
