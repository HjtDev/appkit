"""`appkit.permissions` — IsAppAdmin and IsObjectOwner (docs/CONTRACT.md §2.6)."""

from __future__ import annotations

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User

from appkit.permissions import IsAppAdmin, IsObjectOwner


def _request(user: object) -> SimpleNamespace:
    return SimpleNamespace(user=user)


def test_is_app_admin_permits_a_staff_user() -> None:
    user = User(pk=1, is_staff=True)
    assert IsAppAdmin().has_permission(_request(user), None) is True


def test_is_app_admin_denies_an_authenticated_non_staff_user() -> None:
    user = User(pk=1, is_staff=False)
    assert IsAppAdmin().has_permission(_request(user), None) is False


def test_is_app_admin_denies_an_anonymous_user() -> None:
    assert IsAppAdmin().has_permission(_request(AnonymousUser()), None) is False


def test_is_object_owner_permits_the_owner() -> None:
    user = User(pk=1)
    obj = SimpleNamespace(user=user)
    assert IsObjectOwner().has_object_permission(_request(user), None, obj) is True


def test_is_object_owner_denies_another_users_object() -> None:
    """The IDOR case named explicitly by APP-DESIGN.md §7.4 and §9's security checklist."""
    owner = User(pk=1)
    other = User(pk=2)
    obj = SimpleNamespace(user=owner)
    assert IsObjectOwner().has_object_permission(_request(other), None, obj) is False


def test_is_object_owner_denies_an_anonymous_user() -> None:
    obj = SimpleNamespace(user=User(pk=1))
    assert IsObjectOwner().has_object_permission(_request(AnonymousUser()), None, obj) is False


def test_is_object_owner_denies_rather_than_raises_for_a_misconfigured_owner_field() -> None:
    """A missing `owner_field` attribute must fail closed, never raise `AttributeError`
    mid-permission-check.
    """
    user = User(pk=1)
    obj = SimpleNamespace()  # no `user` attribute at all
    assert IsObjectOwner().has_object_permission(_request(user), None, obj) is False
