"""Shared pytest fixtures for appkit's own test suite.

`golden` loads a fixture file from `tests/fixtures/` — the location
`tests/fixtures/README.md` already pins for the Python half: `Path(__file__).parents[1] /
"fixtures"` resolves to `tests/fixtures` from here (`tests/backend/conftest.py`).
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from django.core.cache import cache

_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"

# docs/CONTRACT.md §9's two-leg test strategy: the gate leg (`-m "not requires_extra"` absent
# from the invocation) MUST have both extras installed, or the security-relevant crypto/image
# tests would silently not exist rather than fail. `pytest.UsageError` aborts before collection
# — a misconfigured gate run fails on the first line instead of passing green.
_EXTRAS_FOR_GATE = {
    "cryptography": "uv run --extra crypto --extra images pytest",
    "PIL": "uv run --extra crypto --extra images pytest",
}


def pytest_configure(config: pytest.Config) -> None:
    markexpr = config.getoption("-m", default="") or ""
    if "not requires_extra" in markexpr:
        return  # the bare-install leg — deliberately runs without either extra

    missing = [name for name in _EXTRAS_FOR_GATE if importlib.util.find_spec(name) is None]
    if missing:
        raise pytest.UsageError(
            f"The gate test run requires both the 'crypto' and 'images' extras installed "
            f"(missing: {missing!r}). Run: uv run --extra crypto --extra images pytest\n"
            f"(For the bare-install leg instead, pass -m 'not requires_extra' explicitly.)"
        )


@pytest.fixture
def golden() -> Callable[[str], Any]:
    """Returns a loader: `golden("error-codes.json")` -> the parsed JSON value."""

    def _load(filename: str) -> Any:
        return json.loads((_FIXTURES_DIR / filename).read_text())

    return _load


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Isolates each test's cache state — `appkit.testing`'s `clear_cache` fixture is a later
    phase's opt-in equivalent; this repo's own suite needs isolation regardless.
    """
    cache.clear()
    yield
    cache.clear()
