"""ASGI entrypoint. Required, not optional, in this playground:
appkit.request_id.RequestIDMiddleware is async-only (sync_capable = False,
markcoroutinefunction(self) in its own __init__) — see config/settings.py's ASGI_APPLICATION
comment and playground/FINDINGS.md.
"""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
