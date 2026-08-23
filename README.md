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
(`INTEGRATION-GUIDE.md` §2 step 5) — not repeated per app after that:

```python
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "appkit.request_id.RequestIDMiddleware",
)  # before anything that logs

REST_FRAMEWORK["EXCEPTION_HANDLER"] = "appkit.exceptions.standard_exception_handler"
```

`config/logging.py`'s `build_logging_config()` imports the request-ID filter from appkit
instead of defining it locally — the `LOGGING` dict's own `filters`/handler wiring is
unchanged, only where `RequestIDFilter` comes from:

```python
# backend/config/logging.py
from appkit.request_id import RequestIDFilter, request_id_var  # was defined locally
```

<!-- STUB — settled in Phase 0: does appkit get an INSTALLED_APPS entry?

     Lean: yes, for three reasons — (1) translations: Django only discovers an app's locale/
     when it's in INSTALLED_APPS; (2) system checks: an AppConfig.ready() that fails loudly if
     appkit is imported but the middleware/EXCEPTION_HANDLER above isn't wired, versus the
     alternative of silently degraded behavior (no request IDs, DRF's default error shape) —
     the strongest argument on its own; (3) future management commands. Cheap to add now,
     breaking to add to every host's settings.py later. INTEGRATION-GUIDE.md §2 step 5's
     wiring block gets an INSTALLED_APPS line added once this is confirmed. -->

<!-- STUB — settled in Phase 0: the full APPKIT = {...} settings dict, if any, and its
     DEFAULTS. -->

## Required `.env` keys

<!-- STUB — settled in Phase 0. Candidates under discussion, neither decided:
     - crypto.py's key: BASE-DESIGN.md §3's tools/-vs-appkit table says field-level crypto
       stays in tools/ permanently, because it wraps the HOST's FERNET_KEY. If appkit ships
       crypto.py anyway, Phase 0 must decide: does it read an APPKIT_FERNET_KEY from settings
       (a new required key for every host), or take a key as a call-time argument (no .env
       key of its own, sidestepping the conflict)? Flagged as an open disagreement with the
       spec, not resolved here — CLAUDE.md's "when this repo and the spec disagree" rule.
     - Any key the files.py / dates.py / net.py modules need (a max-upload-size default, a
       trusted-proxy-count for X-Forwarded-For parsing). -->

## URL mounting

Not applicable — appkit ships no views, no `urls.py`. It's an importable library, not a
mounted app.

## Migrations

Not applicable — appkit ships no models.

## Exports (backend)

<!-- STUB — settled in Phase 0 / Phase 4-5, exact function signatures. Intended module list,
     recorded here so Phase 0 starts from a position: -->

| Module | Provides |
|---|---|
| `appkit.cache` | `build_cache_key`, `cached_call`, `invalidate_namespace`, `namespace_version` |
| `appkit.mixins` | `CachedListMixin` |
| `appkit.exceptions` | `standard_exception_handler` + the ten `code` values (`docs/CONTRACT.md` §1) |
| `appkit.request_id` | `request_id_var`, `RequestIDMiddleware`, `RequestIDFilter` |
| `appkit.permissions` | `IsAppAdmin` |
| `appkit.pagination` | a shared default `pagination_class` |
| `appkit.validation` | a query-param serializer helper, `nh3`-based HTML sanitisation, an ORM lookup-key allowlist |
| `appkit.files` | magic-byte mimetype validation, size limits, extension/mimetype agreement, image checks |
| `appkit.net` | real client IP extraction — trusts only the proxy-appended `X-Forwarded-For` entry, never the client-controlled leftmost value |
| `appkit.text` | truncation |
| `appkit.dates` | Gregorian↔Jalali conversion |
| `appkit.money` | price field sanitisation/formatting |
| `appkit.throttling` | a §1.3 scope-prefix-naming helper |
| `appkit.testing` (pytest plugin) | `api_client`, `auth_client`, `user` fixtures |
| — | `crypto.py` — **open**, see ".env keys" above |

## Exports (frontend)

<!-- STUB — settled in Phase 5, exact types/signatures. Intended surface: -->

| Export | Provides |
|---|---|
| `HttpClient` | The interface a host's concrete client satisfies structurally — appkit never implements one |
| `ApiClientProvider` | The one shared provider a host mounts, carrying `client` + a `basePaths` map |
| `useApiClient(key, defaultBasePath)` | Called from each installed app's own `api/config.ts`, never directly by a host |
| `ApiError` / `ApiErrorEnvelope` / `ApiErrorCode` | Matches the backend envelope exactly — one definition instead of one per app |
| `makeQueryClient()` | A factory (never a module-level singleton) — mirrors the scaffold's own `frontend/lib/query-client.ts` |
| date / price / truncation helpers | Mirror the backend's `dates`/`money`/`text` modules |

<!-- STUB — settled in Phase 0: per-request header injection. Needed for the future auth app
     (Authorization header) without appkit knowing anything about auth. Candidates: an
     interceptor/middleware list on the client contract, or a host-supplied getHeaders()
     callback. Neither decided. -->

## Usage — mounting the shared provider

Every host mounts `ApiClientProvider` **once**, nested under its existing
`QueryClientProvider`, regardless of how many apps are installed — installing a second app
adds a `basePaths` entry to this same provider, it never nests a second provider
(`INTEGRATION-GUIDE.md` §2 step 11):

```tsx
// frontend/app/providers.tsx
import { ApiClientProvider } from "appkit";
import { apiClient } from "@/lib/api-client";

<ApiClientProvider
  client={apiClient}
  basePaths={{
    // ...entries for each installed app's own README-suggested prefix
  }}
>
  {children}
</ApiClientProvider>;
```

`apiClient` is the host's own concrete client (`frontend/lib/api-client.ts`) — appkit owns the
`HttpClient` interface and this provider, never a client implementation. See `CLAUDE.md`'s
"The frontend boundary" for why that split is deliberate, not an oversight.

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

## Test helpers

<!-- STUB — settled once appkit.testing (the pytest plugin) is built. -->

## Suggested Jazzmin icon

Not applicable — appkit registers no models.

## Recommended periodic schedule

Not applicable — appkit ships no `django.tasks`/Celery tasks, deliberately (see above).
