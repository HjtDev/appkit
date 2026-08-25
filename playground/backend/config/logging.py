"""Playground's own logging config module — mirrors what a real base-scaffold host's
`backend/config/logging.py` looks like after wiring in appkit, per README.md:79-82:

    # backend/config/logging.py
    from appkit.request_id import RequestIDFilter, request_id_var  # was defined locally

The rest of this file (the `LOGGING` dict shape, `build_logging_config()`) is NOT part of
appkit's wiring block — appkit's README supplies only the import line above. Everything else
here is playground-authored, standing in for a real host's pre-existing `config/logging.py`,
so that appkit.checks.check_logging_filter (appkit.W005) has something real to validate against
and request-ID correlation is actually observable in `docker compose logs backend`.
"""

from __future__ import annotations

from typing import Any

# ---- README.md:79-82, verbatim ----
from appkit.request_id import RequestIDFilter, request_id_var  # was defined locally  # noqa: F401


def build_logging_config(*, debug: bool) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIDFilter},
        },
        "formatters": {
            "with_request_id": {
                "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "filters": ["request_id"],
                "formatter": "with_request_id",
            },
        },
        "root": {"handlers": ["console"], "level": "DEBUG" if debug else "INFO"},
    }
