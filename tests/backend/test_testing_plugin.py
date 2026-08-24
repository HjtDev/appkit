"""`appkit.testing` — the opt-in pytest plugin (docs/CONTRACT.md §2.17).

Every fixture below carries an `appkit_` prefix (APP-DESIGN.md §1.3's namespacing rule applied
to pytest's fixture registry — see `testing.py`'s module docstring for the full rationale,
including the pytest-django `admin_user`/`admin_client` collision that's the concrete evidence
for why this convention exists here).

Every fixture is exercised by calling its underlying `_fixture_function` directly rather than
requesting it as an ordinary pytest fixture parameter — purely a **coverage-measurement**
concern: `backend/pyproject.toml`'s `addopts` deliberately does NOT carry `-p appkit.testing`
(loading a plugin that way happens before pytest-cov's tracer attaches, and coverage.py then
permanently can't see any of that module's lines as executed — see the addopts comment).
Importing `appkit.testing` normally, here, keeps it inside pytest-cov's measurement.

The one thing that can't be exercised this way — `appkit_user`/`appkit_admin_user` built
reflectively against a genuinely non-`username` `USERNAME_FIELD` custom user model — gets its
own subprocess leg at the bottom of this file, which also happens to be the one place the real
`-p appkit.testing` opt-in load path is proven end to end (see that test's docstring for
confirmation of exactly what it proves).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

import appkit.testing as testing_module

if TYPE_CHECKING:
    from rest_framework.response import Response

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
TESTS_DIR = Path(__file__).resolve().parent


def _call(fixture: object, *args: object) -> object:
    """Invokes a `@pytest.fixture`-decorated function's underlying plain function directly,
    bypassing pytest's fixture-name resolution (and, incidentally, the coverage-measurement
    concern the module docstring explains).
    """
    return fixture._fixture_function(*args)  # type: ignore[attr-defined]


# ------------------------------------------------------- api_client / user / admin_user


def test_api_client_is_unauthenticated() -> None:
    client = _call(testing_module.appkit_api_client)
    assert client.handler._force_user is None  # type: ignore[attr-defined]


def test_user_fixture_builds_through_username_field(db: None) -> None:
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    user = _call(testing_module.appkit_user, None)
    assert getattr(user, username_field)
    assert user.pk is not None  # type: ignore[attr-defined]
    assert user.is_staff is False  # type: ignore[attr-defined]


def test_admin_user_fixture_is_staff_and_superuser(db: None) -> None:
    admin = _call(testing_module.appkit_admin_user, None)
    assert admin.is_staff is True  # type: ignore[attr-defined]
    assert admin.is_superuser is True  # type: ignore[attr-defined]


def test_user_and_admin_user_are_distinct_records(db: None) -> None:
    user = _call(testing_module.appkit_user, None)
    admin = _call(testing_module.appkit_admin_user, None)
    assert user.pk != admin.pk  # type: ignore[attr-defined]


def test_auth_client_is_force_authenticated_as_user(db: None) -> None:
    user = _call(testing_module.appkit_user, None)
    client = _call(testing_module.appkit_api_client)
    result = _call(testing_module.appkit_auth_client, client, user)
    assert result.handler._force_user == user  # type: ignore[attr-defined]


def test_admin_client_is_force_authenticated_as_admin_user(db: None) -> None:
    admin = _call(testing_module.appkit_admin_user, None)
    client = _call(testing_module.appkit_api_client)
    result = _call(testing_module.appkit_admin_client, client, admin)
    assert result.handler._force_user == admin  # type: ignore[attr-defined]


# ------------------------------------------------------------------- frozen_request_id


def test_frozen_request_id_yields_the_fixed_value_and_restores_on_teardown() -> None:
    from appkit.request_id import request_id_var

    prior = request_id_var.get()
    generator = testing_module.appkit_frozen_request_id._fixture_function()  # type: ignore[attr-defined]
    yielded = next(generator)
    assert yielded == "frozen-test-request-id"
    assert request_id_var.get() == yielded

    with pytest.raises(StopIteration):
        next(generator)  # drives the `finally` block, including its internal assertion
    assert request_id_var.get() == prior


# ------------------------------------------------------------------------------ clear_cache


def test_clear_cache_is_not_autouse() -> None:
    """§2.17: deliberately not autouse (xdist cross-worker interference under a shared
    backend). Reads the fixture's own marker so a future edit adding `autouse=True` fails this
    test loudly instead of silently changing behaviour.
    """
    marker = testing_module.appkit_clear_cache._fixture_function_marker  # type: ignore[attr-defined]
    assert marker.autouse is False


def test_clear_cache_clears_the_default_cache() -> None:
    from django.core.cache import cache

    cache.set("appkit-testing-probe", "value")
    _call(testing_module.appkit_clear_cache)
    assert cache.get("appkit-testing-probe") is None


# ------------------------------------------------------------------------ assert_error_envelope


def _fake_response(data: dict[str, object], *, status_code: int) -> Response:
    """A minimal stand-in with the two attributes `appkit_assert_error_envelope` reads — avoids
    pulling in `rest_framework.response` just to poke two attributes.
    """
    from types import SimpleNamespace

    return SimpleNamespace(data=data, status_code=status_code)  # type: ignore[return-value]


def test_assert_error_envelope_passes_for_a_matching_envelope() -> None:
    response = _fake_response(
        {"error": {"code": "not_found", "message": "x", "details": {}, "request_id": "-"}},
        status_code=404,
    )
    testing_module.appkit_assert_error_envelope(response, code="not_found", status=404)  # no raise


def test_assert_error_envelope_raises_for_a_status_mismatch() -> None:
    response = _fake_response(
        {"error": {"code": "not_found", "message": "x", "details": {}, "request_id": "-"}},
        status_code=403,
    )
    with pytest.raises(AssertionError, match="status"):
        testing_module.appkit_assert_error_envelope(response, code="not_found", status=404)


def test_assert_error_envelope_raises_for_a_code_mismatch() -> None:
    response = _fake_response(
        {
            "error": {
                "code": "permission_denied",
                "message": "x",
                "details": {},
                "request_id": "-",
            }
        },
        status_code=403,
    )
    with pytest.raises(AssertionError, match="not_found"):
        testing_module.appkit_assert_error_envelope(response, code="not_found", status=403)


def test_assert_error_envelope_raises_when_envelope_is_missing_entirely() -> None:
    response = _fake_response({"detail": "not found"}, status_code=404)
    with pytest.raises(AssertionError, match="envelope"):
        testing_module.appkit_assert_error_envelope(response, code="not_found", status=404)


def test_assert_error_envelope_raises_when_a_key_is_missing_from_the_envelope() -> None:
    response = _fake_response({"error": {"code": "not_found"}}, status_code=404)
    with pytest.raises(AssertionError, match="missing"):
        testing_module.appkit_assert_error_envelope(response, code="not_found", status=404)


# ---------------------------------------------------------------- reflective USERNAME_FIELD
# (subprocess leg — a non-`username` custom user model can only be exercised in a fresh
# process, since AUTH_USER_MODEL is resolved once per process by Django; this is also the one
# place the real `-p appkit.testing` opt-in load path is proven end to end)


@pytest.mark.integration
def test_reflective_user_fixture_against_a_non_username_user_model() -> None:
    """docs/CONTRACT.md §2.17's mandatory non-obvious-failure-path test: `appkit_user`/
    `appkit_admin_user` must work against a host on a non-`username` `USERNAME_FIELD`, not just
    appkit's own default test settings.

    Confirmation that this genuinely exercises the real `-p appkit.testing` opt-in path, not
    just the fixture logic: `probe_user_fixture.py`'s two tests request `appkit_user`/
    `appkit_admin_user` as ORDINARY fixture parameters (unlike every test above, which calls
    `_fixture_function` directly) — if `-p appkit.testing` failed to load, or the plugin's
    fixtures weren't actually registered, pytest would raise `fixture 'appkit_user' not found`
    at collection time and this subprocess would exit non-zero with that error, not silently
    pass. The `-o addopts=` above also strips this repo's OWN `-p`-avoiding addopts, so the only
    reason `appkit.testing`'s fixtures are available to the probe at all is the explicit
    `-p appkit.testing` on this command line — the exact mechanism a consuming app's own
    `pyproject.toml` uses.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TESTS_DIR / "probe_user_fixture.py"),
            "--ds=tests.backend.settings_email_user",
            "-p",
            "appkit.testing",
            "-o",
            "addopts=",
            "-o",
            "python_files=probe_*.py",
            # This probe doesn't touch crypto/images at all — satisfies conftest.py's
            # extras-guard (which otherwise assumes any run lacking this marker expression is
            # the coverage gate and demands both extras) without being a genuine bare-install
            # assertion itself.
            "-m",
            "not requires_extra",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONPATH": f"{BACKEND_DIR / 'src'}:{BACKEND_DIR.parent}"},
    )
    assert result.returncode == 0, (
        f"reflective user-fixture subprocess failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "2 passed" in result.stdout, result.stdout
