"""Deliberately broken: EXCEPTION_HANDLER points somewhere that is neither DRF's default nor
appkit's -> appkit.W001 (Warning, silenceable). Legitimate if a host wraps appkit's handler in
its own; this module exists to prove the warning fires when that's NOT what happened.

    docker compose exec backend python manage.py check --settings=config.broken.foreign_handler
"""

from config.settings import *  # noqa: F403

REST_FRAMEWORK["EXCEPTION_HANDLER"] = "demo.views.healthz"  # noqa: F405 - any non-appkit dotted path
