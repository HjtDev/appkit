"""Shared pytest fixtures for appkit's own test suite.

`golden` loads a fixture file from `tests/fixtures/` — the location
`tests/fixtures/README.md` already pins for the Python half: `Path(__file__).parents[1] /
"fixtures"` resolves to `tests/fixtures` from here (`tests/backend/conftest.py`).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from django.core.cache import cache

_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"


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
