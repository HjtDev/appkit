"""Shared DRF permission classes.

Public surface (docs/CONTRACT.md §2.6), implemented in a later phase:

    class IsAppAdmin(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool: ...

    class IsObjectOwner(BasePermission):
        owner_field: str = "user"

        def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool: ...
"""

from __future__ import annotations
