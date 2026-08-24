"""Mechanical construction of DRF throttle-scope strings from the app-namespace prefix
convention.

Enforces APP-DESIGN.md §1.3's namespacing rule for throttle scopes — every one is prefixed with
the app's own name, no exceptions, so two apps don't silently collide in one shared
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] dict.

Public surface (docs/CONTRACT.md §2.15), implemented in a later phase:

    def throttle_scope(app_namespace: str, action: str) -> str: ...
        # e.g. throttle_scope("notifications", "list") -> "notifications_list"
        # Raises ValueError if either argument is empty or contains an underscore itself.
"""

from __future__ import annotations
