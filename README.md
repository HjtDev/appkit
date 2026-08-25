# appkit

The shared, versioned, dual-package dependency every app package in this ecosystem declares.
It replaces the base-scaffold's per-project `backend/tools/` helpers (cache, mixins,
error-envelope handling, request-ID plumbing) and `frontend/lib/`'s `HttpClient` contract with
one thing every app imports instead of reimplementing (`APP-DESIGN.md` §1.1, `BASE-DESIGN.md`
§3). It is app package #1 — not itself an installable feature, and not something a project adds
to solve a problem on its own. Every other app in the ecosystem depends on it; a host installs
it transitively the first time it installs any app.

Full package contract: `docs/APP-DESIGN.md`. This README follows its §8 structure.

## Installation — backend

A host normally never runs this directly — every app package declares `"appkit>=1.0,<2.0"` in
`[project.dependencies]`, and `uv` resolves appkit **transitively** the first time any app is
installed (`INTEGRATION-GUIDE.md` §2 step 2). Because `appkit` isn't published to a package
index, the host's own `pyproject.toml` has to say where it comes from — add this once, the
first time any app is installed:

```toml
# host backend/pyproject.toml
[tool.uv.sources]
appkit = { git = "https://github.com/HjtDev/appkit.git", tag = "v1.0.0", subdirectory = "backend" }
```

