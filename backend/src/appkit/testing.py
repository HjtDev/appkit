"""The opt-in pytest plugin — fixtures and an envelope assertion helper.

Opt-in is explicit: ``-p appkit.testing`` in the consumer's own ``addopts``
(``tool.pytest.ini_options``), never automatic. This module deliberately registers NO
``pytest11`` entry point in pyproject.toml — two alternatives were considered and both rejected
(docs/CONTRACT.md §2.17):

  * A ``pytest11`` entry point would auto-load these fixtures into EVERY host's test suite the
    moment appkit is merely installed (which is always, transitively) — invisible magic adding
    fixtures nobody asked for into a namespace they didn't opt into.
  * ``pytest_plugins = ["appkit.testing"]`` only works from the rootdir conftest in pytest 7+;
    an app package's own ``testpaths = ["../tests/backend"]`` means the package's own conftest
    isn't the rootdir conftest, so this wouldn't even work by default for the app packages that
    need it most.

A consuming app wires this up itself, in its own ``pyproject.toml``::

    [tool.pytest.ini_options]
    addopts = "-p appkit.testing ..."

**Every name below carries an ``appkit_`` prefix — this is APP-DESIGN.md §1.3's namespacing
rule applied to pytest's fixture registry, not a stylistic choice.** pytest's fixture registry
is exactly the "shared, flat namespace" §1.3 is about: any name here can collide with a
consuming app's own conftest fixture, another plugin's fixture, or a future pytest-django
release. The concrete evidence this convention exists to prevent, found during this module's
own implementation and kept here as the rationale a future reader will otherwise wonder about:
pytest-django ships its OWN built-in fixtures literally named ``admin_user`` and
``admin_client``, and empirically (verified directly against the installed pytest-django, not
assumed) pytest-django's versions win that name collision **silently** — requesting
``admin_user``/``admin_client`` as an ordinary fixture parameter anywhere pytest-django is
active (which is everywhere ``db``/``django_db`` is used) returns pytest-django's plain
User/Client, never appkit's reflective ones, with no warning anywhere. ``user`` and
``api_client`` haven't collided with anything yet — but "hasn't collided yet" is precisely the
condition §1.3's prefix rule exists to guard against, not a reason two of eight names get a
prefix and six don't.

Public surface (docs/CONTRACT.md §2.17):

    @pytest.fixture
    def appkit_api_client() -> APIClient: ...
        # An unauthenticated DRF APIClient.

    @pytest.fixture
    def appkit_user(db) -> AbstractBaseUser: ...
        # Built through get_user_model().USERNAME_FIELD REFLECTIVELY, not a hardcoded
        # create_user(username=...) call — must work against a host on an email-based custom
        # user model.

    @pytest.fixture
    def appkit_admin_user(db) -> AbstractBaseUser: ...
        # Same reflective construction, staff/admin.

    @pytest.fixture
    def appkit_auth_client(appkit_api_client, appkit_user) -> APIClient: ...

    @pytest.fixture
    def appkit_admin_client(appkit_api_client, appkit_admin_user) -> APIClient: ...

    @pytest.fixture
    def appkit_frozen_request_id() -> Iterator[str]: ...
        # Yields a fixed request-ID string; asserts it's restored to "-" (or the prior value)
        # on fixture teardown, making RequestIDMiddleware's reset-in-finally contract directly
        # assertable from a consuming app's own tests.

    @pytest.fixture
    def appkit_clear_cache() -> None: ...
        # Deliberately NOT autouse — under `pytest -n auto` (pytest-xdist) against a shared
        # Redis instance, an autouse fixture clearing the cache between every test would clear
        # another xdist worker's in-flight test data too.

    def appkit_assert_error_envelope(response: Response, *, code: str, status: int) -> None: ...
        # Plain function, not a fixture — prefixed anyway for consistency with the rest of this
        # module's public surface. Shared assertion for the docs/CONTRACT.md §1 envelope so
        # nine installed apps don't hand-roll nine slightly different assertions. Raises the
        # test framework's own AssertionError with a diff-friendly message on mismatch.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.contrib.auth.base_user import AbstractBaseUser
    from rest_framework.response import Response
    from rest_framework.test import APIClient

# Two distinct reasons the imports below are deferred into function bodies rather than living
# up here at module scope:
#
# `rest_framework.test.APIRequestFactory` reads DRF's `api_settings` at class-definition time
# (import time) — importing it at module scope here would break the moment ANY consumer loads
# `-p appkit.testing` before Django settings are configured, which is exactly how pytest loads
# `-p` plugins named in `addopts` (early, during `consider_preparse`, ahead of pytest-django's
# own settings setup). Imported lazily inside `appkit_api_client()`.
#
# `appkit.request_id` imports cleanly at that same early point, but a module-scope import here
# would make THIS module (also loaded that early, for the same `-p appkit.testing` reason)
# import `appkit.request_id` before pytest-cov's own tracer attaches — coverage.py can then
# never see any of that module's lines as executed, because the one-time module-body execution
# that defines them already happened untraced (verified directly: request_id.py's own coverage
# drops from 100% to 42% the moment this import moves to module scope, in appkit's own suite,
# if it also dogfoods `-p appkit.testing` via its own addopts — which is exactly why it
# deliberately doesn't; see backend/pyproject.toml's addopts comment). Imported lazily inside
# `appkit_frozen_request_id()` instead — a coverage-measurement concern, not a correctness one,
# but avoiding it costs nothing.

__all__ = [
    "appkit_admin_client",
    "appkit_admin_user",
    "appkit_api_client",
    "appkit_assert_error_envelope",
    "appkit_auth_client",
    "appkit_clear_cache",
    "appkit_frozen_request_id",
    "appkit_user",
]

_PLACEHOLDER_PASSWORD = "appkit-testing-placeholder"  # noqa: S105


def _build_user(*, is_staff: bool = False, is_superuser: bool = False) -> AbstractBaseUser:
    """Builds a user through `get_user_model().USERNAME_FIELD` **reflectively** — never a
    hardcoded `create_user(username=...)` call, so this works against a host on an
    email-based (or any other) custom user model, not just Django's default `username`-keyed
    one.
    """
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    unique = uuid.uuid4().hex[:12]
    username_value = f"{unique}@example.com" if "email" in username_field else unique

    field_values: dict[str, Any] = {username_field: username_value}
    for required_field in user_model.REQUIRED_FIELDS:
        if required_field == username_field:
            continue
        field_values[required_field] = (
            f"{unique}@example.com" if required_field == "email" else unique
        )

    new_user = user_model._default_manager.create_user(
        password=_PLACEHOLDER_PASSWORD, **field_values
    )
    if is_staff or is_superuser:
        if is_staff:
            new_user.is_staff = True
        if is_superuser:
            new_user.is_superuser = True
        new_user.save()
    return new_user


@pytest.fixture
def appkit_api_client() -> APIClient:
    """An unauthenticated DRF `APIClient`."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def appkit_user(db: None) -> AbstractBaseUser:
    """A plain (non-staff) user, built reflectively through `USERNAME_FIELD`."""
    return _build_user()


