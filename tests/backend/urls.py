"""Test-tree URLconf.

appkit ships no urlpatterns of its own (docs/CONTRACT.md §10) — there is nothing to include()
here on appkit's behalf, unlike a consuming app's tests/backend/urls.py (APP-DESIGN.md §7.1),
which mounts its own urls.py/urls_admin.py.

Still required: Django needs a ROOT_URLCONF to boot, and appkit.checks.check_throttle_scopes
(appkit.W004) walks it looking for throttle_scope-declared views. The single ``ping`` view below
exists only so the ASGI integration test (tests/backend/test_asgi_integration.py) has a live,
DB-free endpoint to drive through the real async middleware chain — it is not otherwise part of
appkit's public surface.

Throttle-scope test scratch views live in ``tests/backend/urls_throttling.py`` instead of here,
deliberately: a permanently-mounted view with a missing throttle rate would make appkit's own
``manage.py check`` emit appkit.W004 forever, training everyone to ignore it.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path


async def ping(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


urlpatterns = [
    path("ping/", ping),
]
