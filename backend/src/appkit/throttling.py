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

__all__ = ["throttle_scope"]


def throttle_scope(app_namespace: str, action: str) -> str:
    """`throttle_scope("notifications", "list")` -> `"notifications_list"`.

    Enforces naming at the point of declaration — the opt-in half of the prefix convention.
    **Not** the same guarantee as `appkit.W004` (`appkit.checks.check_throttle_scopes`), which
    checks the complementary, orthogonal property: that a declared `throttle_scope`, in whatever
    format, has a matching `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` entry. Neither check
    substitutes for the other.

    Raises:
        ValueError: if either argument is empty, or contains an underscore itself — which
            would make the resulting scope ambiguous to split back apart, and more practically,
            usually signals a caller passing an already-prefixed value by mistake.
    """
    if not app_namespace or not action:
        raise ValueError("throttle_scope() requires non-empty app_namespace and action.")
    if "_" in app_namespace or "_" in action:
        raise ValueError(
            "throttle_scope() arguments must not contain an underscore — "
            f"got app_namespace={app_namespace!r}, action={action!r}."
        )
    return f"{app_namespace}_{action}"
