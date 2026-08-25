"""Playground settings — Phase 6, docs/APP-DESIGN.md §11.2.

This file is deliberately split into two halves, and the split is load-bearing for what this
playground is trying to prove:

  1. "HOST BASELINE" — everything a fresh base-scaffold host already has *before* any app
     package is installed: SECRET_KEY, ALLOWED_HOSTS, a full MIDDLEWARE list, Postgres, Redis,
     media settings, and the SECURE_PROXY_SSL_HEADER block, quoted verbatim from
     docs/BASE-DESIGN.md §4.3 (lines 399-419) — that file describes the BASE-SCAFFOLD's own
     settings.py, not appkit's, and appkit's README never mentions it (see playground/FINDINGS.md
     finding #3: whether that omission is real).

  2. "APPKIT WIRING — VERBATIM FROM README.md" — a byte-for-byte copy-paste of the three code
     fences in /home/hjtdev/Projects/appkit/README.md, lines 66-73, 79-82, 89-107, IN README
     ORDER. Nothing was added, reordered, or "fixed" inside the banner. If the project doesn't
     boot with only what's between the banners, that gap is recorded in FINDINGS.md as a README
     defect, not silently patched here.

Do not edit anything between "APPKIT WIRING" START/END without also updating FINDINGS.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================================
# HOST BASELINE — what a fresh base-scaffold host already has before any app is installed.
# ============================================================================================

SECRET_KEY = config("SECRET_KEY", default="playground-not-a-secret")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="localhost,127.0.0.1,backend", cast=lambda v: v.split(",")
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "demo",
    # ---- APPKIT WIRING adds "appkit" below, per README.md ----
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # ---- APPKIT WIRING inserts RequestIDMiddleware here, right after SecurityMiddleware ----
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
# No WSGI_APPLICATION — appkit.request_id.RequestIDMiddleware is async-only
# (sync_capable = False), so this playground must run under uvicorn/ASGI, never runserver's
# WSGI path or a WSGI app server. See playground/FINDINGS.md for what a WSGI boot actually does.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="playground"),
        "USER": config("POSTGRES_USER", default="playground"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="playground"),
        "HOST": config("POSTGRES_HOST", default="db"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# appkit.mixins.CachedListMixin needs a real cache backend to prove anything — README's
# Settings section never says a host needs one. Tracked as a finding.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

AUTH_USER_MODEL = "auth.User"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

CSRF_COOKIE_HTTPONLY = False  # must stay JS-readable — the frontend sends it as a header
SESSION_COOKIE_HTTPONLY = True

# ---- docs/BASE-DESIGN.md §4.3, lines 399-419, quoted verbatim ----
# Env-driven, defaulting to "secure unless DEBUG says otherwise" — SECURE_HSTS_SECONDS below
# is the one exception that does NOT inherit that default; see its own comment for why.
_SECURE_DEFAULT = not DEBUG
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)  # nginx handles it
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=_SECURE_DEFAULT, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=_SECURE_DEFAULT, cast=bool)
# Defaults to 0 in every environment, including prod: a year of HSTS is effectively
# irreversible for the domain and every subdomain, so turning it on is a deliberate,
# explicit act (backend/.env.prod.example sets 31536000), never an inherited default.
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
# Only trust X-Forwarded-Proto when we know a proxy sits in front — trusting it
# unconditionally is a spoofing vector the moment the container is reachable directly.
TRUST_PROXY_SSL_HEADER = config("TRUST_PROXY_SSL_HEADER", default=True, cast=bool)
if TRUST_PROXY_SSL_HEADER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
# ---- end docs/BASE-DESIGN.md §4.3 verbatim block ----

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:8080,https://localhost:8443,http://localhost:3000",
    cast=lambda v: v.split(","),
)

REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        # This playground's OWN throttle rate, registered per docs/APP-DESIGN.md §1.3's
        # namespacing convention (throttle_scope("demo", "list") -> "demo_list"). Not part of
        # appkit's wiring — appkit ships zero throttle scopes of its own.
        "demo_list": "5/min",
    },
}

# ============================================================================================
# APPKIT WIRING — VERBATIM FROM README.md (backend/README.md, this repo, lines 66-107)
# Do not reorder, merge, or "improve" anything between these banners. See module docstring.
# ============================================================================================

# ---- README.md:66-73 ----
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "appkit.request_id.RequestIDMiddleware",
)  # before anything that logs

REST_FRAMEWORK["EXCEPTION_HANDLER"] = "appkit.exceptions.standard_exception_handler"

# ---- README.md:79-82 ----
# backend/config/logging.py imports the request-ID filter from appkit instead of defining it
# locally — see config/logging.py, which contains the actual "from appkit.request_id import
# RequestIDFilter, request_id_var" line. Imported here only to build the LOGGING dict below.
from config.logging import build_logging_config  # noqa: E402

# ---- README.md:89-107 ----
INSTALLED_APPS += ["appkit"]

REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] = "appkit.pagination.DefaultPagination"
# No REST_FRAMEWORK["PAGE_SIZE"] needed — DefaultPagination carries its own page_size (25).

# Optional — every key below already defaults to the value shown if omitted entirely.
APPKIT = {
    "CACHE_TIMEOUT": 60,  # appkit.cache / appkit.mixins default, seconds
    "TRUSTED_PROXY_COUNT": 1,  # appkit.net's trusted X-Forwarded-For hops
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,  # appkit.files' semantic size cap
    "SITE_URL": "",  # required only if appkit.media is ever called
    # with no request in scope (a Celery task, a
    # management command) — raises
    # ImproperlyConfigured naming this key the first
    # time that happens, rather than emitting a
    # broken relative URL
}

# ============================================================================================
# END APPKIT WIRING
# ============================================================================================

# LOGGING is the playground's own — README's "Settings" section supplies only the RequestIDFilter
# import (config/logging.py), not a full LOGGING dict. This one exists so
# appkit.checks.check_logging_filter (appkit.W005) has something real to validate and so
# request-ID correlation is actually observable in `docker compose logs backend`.
LOGGING = build_logging_config(debug=DEBUG)

# Playground-only: appkit.crypto.Cipher takes its key at call time, never from settings
# (docs/CONTRACT.md §3) — this key belongs to `demo`, not to appkit, exactly as the README's
# ".env keys" section describes for a real consuming app.
DEMO_FERNET_KEY = config("DEMO_FERNET_KEY", default="")
