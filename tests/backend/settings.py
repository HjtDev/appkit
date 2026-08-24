"""Minimal Django settings for appkit's own test suite.

Lives in the test tree, not the package — the package must never contain a settings file
(APP-DESIGN.md §7.1). Kept deliberately minimal: if appkit's tests only pass with extra apps
installed, appkit has an undeclared dependency on host configuration.

Deviates from APP-DESIGN.md §7.1's generic template in ways forced by docs/CONTRACT.md:

  * No drf_spectacular / SPECTACULAR_SETTINGS — docs/CONTRACT.md §9 lists drf-spectacular under
    "deliberately not depended on"; nothing in appkit introspects an OpenAPI schema.
  * appkit itself is in INSTALLED_APPS (docs/CONTRACT.md §5).
  * MIDDLEWARE and REST_FRAMEWORK["EXCEPTION_HANDLER"] are wired here, non-optionally: appkit.E001
    and appkit.E002 are Errors, so appkit's own test settings must satisfy appkit's own system
    checks or `manage.py check` (and anything that triggers it) fails outright.
  * CACHES uses LocMemCache, per docs/CONTRACT.md §2.17's explicit recommendation — isolates
    appkit.testing's (deliberately non-autouse) clear_cache fixture per xdist worker process.
"""

from __future__ import annotations

SECRET_KEY = "test-only-not-a-secret"  # noqa: S105
DEBUG = False
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "appkit",
]
# No django.contrib.admin/messages/staticfiles: appkit ships no admin.py, no message-driven
# views, and no static assets (docs/CONTRACT.md §10) — the §7.1 generic template includes them
# for an app with admin.py; appkit genuinely doesn't need them, and keeping this list minimal
# is the whole point of the rule below.

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "appkit.request_id.RequestIDMiddleware",  # before anything that logs
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "tests.backend.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_appkit",
        "USER": "postgres",
        "PASSWORD": "postgres",  # noqa: S105
        "HOST": "localhost",  # overridden to "postgres" by CI env, APP-DESIGN.md §10
        "PORT": "5432",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "appkit.pagination.DefaultPagination",
}

# Optional — every key below already defaults to the value shown if omitted entirely
# (docs/CONTRACT.md §7). Set explicitly here so appkit's own W003 check has something real to
# validate against in later phases.
APPKIT = {
    "CACHE_TIMEOUT": 60,
    "TRUSTED_PROXY_COUNT": 1,
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,
    "SITE_URL": "",
}
