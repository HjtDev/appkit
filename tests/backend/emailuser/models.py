"""A minimal, email-keyed custom user model — the non-`username` `USERNAME_FIELD` case
docs/CONTRACT.md §2.17 requires `appkit.testing`'s `appkit_user`/`appkit_admin_user` fixtures to
be proven against.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class EmailUserManager(BaseUserManager):
    def create_user(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> EmailUser:
        if not email:
            raise ValueError("EmailUser.objects.create_user() requires an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> EmailUser:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class EmailUser(AbstractBaseUser):
    """A deliberately minimal user model keyed on `email`, not `username` — `username` doesn't
    exist on this model at all, so a fixture that assumes it would fail immediately.

    Deliberately skips `PermissionsMixin`: its `groups`/`user_permissions` M2M fields carry a
    foreign key onto `auth.Group`/`auth.Permission`, and Django's own `migrate --run-syncdb`
    (what `manage.py test`/pytest-django use to build a test DB) creates unmigrated apps'
    tables *before* running migrated apps' migrations — an FK from this unmigrated app onto a
    not-yet-existing `auth_group` table fails outright. `is_staff`/`is_superuser` alone are
    enough for what this model exists to prove.
    """

    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = EmailUserManager()

    class Meta:
        app_label = "emailuser"

    def __str__(self) -> str:
        return self.email
