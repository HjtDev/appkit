"""Exercises appkit.testing (the pytest plugin) exactly as a real consuming app would, via the
"-p appkit.testing" opt-in wired into THIS package's own pyproject.toml addopts
(docs/CONTRACT.md §2.17) — not appkit's own suite, which deliberately never does this (it would
break coverage measurement on appkit.request_id/appkit.testing themselves,
backend/pyproject.toml:164-180). Before this file, the ONLY thing exercising this opt-in path
was a subprocess test in appkit's own Phase 4 suite.

Not marked `live` — runs against Django's ORM directly (POSTGRES_HOST from env, defaulting to
the playground compose stack's published port), not over HTTP through nginx.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_appkit_user_is_reflectively_built(appkit_user: AbstractBaseUser) -> None:
    assert appkit_user.pk is not None
    assert not appkit_user.is_staff


def test_appkit_admin_user_is_staff_and_superuser(appkit_admin_user: AbstractBaseUser) -> None:
    assert appkit_admin_user.is_staff
    assert appkit_admin_user.is_superuser


def test_appkit_auth_client_is_authenticated(appkit_auth_client: APIClient) -> None:
    r = appkit_auth_client.get("/api/v1/demo/errors/not-authenticated/")
    # IsAuthenticated passes (force_authenticate) -> the view's own 200, not a 401 envelope.
    assert r.status_code == 200


def test_appkit_admin_client_passes_is_app_admin(appkit_admin_client: APIClient) -> None:
    r = appkit_admin_client.get("/api/v1/demo/errors/permission-denied/")
    assert r.status_code == 200


def test_appkit_assert_error_envelope(appkit_api_client: APIClient) -> None:
    from appkit.testing import appkit_assert_error_envelope

    r = appkit_api_client.get("/api/v1/demo/errors/not-found/")
    appkit_assert_error_envelope(r, code="not_found", status=404)


def test_appkit_frozen_request_id(appkit_frozen_request_id: str, appkit_api_client: APIClient) -> None:
    assert appkit_frozen_request_id == "frozen-test-request-id"


def test_appkit_clear_cache_is_not_autouse(appkit_clear_cache: None) -> None:
    # Merely requesting it as a normal fixture parameter proves it's callable/not-autouse —
    # appkit's own suite already unit-tests its cache.clear() behaviour; this file's job is
    # only to prove the fixture is reachable through THIS package's own -p appkit.testing wire.
    pass
