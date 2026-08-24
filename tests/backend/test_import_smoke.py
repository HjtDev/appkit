"""Every `appkit.*` module imports cleanly with neither optional extra installed
(docs/CONTRACT.md §9's bare-install CI leg) — and, incidentally, keeps the still-stub modules
out of the 0%-coverage bucket that would otherwise drag the whole package under the 95% gate
before their own phase writes real tests against them.
"""

from __future__ import annotations

import importlib

MODULES = [
    "appkit",
    "appkit.apps",
    "appkit.cache",
    "appkit.checks",
    "appkit.conf",
    "appkit.crypto",
    "appkit.dates",
    "appkit.exceptions",
    "appkit.files",
    "appkit.media",
    "appkit.mixins",
    "appkit.money",
    "appkit.net",
    "appkit.pagination",
    "appkit.permissions",
    "appkit.request_id",
    "appkit.testing",
    "appkit.text",
    "appkit.throttling",
    "appkit.validation",
]


def test_every_public_module_imports_cleanly() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
