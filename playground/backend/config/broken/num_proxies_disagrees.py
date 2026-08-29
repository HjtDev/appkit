"""Deliberately broken: REST_FRAMEWORK["NUM_PROXIES"] is set but disagrees with
APPKIT["TRUSTED_PROXY_COUNT"] (1, config/settings.py) -> appkit.W006 (Warning).

    docker compose exec backend python manage.py check --settings=config.broken.num_proxies_disagrees
"""

from config.settings import *  # noqa: F403

REST_FRAMEWORK["NUM_PROXIES"] = 2  # noqa: F405
