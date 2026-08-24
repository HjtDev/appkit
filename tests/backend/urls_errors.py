"""Scratch URLconf for `appkit.exceptions` integration tests only — the two cases that need a
real DRF request/response cycle to prove a header survives: `Retry-After` on a throttled
response and `WWW-Authenticate` on a 401 are both set by `APIView.handle_exception` *before*
our own handler ever runs, so a direct unit call against `standard_exception_handler` proves
nothing about them.

Mounted exclusively via ``override_settings(ROOT_URLCONF="tests.backend.urls_errors")``, same
pattern as ``urls_throttling.py`` — never the default test-tree URLconf.
"""

from __future__ import annotations

from django.urls import path
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView


class _FixedRateThrottle(AnonRateThrottle):
    """A hardcoded 1/min rate, so the test doesn't need to touch DEFAULT_THROTTLE_RATES.
    `AnonRateThrottle` (not the abstract `SimpleRateThrottle`) supplies `get_cache_key`.
    """

    scope = "errors_test"

    def get_rate(self) -> str:
        return "1/min"


class _ThrottledView(APIView):
    """First GET succeeds; the second (same client/IP) is throttled and gets Retry-After."""

    throttle_classes = [_FixedRateThrottle]

    def get(self, request: object) -> Response:
        return Response({"ok": True})


class _UnauthenticatedView(APIView):
    """BasicAuthentication supplies a real `authenticate_header`, so an unauthenticated
    request raises NotAuthenticated with WWW-Authenticate set, rather than being silently
    flipped to a plain 403 by APIView.handle_exception.
    """

    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: object) -> Response:
        return Response({"ok": True})


urlpatterns = [
    path("throttled/", _ThrottledView.as_view()),
    path("unauthenticated/", _UnauthenticatedView.as_view()),
]
