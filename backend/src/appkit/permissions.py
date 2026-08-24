"""Shared DRF permission classes.

Public surface (docs/CONTRACT.md §2.6), implemented in a later phase:

    class IsAppAdmin(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool: ...

    class IsObjectOwner(BasePermission):
        owner_field: str = "user"

        def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool: ...
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

__all__ = ["IsAppAdmin", "IsObjectOwner"]


class IsAppAdmin(BasePermission):
    """Gates the custom admin-dashboard API surface (`APP-DESIGN.md` §5's second admin
    surface). Relies only on what Django's user model already guarantees everywhere — never on
    another app's model. Never raises.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsObjectOwner(BasePermission):
    """Denies access to another user's object — the IDOR case `APP-DESIGN.md` §7.4 and §9's
    security checklist name explicitly.
    """

    owner_field: str = "user"

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        # A misconfigured `owner_field` must deny access, never raise `AttributeError`
        # mid-permission-check — failing closed with a wrong-looking answer is safer than
        # failing open by accident.
        return getattr(obj, self.owner_field, None) == request.user
