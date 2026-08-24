"""Test-tree URLconf.

appkit ships no urlpatterns of its own (docs/CONTRACT.md §10) — there is nothing to include()
here on appkit's behalf, unlike a consuming app's tests/backend/urls.py (APP-DESIGN.md §7.1),
which mounts its own urls.py/urls_admin.py.

Still required: Django needs a ROOT_URLCONF to boot, and appkit.checks.check_throttle_scopes
(appkit.W004) walks it looking for throttle_scope-declared views — so later phases' throttling
tests mount a scratch view here.
"""

from __future__ import annotations

urlpatterns: list = []