To install directly (e.g. this repo's own `playground/`, or a host without any apps yet):

```bash
uv add "git+https://github.com/HjtDev/appkit.git@v1.0.0#subdirectory=backend"
```

`HjtDev/appkit` is a **private** repo (`APP-DESIGN.md` §1.2) — authenticate with either an SSH
agent (`git+ssh://git@github.com/HjtDev/appkit.git@v1.0.0#subdirectory=backend`) or a token via
`git config --global url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf
"https://github.com/"`. Never pass a token as a Docker `ARG`/`ENV` — it persists in image
history.

## Installation — frontend

Unlike the backend half, the frontend half is installed **explicitly and once per host**, even
though every SDK declares it as a `peerDependency` — npm can't dedupe two different
`github:HjtDev/appkit#vX:frontend` specs into one copy, and two copies means two React
contexts, so `useApiClient` would silently return `null` in half the tree
(`INTEGRATION-GUIDE.md` §2 step 3):

```bash
npm install "github:HjtDev/appkit#v1.0.0:frontend"
```

Already installed at a version satisfying every app's peer range? Skip this step.

## Compatibility

<!-- STUB — the ranges below are the intended targets recorded in CLAUDE.md, pending Phase 0
     confirming the actual `pyproject.toml`/`package.json` ranges against real usage. -->

- Python 3.13+ · Django 5.2–6.x · DRF 3.15+
- React 18+ · `@tanstack/react-query` 5+ (peer dependencies)

## Settings — add to `backend/config/settings.py`

The one-time wiring every fresh host needs the first time *any* app is installed
(`INTEGRATION-GUIDE.md` §2 step 5) — not repeated per app after that. Copy-pasteable as one
block, verbatim from `docs/CONTRACT.md` §8:

```python
INSTALLED_APPS += ["appkit"]

MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "appkit.request_id.RequestIDMiddleware",
)  # before anything that logs

REST_FRAMEWORK["EXCEPTION_HANDLER"] = "appkit.exceptions.standard_exception_handler"
REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] = "appkit.pagination.DefaultPagination"
# No REST_FRAMEWORK["PAGE_SIZE"] needed — DefaultPagination carries its own page_size (25).

# Optional — every key below already defaults to the value shown if omitted entirely.
APPKIT = {
    "CACHE_TIMEOUT": 60,                    # appkit.cache / appkit.mixins default, seconds
    "TRUSTED_PROXY_COUNT": 1,               # appkit.net's trusted X-Forwarded-For hops
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,   # appkit.files' semantic size cap
    "SITE_URL": "",                         # required only if appkit.media is ever called
                                             # with no request in scope (a Celery task, a
                                             # management command) — raises
                                             # ImproperlyConfigured naming this key the first
                                             # time that happens, rather than emitting a
                                             # broken relative URL
}
```

Settled: appkit **does** get an `INSTALLED_APPS` entry — `AppKitConfig.ready()` registers the
system checks named in `docs/CONTRACT.md` §6 (a host that wires the middleware/exception handler
wrong fails loudly at `manage.py check`, rather than silently losing request IDs or DRF's
default error shape).

`config/logging.py`'s `build_logging_config()` imports the request-ID filter from appkit
instead of defining it locally — the `LOGGING` dict's own `filters`/handler wiring is
unchanged, only where `RequestIDFilter` comes from:

```python
# backend/config/logging.py
from appkit.request_id import RequestIDFilter, request_id_var  # was defined locally
```

If `config/logging.py` doesn't exist yet, the minimal shape that makes the import above
actually correlate anything — a handler has to list `"request_id"` in its own `filters`, not
just declare the filter (`docs/CONTRACT.md` §8; `appkit.checks.check_logging_filter`/
`appkit.W005` fires if no handler does):

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": RequestIDFilter}},
    "formatters": {
        "with_request_id": {
            "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "with_request_id",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

### Four things the block above doesn't cover, but a real deployment needs

Found building this package's own `playground/` (`playground/FINDINGS.md`, Phase 6) — none of
these are `APPKIT` settings, so they don't belong in the dict above, but a host that skips them
still passes `manage.py check` cleanly and gets broken behavior anyway:

- **ASGI is required, not optional.** `appkit.request_id.RequestIDMiddleware` is async-only
  (`sync_capable = False`) — a WSGI-only host (plain `runserver`, gunicorn's sync workers)
  cannot run it at all. Serve via `uvicorn config.asgi:application` (or another ASGI server).
- **`SECURE_PROXY_SSL_HEADER` (or `BASE-DESIGN.md` §4.3's `TRUST_PROXY_SSL_HEADER`), if this
  host sits behind a TLS-terminating proxy.** `appkit.media.absolute_url` delegates to Django's
  own `request.build_absolute_uri()`, which only reports `https://` if this is set — appkit has
  no setting of its own for it, but every media URL is `http://` (mixed content) behind TLS
  without it.
- **A real cache backend.** `appkit.mixins.CachedListMixin` works against whatever
  `CACHES["default"]` is configured to — Django's `LocMemCache` default means no caching, and no
  cross-process invalidation, happens at all, silently.
- **`REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]` must include `ScopedRateThrottle`** for
  `appkit.throttling.throttle_scope()` (and `appkit.checks`' `appkit.W004`) to have any runtime
  effect — DRF only enforces a `throttle_scope` class attribute when a throttle class that reads
  it is actually installed; a view can pass `W004` and still be completely unthrottled.

## Testing — pytest fixtures (opt-in)

appkit ships a pytest plugin, `appkit.testing`, providing `appkit_api_client`, `appkit_user`,
`appkit_admin_user`, `appkit_auth_client`, `appkit_admin_client`, `appkit_frozen_request_id`,
`appkit_clear_cache`, and the `appkit_assert_error_envelope(response, *, code, status)` helper
(`docs/CONTRACT.md` §2.17).

**Every name carries an `appkit_` prefix** — `APP-DESIGN.md` §1.3's namespacing rule applied to
pytest's fixture registry, which is exactly the kind of shared, flat namespace that rule exists
for. This isn't theoretical: pytest-django ships its own built-in fixtures literally named
`admin_user` and `admin_client`, and (verified directly) pytest-django's versions win that name
collision **silently** wherever `db`/`django_db` is in play — a bare `admin_client` fixture
parameter returns pytest-django's plain Django `Client`, never appkit's DRF `APIClient`, with no
warning. Prefixing every name this plugin exposes — not just the two that happen to collide
today — is what keeps a future pytest-django release, another plugin, or a consuming app's own
`conftest.py` from silently shadowing the rest.

It is **opt-in, not automatic** — no `pytest11` entry point is registered, on purpose: appkit is
installed transitively by every host, so auto-loading would inject these fixtures into every
consuming app's test namespace whether or not it asked for them. Wire it up explicitly in the
consuming app's own `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-p appkit.testing ..."
```

An app package doing this gets `appkit_api_client`/`appkit_auth_client`/`appkit_user` for free
instead of hand-rolling a slightly different version of each in its own `conftest.py`.

## Required `.env` keys

**None.** Settled: `appkit.crypto.Cipher` takes its key as a constructor argument, never from
Django settings or an environment variable — `docs/CONTRACT.md` §3. Field-level crypto wrapping
a host's own `FERNET_KEY` stays in the host's `tools/crypto.py` permanently; an app declaring
`appkit[crypto]` builds a `Cipher` from its own documented `.env` key instead. Every
configurable value the modules below read (`MAX_UPLOAD_BYTES`, `TRUSTED_PROXY_COUNT`,
`SITE_URL`, `CACHE_TIMEOUT`) is an optional `APPKIT` **settings** key, not an `.env` key — see
"Settings" above.

## URL mounting

Not applicable — appkit ships no views, no `urls.py`. It's an importable library, not a
mounted app.

## Migrations

Not applicable — appkit ships no models.

## Exports (backend)

Every module below is complete as of `docs/CONTRACT.md` §2 — exact signatures there, `README.md`
lists what each provides rather than repeating them verbatim.

| Module | Provides |
|---|---|
| `appkit.cache` | `build_cache_key`, `cached_call`, `invalidate_namespace`, `namespace_version` |
| `appkit.mixins` | `CachedListMixin` |
| `appkit.exceptions` | `standard_exception_handler` + the ten `code` values (`docs/CONTRACT.md` §1) |
| `appkit.request_id` | `request_id_var`, `RequestIDMiddleware`, `RequestIDFilter` |
| `appkit.permissions` | `IsAppAdmin`, `IsObjectOwner` (the IDOR-case permission, `owner_field`-configurable) |
| `appkit.pagination` | `DefaultPagination` — `page_size=25`, `max_page_size=100` |
| `appkit.validation` | `validate_query_params`, `sanitize_html`/`strip_html` (`nh3`-based), `ALLOWED_LOOKUPS`/`validate_lookup`/`safe_filter_kwargs` (an ORM lookup-key allowlist — `regex`/`iregex` excluded, a ReDoS vector) |
| `appkit.files` | `ImageInfo`, `detect_mimetype`, `validate_upload`, `validate_image` — magic-byte mimetype validation, size limits, hardcoded extension/mimetype agreement table, decompression-bomb-aware image dimension checks. `validate_image`'s raster-format path requires the `images` extra |
| `appkit.net` | `client_ip` — trusts only the proxy-appended `X-Forwarded-For` entry (`APPKIT["TRUSTED_PROXY_COUNT"]`-th from the right), never the client-controlled leftmost value |
| `appkit.media` | `file_url`, `absolute_url` — media URL absolutisation; this, not `appkit.urls`, is where a media-URL helper lives, since appkit exposes no `urlpatterns` at all |
| `appkit.text` | `truncate`, `to_english_digits`, `to_persian_digits` — codepoint-aware, matches the frontend half's `truncate` exactly |
| `appkit.dates` | `to_jalali`, `from_jalali`, `format_jalali`, `parse_jalali` — Gregorian↔Jalali conversion; no third-party type in any signature |
| `appkit.money` | `parse_amount`, `format_amount` — fixed ASCII `,` grouping, never locale-dependent |
| `appkit.throttling` | `throttle_scope` — a §1.3 scope-prefix-naming helper |
| `appkit.conf` | `get_setting`, `UNSET`, `DEFAULTS` (internal-but-stable, not re-exported from top-level `appkit`) |
| `appkit.crypto` | `Cipher`, `generate_key` — Fernet encryption taking its key at call time. Requires the `crypto` extra; resolved in `docs/CONTRACT.md` §3: appkit reads no `.env`/settings key of its own, ever |
| `appkit.testing` (pytest plugin, opt-in — see "Testing" above) | `appkit_api_client`, `appkit_user`, `appkit_admin_user`, `appkit_auth_client`, `appkit_admin_client`, `appkit_frozen_request_id`, `appkit_clear_cache`, `appkit_assert_error_envelope`. Every name is `appkit_`-prefixed on purpose — pytest-django ships its own built-in `admin_user`/`admin_client` fixtures, and (verified directly) pytest-django's win that exact name collision silently; the prefix is what keeps this plugin's fixtures from ever landing in that situation |

## Exports (frontend)

Full signatures, failure paths, and reasoning: `docs/CONTRACT.md` §14–§23 (frontend contract,
Session 2). Nothing beyond this table is exported from `src/index.ts`.

| Export | Provides |
|---|---|
| `HttpClient` | The five-method interface (`get`/`post`/`put`/`patch`/`delete`) a host's concrete client satisfies structurally — appkit never implements one |
| `ApiClientProvider` | The one shared provider a host mounts, carrying `client`, an optional `headerSources` array, and a `basePaths` map |
| `useApiClient(key, defaultBasePath)` | Called from each installed app's own `api/config.ts`, never directly by a host. Both arguments required — a missing `basePaths` entry falls back to the app's own default, never to `""`/`/` |
| `HeaderSource` | `() => HeadersInit \| Promise<HeadersInit>` — see "Header injection" below |
| `ApiError` / `isApiError` | Matches the backend envelope exactly — one definition instead of one per app. `isApiError` is a brand check, not `instanceof`, so it survives a duplicate-copy install |
| `isApiErrorEnvelope` / `apiErrorFromEnvelope` | Pure envelope-parsing helpers — validate/construct from already-fetched data, never touch `fetch`/`Response` themselves |
| `ApiErrorCode` / `ClientErrorCode` / `ApiErrorEnvelope` | Types — the ten backend codes plus this client's own `"unknown_error"`, kept as a separate type so the ten-member union stays a true mirror |
| `makeQueryClient()` | A factory (never a module-level singleton) — mirrors the scaffold's own `frontend/lib/query-client.ts` |
| `truncate` / `toEnglishDigits` / `toPersianDigits` | Mirror the backend's `appkit.text` — codepoint-aware, not UTF-16-unit-aware |
| `parseAmount` / `formatAmount` | Mirror `appkit.money` — fixed `,` separator, never locale-dependent |
| `toJalali` / `fromJalali` / `formatJalali` / `parseJalali` / `calendarDateIn` | Mirror `appkit.dates`. Date-only by default; `calendarDateIn(instant, timeZone)` is the explicit, no-default bridge from an instant to a calendar date |
| `mediaUrl(value, baseUrl)` | Mirrors `appkit.media` — takes its base as an argument, never reads `NEXT_PUBLIC_API_URL` itself |

**Not exported, on purpose:** a concrete client/`apiClient` singleton, `getApiBaseUrl`, a
`QueryClient` singleton, the `ApiClientContext` object itself, any manager or config-hook shape,
any UI component, any storage helper. Reasoning for each: `docs/CONTRACT.md` §21.

## Header injection

Settled in Phase 0 (`docs/CONTRACT.md` §16): `ApiClientProvider` takes an optional
`headerSources?: ReadonlyArray<HeaderSource>` prop. Sources run left-to-right, then the call's
own `init.headers` last — later always wins, header names compared case-insensitively so
`authorization`/`Authorization` from two sources collapse into one. A source that throws or
rejects **fails the request**, naming which source failed, rather than silently shipping the
request without that header. This is how the future JWT app attaches `Authorization` without
appkit knowing anything about auth:

> appkit never reads, stores, refreshes, or inspects a token. It invokes opaque callbacks the
> host supplies and merges their output into request headers.

Token refresh / retry-on-401 is explicitly **not** appkit's job — see "What appkit deliberately
does not provide" below.

## Usage — mounting the shared provider

Every host mounts `ApiClientProvider` **once**, nested under its existing
`QueryClientProvider`, regardless of how many apps are installed — installing a second app
adds a `basePaths` entry to this same provider, it never nests a second provider
(`INTEGRATION-GUIDE.md` §2 step 11):

```tsx
// frontend/app/providers.tsx
"use client";

import { useState, useMemo } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ApiClientProvider, makeQueryClient } from "appkit";
import { apiClient } from "@/lib/api-client";
import { getAuthHeaders } from "@/lib/auth"; // host's own — appkit knows nothing about it

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());
  const headerSources = useMemo(() => [getAuthHeaders], []); // stable reference — see below

  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider
        client={apiClient}
        headerSources={headerSources}
        basePaths={{
          // ...entries for each installed app's own README-suggested prefix
        }}
      >
        {children}
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
```

`apiClient` is the host's own concrete client (`frontend/lib/api-client.ts`) — appkit owns the
`HttpClient` interface and this provider, never a client implementation. See `CLAUDE.md`'s
"The frontend boundary" for why that split is deliberate, not an oversight.

`headerSources` must be a **stable reference** (built with `useMemo`/module scope, never an
inline array literal) — the decorated client is memoised on it, and a new array identity every
render rebuilds every installed app's own manager on every render (`docs/CONTRACT.md` §15).

## What appkit deliberately does not provide

- **No Celery / `django.tasks`.** A shared dependency that drags in a task runner forces every
  consuming app *and* host to care about it. If a future shared helper genuinely needs async
  work, that's a design discussion, not a default (`CLAUDE-CODE-GUIDE-APP.md` §1.3).
- **No models, no migrations, no admin.**
- **No UI components.** The frontend half is an SDK contract — hooks and a fetcher interface —
  not a component library. A `share()` helper or anything else UI-shaped belongs in a separate
  package if it's ever wanted.
- **No parallel validation framework.** DRF serializers do the work; appkit adds a thin helper
  for validating `request.query_params` through a serializer, not a new declaration system.
- **No generic "XSS/SQL-injection checker."** The ORM already prevents SQL injection;
  string-scanning for `<script>` is a blocklist that provides false confidence. The two real
  pieces underneath are in scope instead: HTML sanitisation and an ORM lookup-key allowlist
  (see Exports above).
- **No client implementation on the frontend half — interface and shared provider only.**
  appkit owns `HttpClient` and `ApiClientProvider`/`useApiClient`; the host always constructs
  and injects the real client (`NEXT_PUBLIC_API_URL`, CSRF, credentials mode — all host
  configuration). See "The frontend boundary" in `CLAUDE.md`.
- **No retry-on-401 / token refresh**, anywhere in `headerSources` or the client appkit
  decorates. A real refresh loop needs the refresh endpoint, infinite-loop protection, and
  concurrent-refresh dedupe — all auth-specific knowledge appkit must never have. That's the
  host's concrete client's job; the future JWT app's own README documents it there
  (`docs/CONTRACT.md` §J).

## Known caveats inherited from the base-scaffold helpers this replaces

Flagged here rather than silently fixed, since the base-scaffold's `backend/tools/` module is
the *source* appkit's own versions are built from, and this repo has no standing to edit it:

- `standard_exception_handler`'s fallback `code` (`"error"`, for an `APIException` outside the
  eight specifically-mapped types) was undercounted here as outside "the nine documented
  codes". **Resolved in `docs/CONTRACT.md` §1: the set is ten, not nine** — `"error"` is now a
  documented member in its own right, with the HTTP status authoritative for it. See that
  section for the full reasoning and the exhaustive `ApiErrorCode` this implies for the
  frontend half.
- `invalidate_namespace` (get-then-increment) isn't atomic — a cache eviction between the two
  calls raises. Low-probability, but appkit's blast radius means it now affects every app.
- `cached_call` can't distinguish "cache miss" from "legitimately cached `None`" — documented
  behavior, not a bug, but worth restating here since this is now shared infrastructure.

## Known caveat — Django's own request logging never carries the request ID

Found via `playground/` (`playground/FINDINGS.md`), root-caused against Django's own source
(`django/core/handlers/base.py`), not inherited from base-scaffold: Django's built-in
`django.request` logger — the one that auto-logs every 4xx/5xx response — will **never** carry
`request_id`, no matter how `MIDDLEWARE` is ordered. `BaseHandler.get_response_async` awaits the
entire middleware chain (including `RequestIDMiddleware`) to completion *before* it calls
`log_response()` for a 4xx/5xx response — by that point `RequestIDMiddleware`'s own
`finally: request_id_var.reset(token)` has already run. This isn't fixable inside appkit without
reintroducing the exact ID-bleed-under-concurrency bug that `finally: reset()` exists to prevent.

Correlation still works everywhere it matters: the response's own `X-Request-ID` header, any
logger your *own* view/handler code calls during request handling (e.g.
`standard_exception_handler`'s `logger.exception(...)`), and `appkit.testing`'s
`appkit_frozen_request_id` fixture all see the correct ID. Only Django's automatic, built-in
4xx/5xx logging does not.

## Test helpers

See "Testing — pytest fixtures (opt-in)" above for the full fixture/helper list and the
`appkit_`-prefix naming rationale. Two behaviors worth calling out beyond that list:

- `appkit_user`/`appkit_admin_user` build through `get_user_model().USERNAME_FIELD`
  **reflectively** — they work against a custom, non-`username`-keyed user model without any
  extra configuration.
- `appkit_clear_cache` is deliberately **not** `autouse` — under `pytest -n auto` against a
  shared cache backend, an autouse cache-clear would clear another xdist worker's in-flight
  data too.

## Suggested Jazzmin icon

Not applicable — appkit registers no models.

## Recommended periodic schedule

Not applicable — appkit ships no `django.tasks`/Celery tasks, deliberately (see above).
