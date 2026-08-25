"""Deliberately broken: RequestIDMiddleware ordered before SecurityMiddleware -> appkit.W002
(Warning).

    docker compose exec backend python manage.py check --settings=config.broken.middleware_order
"""

from config.settings import *  # noqa: F403

MIDDLEWARE = [m for m in MIDDLEWARE if m != "appkit.request_id.RequestIDMiddleware"]  # noqa: F405
MIDDLEWARE.insert(0, "appkit.request_id.RequestIDMiddleware")
