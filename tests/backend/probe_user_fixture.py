"""Subprocess probe for `appkit.testing`'s `appkit_user`/`appkit_admin_user` fixtures against a
non-`username` `USERNAME_FIELD` (docs/CONTRACT.md §2.17).

Deliberately **not** named `test_*.py` — the main suite's `python_files = ["test_*.py"]`
pattern skips it during ordinary collection. It's invoked directly, as an explicit path, by a
separate `pytest` subprocess in `test_testing_plugin.py`, pointed at
`tests.backend.settings_email_user` and loaded with `-p appkit.testing`.
"""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_user_fixture_builds_through_the_email_username_field(appkit_user: object) -> None:
    assert getattr(appkit_user, "email", None)
    assert getattr(appkit_user, "pk", None) is not None


@pytest.mark.django_db
def test_admin_user_fixture_is_staff_and_superuser(appkit_admin_user: object) -> None:
    assert appkit_admin_user.is_staff is True  # type: ignore[attr-defined]
    assert appkit_admin_user.is_superuser is True  # type: ignore[attr-defined]
