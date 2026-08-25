"""Deliberately broken: LOGGING is configured but no handler references a filter resolving to
appkit.request_id.RequestIDFilter -> appkit.W005 (Warning).

    docker compose exec backend python manage.py check --settings=config.broken.no_logging_filter
"""

from config.settings import *  # noqa: F403

LOGGING = {  # noqa: F405 - overriding the name, not reading it
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