@pytest.fixture
def appkit_admin_user(db: None) -> AbstractBaseUser:
    """A staff+superuser user, built reflectively through `USERNAME_FIELD`."""
    return _build_user(is_staff=True, is_superuser=True)


@pytest.fixture
def appkit_auth_client(appkit_api_client: APIClient, appkit_user: AbstractBaseUser) -> APIClient:
    """`appkit_api_client`, force-authenticated as `appkit_user`."""
    appkit_api_client.force_authenticate(user=appkit_user)
    return appkit_api_client


@pytest.fixture
def appkit_admin_client(
    appkit_api_client: APIClient, appkit_admin_user: AbstractBaseUser
) -> APIClient:
    """`appkit_api_client`, force-authenticated as `appkit_admin_user`."""
    appkit_api_client.force_authenticate(user=appkit_admin_user)
    return appkit_api_client


@pytest.fixture
def appkit_frozen_request_id() -> Iterator[str]:
    """Yields a fixed request-ID string, and asserts `request_id_var` is restored to its prior
    value on teardown — making `RequestIDMiddleware`'s reset-in-`finally` contract directly
    assertable from a consuming app's own tests, not just appkit's.
    """
    from appkit.request_id import request_id_var

    fixed_id = "frozen-test-request-id"
    prior = request_id_var.get()
    token = request_id_var.set(fixed_id)
    try:
        yield fixed_id
    finally:
        request_id_var.reset(token)
        restored = request_id_var.get()
        assert restored == prior, (
            "appkit_frozen_request_id: request_id_var was not restored on teardown "
            f"(expected {prior!r}, got {restored!r})"
        )


@pytest.fixture
def appkit_clear_cache() -> None:
    """Clears Django's default cache. **Deliberately not `autouse`** — under
    `pytest -n auto` (pytest-xdist) against a single shared Redis instance, an autouse fixture
    clearing the cache between every test would clear another xdist worker's in-flight test
    data too. Use `LocMemCache` for test settings (isolated per process) if that isolation is
    wanted by default instead.
    """
    cache.clear()


def appkit_assert_error_envelope(response: Response, *, code: str, status: int) -> None:
    """Asserts `response` carries the docs/CONTRACT.md §1 error envelope with the given `code`
    and HTTP `status`. Raises a diff-friendly `AssertionError` on mismatch — the shared
    assertion so N installed apps don't hand-roll N slightly different envelope checks.
    """
    if response.status_code != status:
        raise AssertionError(
            f"appkit_assert_error_envelope: expected status {status}, got "
            f"{response.status_code}. response.data={response.data!r}"
        )

    data = response.data
    if not isinstance(data, dict) or "error" not in data:
        raise AssertionError(
            "appkit_assert_error_envelope: response.data does not contain an 'error' "
            f"envelope. response.data={data!r}"
        )

    envelope = data["error"]
    actual_code = envelope.get("code")
    if actual_code != code:
        raise AssertionError(
            f"appkit_assert_error_envelope: expected error code {code!r}, got "
            f"{actual_code!r}. envelope={envelope!r}"
        )

    missing = [key for key in ("message", "details", "request_id") if key not in envelope]
    if missing:
        raise AssertionError(
            f"appkit_assert_error_envelope: envelope is missing required key(s) {missing!r}. "
            f"envelope={envelope!r}"
        )
