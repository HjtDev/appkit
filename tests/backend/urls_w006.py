"""Scratch URLconf for `appkit.checks.check_num_proxies_throttle_agreement` (`appkit.W006`)
tests only.

Mounted exclusively via ``override_settings(ROOT_URLCONF="tests.backend.urls_w006")`` inside
test_checks.py — never the default test-tree URLconf. A view configuring a throttle class
mounted permanently would make appkit's own ``manage.py check`` emit `appkit.W006` forever
(the default test settings deliberately leave `REST_FRAMEWORK["NUM_PROXIES"]` unset), training
everyone to ignore a warning that exists to be actionable — the same trap `urls_throttling.py`
avoids for `appkit.W004`.

`_PerViewOnlyView` exists specifically to prove the per-view coverage `_collect_throttle_info`
provides: it sets `throttle_classes` directly, with no `REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`
configured anywhere, which the raw-settings half of `_configured_throttle_classes` alone would
never see.
"""

from __future__ import annotations

from typing import ClassVar

from django.http import HttpResponse
from django.urls import path
from rest_framework.throttling import AnonRateThrottle, BaseThrottle
from rest_framework.views import APIView


class _PerViewOnlyView(APIView):
    """No global DEFAULT_THROTTLE_CLASSES anywhere — only this view's own attribute."""

    throttle_classes: ClassVar[list[type[BaseThrottle]]] = [AnonRateThrottle]

    def get(self, request: object) -> HttpResponse:
        return HttpResponse("ok")


class _UnthrottledView(APIView):
    """No throttle_classes override — must never contribute a spoofable class on its own."""

    def get(self, request: object) -> HttpResponse:
        return HttpResponse("ok")


urlpatterns = [
    path("per-view-only/", _PerViewOnlyView.as_view()),
    path("unthrottled/", _UnthrottledView.as_view()),
]
