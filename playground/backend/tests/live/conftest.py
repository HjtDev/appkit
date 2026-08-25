"""Fixtures for tests hitting the REAL docker-compose stack over HTTP through nginx — not
Django's test client. Requires `docker compose -f playground/docker-compose.yml up -d --wait`
to already be running (see playground/README.md).
"""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterator

import httpx
import pytest

BASE_HTTP = os.environ.get("PLAYGROUND_BASE_HTTP", "http://localhost:8080")
BASE_HTTPS = os.environ.get("PLAYGROUND_BASE_HTTPS", "https://localhost:8443")
BACKEND_CONTAINER = os.environ.get("PLAYGROUND_BACKEND_CONTAINER", "appkit-playground-backend-1")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # `pytestmark` only auto-applies within the test MODULE that defines it, not from a
    # conftest.py — this is the actual mechanism that marks every test under tests/live/ as
    # `live`, so `pytest -m live` / `pytest -m "not live"` (see pyproject.toml's marker
    # definition) can select/deselect this whole directory without touching every file.
    here = os.path.dirname(__file__)
    for item in items:
        if str(item.fspath).startswith(here):
            item.add_marker(pytest.mark.live)


@pytest.fixture(scope="session")
def base_http() -> str:
    return BASE_HTTP


@pytest.fixture(scope="session")
def base_https() -> str:
    return BASE_HTTPS


@pytest.fixture
def http_client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_HTTP, timeout=10.0) as client:
        yield client


@pytest.fixture
def https_client() -> Iterator[httpx.Client]:
    # verify=False: the cert is self-signed by design (playground/nginx/Dockerfile) — this
    # test suite's job is to prove appkit's OWN behaviour behind TLS termination, not to
    # validate a real CA chain.
    with httpx.Client(base_url=BASE_HTTPS, timeout=10.0, verify=False) as client:  # noqa: S501
        yield client


def _unique_username() -> str:
    return f"live-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def new_user_credentials(http_client: httpx.Client) -> tuple[str, str]:
    """Creates a fresh Django user directly inside the running backend container via
    `manage.py shell`, so each test gets a user nobody else's test run has touched — avoids
    hand-rolling a signup endpoint the demo app doesn't have.
    """
    username = _unique_username()
    password = "live-test-password-123"  # noqa: S105
    script = (
        "from django.contrib.auth import get_user_model; "
        "U = get_user_model(); "
        f"U.objects.filter(username={username!r}).exists() or "
        f"U.objects.create_user({username!r}, password={password!r})"
    )
    result = run_manage(["shell", "-c", script])
    assert result.returncode == 0, result.stderr
    return username, password


def run_manage(args: list[str], *, settings: str | None = None) -> subprocess.CompletedProcess[str]:
    """Runs `manage.py <args>` INSIDE the live backend container via `docker exec` — the only
    way to exercise config.broken.* settings modules and the pytest plugin against the exact
    environment the compose stack actually boots, not a locally-simulated one.
    """
    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "manage.py", *args]
    if settings:
        cmd.append(f"--settings={settings}")
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
