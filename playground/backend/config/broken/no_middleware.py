"""Deliberately broken: RequestIDMiddleware removed from MIDDLEWARE -> appkit.E001 (Error).

    docker compose exec backend python manage.py check --settings=config.broken.no_middleware
"""

from config.settings import *  # noqa: F403

MIDDLEWARE = [m for m in MIDDLEWARE if m != "appkit.request_id.RequestIDMiddleware"]  # noqa: F405
