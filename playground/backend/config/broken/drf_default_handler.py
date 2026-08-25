"""Deliberately broken: EXCEPTION_HANDLER left at DRF's own default -> appkit.E002 (Error).

    docker compose exec backend python manage.py check --settings=config.broken.drf_default_handler
"""

from config.settings import *  # noqa: F403

REST_FRAMEWORK["EXCEPTION_HANDLER"] = "rest_framework.views.exception_handler"  # noqa: F405
