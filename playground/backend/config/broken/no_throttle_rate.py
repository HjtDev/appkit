"""Deliberately broken: DemoItemListView declares throttle_scope="demo_list", but this settings
module removes it from DEFAULT_THROTTLE_RATES -> appkit.W004 (Warning), one per missing scope.

    docker compose exec backend python manage.py check --settings=config.broken.no_throttle_rate
"""

from config.settings import *  # noqa: F403

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405
