"""Deliberately broken: APPKIT contains a typo'd key not in appkit.conf.DEFAULTS ->
appkit.W003 (Warning). CACHE_TIMOUT (missing E) silently falls back to the CACHE_TIMEOUT
default forever — the whole point of this check.

    docker compose exec backend python manage.py check --settings=config.broken.unknown_appkit_key
"""

from config.settings import *  # noqa: F403

APPKIT = {**APPKIT, "CACHE_TIMOUT": 30}  # noqa: F405 - deliberate typo, not a real key
