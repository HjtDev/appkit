"""Proves the flake8-tidy-imports banned-api block in backend/pyproject.toml actually fires.

A banned-api entry with a typo'd module name is silent — ruff simply never flags it, and
appkit's ONE structural rule (never import a host module: no tools.*, no core.*, no config.*)
would be unenforced without anyone noticing. This runs ruff itself against a probe import,
outside the tests/** tree's own TID251 exemption, and asserts it's rejected.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

BANNED_HOST_MODULES = ["tools", "core", "config"]


@pytest.mark.parametrize("module", BANNED_HOST_MODULES)
def test_host_module_import_is_banned(module: str) -> None:
    """`from <module> import x` inside src/appkit must be rejected by ruff's TID251 rule.

    Checked via `ruff check --stdin-filename`, pointed at a path INSIDE src/appkit/ (not
    tests/**, which is TID251-exempt per pyproject.toml's per-file-ignores) so the probe is
    subject to the real banned-api block rather than the test tree's own exemption.
    """
    probe_source = f"from {module} import something\n"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--stdin-filename",
            "src/appkit/_import_boundary_probe.py",
            "-",
        ],
        input=probe_source,
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
    )

    assert result.returncode != 0, (
        f"ruff accepted `from {module} import ...` inside src/appkit — the banned-api entry "
        f"for {module!r} is missing or not firing.\nstdout:\n{result.stdout}"
    )
    assert "TID251" in result.stdout, (
        f"ruff rejected the probe for {module!r}, but not via TID251 (banned-api) — "
        f"got:\n{result.stdout}"
    )
