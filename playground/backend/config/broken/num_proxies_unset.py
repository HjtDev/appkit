"""Deliberately broken: unsets REST_FRAMEWORK["NUM_PROXIES"] while ScopedRateThrottle is still
configured (DEFAULT_THROTTLE_CLASSES, config/settings.py) -> appkit.W006 (Warning).

    docker compose exec backend python manage.py check --settings=config.broken.num_proxies_unset
"""

from config.settings import *  # noqa: F403

del REST_FRAMEWORK["NUM_PROXIES"]  # noqa: F405
