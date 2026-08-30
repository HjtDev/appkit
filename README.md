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

Published to the **public PyPI registry** as **`hjtdev-appkit`** (not the bare `appkit` name —
already taken by an unrelated package, same situation as `@hjtdev/appkit` on npm below). The
*import* name is unaffected — `import appkit` — only the installable/requirement name is
prefixed, exactly like `python-dateutil` ships `import dateutil`.

A host normally never runs this directly — every app package declares
`"hjtdev-appkit>=2.0,<3.0"` in `[project.dependencies]`, and `uv`/`pip` resolve it **transitively**
the first time any app is installed (`INTEGRATION-GUIDE.md` §2 step 2). To install directly (e.g.
this repo's own `playground/`, or a host without any apps yet):

```bash
uv add "hjtdev-appkit>=2.0,<3.0"
# or: pip install "hjtdev-appkit>=2.0,<3.0"
```

**Pinning an unreleased commit instead of a tagged version** (rare — normal installs use the line
above) still works via the git+subdirectory form, since `uv`/`pip` correctly implement Git's
`#subdirectory=` fragment:

```toml
# host backend/pyproject.toml
[tool.uv.sources]
hjtdev-appkit = { git = "https://github.com/HjtDev/appkit.git", tag = "v2.0.0", subdirectory = "backend" }
```

`HjtDev/appkit` is a **public** repo — no authentication needed for either half.

**Host action if upgrading from `<2.0`:** the requirement name changed from `appkit` to
`hjtdev-appkit` (see `CHANGELOG.md`'s `[2.0.0]` entry) — `uv remove appkit && uv add
"hjtdev-appkit>=2.0,<3.0"`, and drop any `[tool.uv.sources]` entry for the old git install if one
was added. No import changes anywhere.

### Extras

Two optional dependency groups, installed with `hjtdev-appkit[extra]`. Omitted entirely, appkit's
own hard dependencies (`django`, `djangorestframework`, `nh3`, `puremagic`, `jdatetime` — see
"Compatibility" below) already cover the whole non-extra surface:

- **`crypto`** — pulls in `cryptography`, enabling `appkit.crypto.Cipher`/`generate_key`. Needed
  only by an app encrypting a field with its own key (never appkit's own — `docs/CONTRACT.md`
  §3, and "Required `.env` keys" below).
- **`images`** — pulls in `Pillow`, enabling `appkit.files.validate_image`'s raster-format
  dimension checks. Needed only by an app that accepts image uploads.
- Compose both as `hjtdev-appkit[crypto,images]` when an app needs both.

Calling the corresponding function with the extra not installed raises `ImportError` with an
actionable message (`Install with: uv add "hjtdev-appkit[crypto]"`) rather than a bare traceback
three frames deep — confirmed live against a real bare-install container
(`playground/FINDINGS.md` §10.1).

## Installation — frontend

Unlike the backend half, the frontend half is published to the **public npm registry** as
`@hjtdev/appkit` (not the bare `appkit` name — already taken by an unrelated package), and is
installed **explicitly and once per host**, even though every SDK declares it as a
`peerDependency` (`INTEGRATION-GUIDE.md` §2 step 3):

```bash
npm install @hjtdev/appkit
```

Already installed at a version satisfying every app's peer range? Skip this step. After
installing every app, `npm ls @hjtdev/appkit` should show exactly **one** resolved copy — two
copies means two separate React module instances, and `useApiClient` would silently return
`null` in half the tree.

**Why both halves ended up on a registry.** The backend half could, in principle, stay a plain
git dependency — `uv`/`pip` correctly implement Git's `#subdirectory=` fragment, unlike npm (see
below) — but that still left every host writing its own `[tool.uv.sources]` block by hand, since
`uv` never reads a transitive dependency's *own* sources table. Publishing to PyPI removes that
step entirely: a plain version range resolves like any other dependency. The frontend half has no
working git-install alternative at all: `github:HjtDev/appkit#vX:frontend` silently drops both the
tag and the subdirectory (npm parses `:frontend` as junk and falls back to the default branch),
and the documented-looking `::path:frontend` form only changes which `package.json` npm reads
metadata from — it still packs and installs the **entire repository root**, `backend/` and all,
so `import "..."` fails with `ERR_PACKAGE_PATH_NOT_EXPORTED`. Neither is a bug in this repo's
layout; it's the ceiling of what npm's git installer supports. The registry install is the only
supported way to install the frontend half, and now the simplest way to install the backend half
too.

## Compatibility

Verified directly against `backend/pyproject.toml` and `frontend/package.json`, not carried over
from CLAUDE.md's original targets unread:

- **Python** `>=3.13` · **Django** `>=5.2,<7.0` · **DRF** `>=3.15,<4.0` — wide ranges, never
  exact pins (`CLAUDE.md`'s dependency-range rule). appkit is the most widely shared dependency
  in the ecosystem, so an exact pin here would force every host and every other app package to
  match it.
- **React** `>=18` · **`@tanstack/react-query`** `>=5` — peer dependencies only. The frontend
  half has **zero runtime dependencies of its own**.
- appkit's own hard backend dependencies, inherited transitively by every host the first time
  any app package is installed: `django>=5.2,<7.0`, `djangorestframework>=3.15,<4.0`,
  `nh3>=0.2,<1.0` (HTML sanitisation — a hard dependency, not an extra, since a skippable
  sanitiser is a stored-XSS bug waiting to happen), `puremagic>=2,<3` (magic-byte mimetype
  sniffing), `jdatetime>=5,<7` (Gregorian↔Jalali conversion; pulls in `jalali-core` transitively).

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

## System checks

Registered from `AppKitConfig.ready()` — the reason appkit needs a real `INSTALLED_APPS` entry,
not just importability. Eight IDs, seven functions, all reachable via `manage.py check`. This is
appkit's substitute for the "signals emitted" section every other app package has: the contract
about what appkit will tell a host, and how to diagnose a misconfiguration without reading
appkit's source.

| ID | Severity | Catches | Fix |
|---|---|---|---|
| `appkit.E001` | Error | `RequestIDMiddleware` absent from `MIDDLEWARE` | Add it right after `SecurityMiddleware` — see "Settings" above |
| `appkit.E002` | Error | `EXCEPTION_HANDLER` unset, or still DRF's own default | Set `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "appkit.exceptions.standard_exception_handler"` |
| `appkit.W001` | Warning | `EXCEPTION_HANDLER` set to neither DRF's default nor appkit's | Confirm it's deliberate (a handler wrapping appkit's own); silence via `SILENCED_SYSTEM_CHECKS` if so, otherwise fix it |
| `appkit.W002` | Warning | `RequestIDMiddleware` present but ordered before `SecurityMiddleware` | Move it to right after `SecurityMiddleware` in `MIDDLEWARE` |
| `appkit.W003` | Warning | `APPKIT` dict has a key not in `appkit.conf.DEFAULTS` | Fix the typo — an unrecognised key is silently ignored, its value never read |
| `appkit.W004` | Warning | A view reachable via `ROOT_URLCONF` declares a `throttle_scope` with no matching `DEFAULT_THROTTLE_RATES` entry | Add the rate, or fix the typo'd scope — DRF only raises for this at request time, per request, so it can otherwise ship silently |
| `appkit.W005` | Warning | `LOGGING` is configured but no handler references a filter resolving to `RequestIDFilter` | Add `"request_id": {"()": "appkit.request_id.RequestIDFilter"}` to `LOGGING["filters"]`, and `"request_id"` to the relevant handler's `filters` list |
| `appkit.W006` | Warning | `REST_FRAMEWORK["NUM_PROXIES"]` disagrees with `APPKIT["TRUSTED_PROXY_COUNT"]`, or is unset while a `SimpleRateThrottle` subclass (`ScopedRateThrottle`, `AnonRateThrottle`, `UserRateThrottle`, or a host's own) is configured, globally or on any view | Set `REST_FRAMEWORK["NUM_PROXIES"]` to the same value as `APPKIT["TRUSTED_PROXY_COUNT"]` — see "`client_ip()` — the trusted-hop algorithm" below; DRF's `get_ident()` does its own `X-Forwarded-For` parsing appkit cannot inject into, so the two settings drifting apart makes the throttle bucket spoofable even though `client_ip()` itself is correct |

Every check is defensive by construction — a system check that raises breaks `manage.py`
outright, including the very commands someone would use to fix what it's complaining about, so
each function treats a malformed or partially-configured host structure as "nothing to report,"
never a crash. One stated limit: every check above only runs if `INSTALLED_APPS` lists
`"appkit"` in the first place — Django never calls `ready()` on an app that isn't listed, and
nothing inside appkit can self-detect that omission.

## The error envelope

Every error response `standard_exception_handler` produces has this shape, verbatim:

```json
{
  "error": {
    "code": "validation_error",
    "message": "...",
    "details": {},
    "request_id": "..."
  }
}
```

`details` is always present (`{}` when nothing is field-level). `request_id` is the same
correlation ID `appkit.request_id.request_id_var` carries. Headers DRF already sets
(`Retry-After` on `throttled`, `WWW-Authenticate` on `not_authenticated`/
`authentication_failed`) are untouched — the handler only ever rewrites `response.data`.

Ten `code` values, in this exact order (pinned against `tests/fixtures/error-codes.json`, which
both halves are independently verified against rather than against each other directly):

`validation_error`, `parse_error`, `not_authenticated`, `authentication_failed`,
`permission_denied`, `not_found`, `method_not_allowed`, `throttled`, `server_error`, **`error`**.

**`"error"` is the documented catch-all**, not an omission — it covers any `APIException` DRF
resolved to a response that isn't one of the other nine specific types. For `"error"`, the HTTP
status is authoritative, the code is not. New specific codes may be carved out of `"error"` in a
future **minor** version — the one place this ten-member set can grow without a major bump (see
"Semver triggers" in `CLAUDE.md`).

## Testing — pytest fixtures (opt-in)

appkit ships a pytest plugin, `appkit.testing`, providing `appkit_api_client`, `appkit_user`,
`appkit_admin_user`, `appkit_auth_client`, `appkit_admin_client`, `appkit_frozen_request_id`,
`appkit_clear_cache`, and the `appkit_assert_error_envelope(response, *, code, status)` helper
(`docs/CONTRACT.md` §2.17).

**Every name carries an `appkit_` prefix** — `APP-DESIGN.md` §1.2's namespacing rule applied to
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

**Why two of `appkit.testing`'s own imports are deferred into function bodies, not module
scope** (previously only in the source comments of `backend/src/appkit/testing.py`):

- `rest_framework.test.APIRequestFactory` reads DRF's `api_settings` at **class-definition**
  time. A `-p` plugin named in `addopts` is imported during pytest's early
  `consider_preparse` phase — ahead of pytest-django's own settings setup — so a module-scope
  import here would raise `ImproperlyConfigured` the moment any consumer wires up
  `-p appkit.testing`, before Django settings exist at all. Deferred into
  `appkit_api_client()` instead.
- A module-scope `appkit.request_id` import here lands **before** pytest-cov's tracer attaches
  (for the same early-loading reason), and coverage.py then permanently reports every line that
  module's import executes as "previously imported but not measured" — verified directly against
  this exact codebase: `request_id.py`'s own measured coverage drops from 100% to 42% the moment
  this import moves to module scope, in appkit's own suite, with no change in what actually ran.
  This is why appkit's own `pyproject.toml` deliberately does **not** dogfood
  `-p appkit.testing` in its own `addopts` — doing so would reproduce both drops in appkit's own
  coverage numbers, not just a downstream consumer's.

### Two-leg strategy: gate run vs. bare-install check

Every test run happens twice — proving the core stands alone, and proving both extras work when
installed:

```bash
make test        # gate: authoritative, >=95% coverage, both extras installed, against Postgres
make test-bare    # bare-install check: neither extra, -m "not requires_extra", no coverage gate
```

Any test exercising `crypto`/`images`-gated behavior carries the `requires_extra` marker, so the
bare leg deselects it rather than failing on a missing optional dependency.

### The golden-fixture rule

Any behaviour that must agree across the two halves — the ten error codes, Jalali round-trips,
money formatting, truncation — is verified by **one fixture file both suites load**
(`tests/fixtures/*.json`), never by two independently hand-written test files that happen to
agree today. `appkit.exceptions.ERROR_CODES` and the frontend's `ApiErrorCode` union are each
asserted against `tests/fixtures/error-codes.json` directly, not against each other — a
divergence between the halves is impossible to introduce by editing only one side's tests. See
`tests/fixtures/README.md` for the full fixture list.

## Required `.env` keys

**None.** Settled: `appkit.crypto.Cipher` takes its key as a constructor argument, never from
Django settings or an environment variable — `docs/CONTRACT.md` §3. Field-level crypto wrapping
a host's own `FERNET_KEY` stays in the host's `tools/crypto.py` permanently; an app declaring
`hjtdev-appkit[crypto]` builds a `Cipher` from its own documented `.env` key instead. Every
configurable value the modules below read (`MAX_UPLOAD_BYTES`, `TRUSTED_PROXY_COUNT`,
`SITE_URL`, `CACHE_TIMEOUT`) is an optional `APPKIT` **settings** key, not an `.env` key — see
"Settings" above.

## URL mounting

Not applicable — appkit ships no views, no `urls.py`. It's an importable library, not a
mounted app.

## Migrations

Not applicable — appkit ships no models.

## Services and signals

Not applicable, and deliberately so. Other app packages in this ecosystem follow a three-file
shape (`models.py`/`services.py`/`signals.py`); appkit's public surface is its importable
modules instead (`appkit.cache`, `appkit.mixins`, etc.) — there is no `services.py` to hold
business logic and no `signals.py` to emit, since appkit has no models to signal about.

## Factories

Not applicable — appkit ships no models, so `APP-DESIGN.md`'s `factories.py` test-surface
convention (factory-boy) does not apply here.

## Exports (backend)

Every module below is complete as of `docs/CONTRACT.md` §2 — exact signatures there, `README.md`
lists what each provides rather than repeating them verbatim.

| Module | Provides |
|---|---|
| `appkit.cache` | `build_cache_key(namespace, *parts) -> str`, `cached_call(key, timeout, producer) -> T`, `cache_endpoint(*, namespace, timeout=UNSET, per_user=True, vary_headers=(), cache_statuses=(200,))` — decorator wrapping a DRF view method (`list`/`retrieve`), `invalidate_namespace(namespace) -> int`, `namespace_version(namespace) -> int` |
| `appkit.mixins` | `CachedListMixin` — `cache_namespace: str` (required, no default — raises `ImproperlyConfigured` if left empty), `cache_timeout: int \| UNSET` |
| `appkit.exceptions` | `standard_exception_handler(exc, context) -> Response \| None`, `ERROR_CODES: tuple[str, ...]` — the ten `code` values, in order (see "The error envelope" above) |
| `appkit.request_id` | `request_id_var: ContextVar[str]`, `RequestIDMiddleware`, `RequestIDFilter` |
| `appkit.permissions` | `IsAppAdmin`, `IsObjectOwner` (`owner_field: str = "user"` — the IDOR-case permission) |
| `appkit.pagination` | `DefaultPagination` — `page_size=25`, `max_page_size=100` |
| `appkit.validation` | `validate_query_params(serializer_class, params) -> S`, `sanitize_html(value, *, allowed_tags=None) -> str`, `strip_html(value) -> str` (`nh3`-based), `ALLOWED_LOOKUPS: frozenset[str]`, `validate_lookup(lookup) -> bool`, `safe_filter_kwargs(params, allowed_fields, *, allow_relations=False) -> dict` (an ORM lookup-key allowlist — `regex`/`iregex` excluded, a ReDoS vector) |
| `appkit.files` | `ImageInfo` (`width`, `height`, `format`), `detect_mimetype(data: bytes) -> str`, `validate_upload(file, *, allowed_mimetypes, max_bytes=UNSET) -> None`, `validate_image(file, *, max_bytes=UNSET, max_dimensions=None, allow_svg=False) -> ImageInfo` — magic-byte mimetype validation, size limits, a hardcoded extension/mimetype agreement table, decompression-bomb-aware image dimension checks. `validate_image`'s raster-format path requires the `images` extra |
| `appkit.net` | `client_ip(request) -> str` — trusts only the proxy-appended `X-Forwarded-For` entry (`APPKIT["TRUSTED_PROXY_COUNT"]`-th from the right), never the client-controlled leftmost value |
| `appkit.media` | `file_url(value, *, request=None) -> str \| None`, `absolute_url(url, *, request=None) -> str \| None` — media URL absolutisation; this, not `appkit.urls`, is where a media-URL helper lives, since appkit exposes no `urlpatterns` at all |
| `appkit.text` | `truncate(value, length, *, suffix="…") -> str`, `to_english_digits(value) -> str`, `to_persian_digits(value) -> str` — codepoint-aware, matches the frontend half's `truncate` in *behaviour* exactly (the signature shape differs — TS has no keyword-only arguments; see "Frontend usage" below) |
| `appkit.dates` | `to_jalali(value: date \| datetime) -> tuple[int, int, int]`, `from_jalali(year, month, day) -> date`, `format_jalali(value, fmt="%Y/%m/%d") -> str`, `parse_jalali(value, fmt="%Y/%m/%d") -> date` — Gregorian↔Jalali conversion; no third-party type in any signature |
| `appkit.money` | `parse_amount(value: str \| int) -> int`, `format_amount(value: int, *, currency="") -> str` — fixed ASCII `,` grouping, never locale-dependent |
| `appkit.throttling` | `throttle_scope(app_namespace, action) -> str` — a §1.2 scope-prefix-naming helper |
| `appkit.conf` | `get_setting(key) -> Any`, `UNSET`, `DEFAULTS` (internal-but-stable, not re-exported from top-level `appkit`) |
| `appkit.crypto` | `Cipher(key: str \| bytes)` — `.encrypt(value) -> str`, `.decrypt(token) -> str`; `generate_key() -> str`. Fernet encryption taking its key at construction. Requires the `crypto` extra; resolved in `docs/CONTRACT.md` §3: appkit reads no `.env`/settings key of its own, ever |
| `appkit.testing` (pytest plugin, opt-in — see "Testing" above) | `appkit_api_client`, `appkit_user`, `appkit_admin_user`, `appkit_auth_client`, `appkit_admin_client`, `appkit_frozen_request_id`, `appkit_clear_cache`, `appkit_assert_error_envelope(response, *, code, status) -> None`. Every name is `appkit_`-prefixed on purpose — pytest-django ships its own built-in `admin_user`/`admin_client` fixtures, and (verified directly) pytest-django's win that exact name collision silently; the prefix is what keeps this plugin's fixtures from ever landing in that situation |

### `client_ip()` — the trusted-hop algorithm

The table above gives the outcome ("trusts only the proxy-appended entry, `TRUSTED_PROXY_COUNT`-th
from the right"); this is the mechanism, since a host debugging a wrong client IP needs the
algorithm, not just the promise.

`X-Forwarded-For` is a comma-separated list a client can prepend arbitrary fake entries to —
every entry left of what your own infrastructure appended is attacker-controlled. `client_ip()`
never trusts the leftmost entry for exactly this reason. Instead:

1. Split the header on `,`, trim whitespace from each part.
2. Index **from the right**: `parts[-TRUSTED_PROXY_COUNT]` — the entry your own
   `TRUSTED_PROXY_COUNT`-th proxy hop appended, never a client-suppliable position.
3. Validate that entry as an IPv4/IPv6 address (stripping a `[bracket]:port` wrapper or a
   trailing `:port` first) before returning it.

Every one of these four situations falls back to the connection's own `REMOTE_ADDR`, with a
logged warning, rather than raising or returning something wrong:

- `X-Forwarded-For` is absent or empty — no proxy in front of this request at all.
- The header has **fewer entries** than `TRUSTED_PROXY_COUNT` — a misconfigured proxy count, or a
  request that skipped a hop somewhere.
- `TRUSTED_PROXY_COUNT` is **not positive** — `parts[-0]` is `parts[0]`, the spoofable leftmost
  entry, so a zero or negative count is treated as "nothing configured" rather than silently
  handing an attacker-controlled value back as the trusted client IP.
- The candidate at that position **isn't a valid IP address** once normalised — a malformed or
  unexpected header shape.

`appkit.W006` (see "System checks" above) exists because DRF's own `SimpleRateThrottle.get_ident()`
does a **different**, simpler parse of the same header with no way for appkit to inject this
algorithm into it — the two silently disagreeing about who the client is is exactly the failure
that check catches.

## Exports (frontend)

Full signatures, failure paths, and reasoning: `docs/CONTRACT.md` §14–§23 (frontend contract,
Session 2). Nothing beyond this table is exported from `src/index.ts`.

| Export | Provides |
|---|---|
| `HttpClient` | The five-method interface (`get`/`post`/`put`/`patch`/`delete`) a host's concrete client satisfies structurally — appkit never implements one |
| `ApiClientProvider` | The one shared provider a host mounts. Props: `client: HttpClient` (required), `basePaths?: Readonly<Record<string, string>>` (optional, defaults to `{}`), `headerSources?: ReadonlyArray<HeaderSource>` (optional, defaults to `[]`), `children` |
| `ApiClientProviderProps` | The type of the props object above |
| `useApiClient(key, defaultBasePath)` | Called from each installed app's own `api/config.ts`, never directly by a host. **Returns `{ client: HttpClient; basePath: string }`** — this shape is a semver-major-bump trigger (`CLAUDE.md`). Both arguments required — a missing `basePaths` entry falls back to the app's own default, never to `""`/`/`; throws if called outside a mounted `ApiClientProvider` |
| `HeaderSource` | `() => HeadersInit \| Promise<HeadersInit>` — see "Header injection" below |
| `ApiError` / `isApiError` | Matches the backend envelope exactly — one definition instead of one per app. `isApiError` is a brand check, not `instanceof`, so it survives a duplicate-copy install |
| `isApiErrorEnvelope` / `apiErrorFromEnvelope` | Pure envelope-parsing helpers — validate/construct from already-fetched data, never touch `fetch`/`Response` themselves. Forward-compatible on `code`: a code outside the ten-member union still validates as an envelope, and `apiErrorFromEnvelope` degrades it to `"error"` while preserving `message`/`details`/`request_id` and exposing the raw value on `ApiError.unrecognizedCode` (`null` for every known code) |
| `ApiErrorCode` / `ClientErrorCode` / `ApiErrorEnvelope` | Types — the ten backend codes plus this client's own `"unknown_error"`, kept as a separate type so the ten-member union stays a true mirror |
| `makeQueryClient()` | A factory (never a module-level singleton) — mirrors the scaffold's own `frontend/lib/query-client.ts` |
| `truncate(value, length, suffix?)` / `toEnglishDigits(value)` / `toPersianDigits(value)` | Mirror the backend's `appkit.text` in *behaviour* — codepoint-aware, not UTF-16-unit-aware. `suffix` is a plain optional positional parameter here (TS has no keyword-only arguments; the backend's equivalent is keyword-only) |
| `parseAmount(value)` / `formatAmount(value, currency?)` | Mirror `appkit.money` — fixed `,` separator, never locale-dependent |
| `toJalali` / `fromJalali` / `formatJalali` / `parseJalali` / `calendarDateIn` | Mirror `appkit.dates`. Date-only by default; `calendarDateIn(instant, timeZone)` is the explicit, no-default bridge from an instant to a calendar date |
| `JalaliDate` | `{ year: number; month: number; day: number }` — the type every function above operates on |
| `mediaUrl(value, baseUrl)` | Mirrors `appkit.media` — takes its base as an argument, never reads `NEXT_PUBLIC_API_URL` itself |

**Not exported, on purpose:** a concrete client/`apiClient` singleton, `getApiBaseUrl`, a
`QueryClient` singleton, the `ApiClientContext` object itself, any manager or config-hook shape,
any UI component, any storage helper. Reasoning for each: `docs/CONTRACT.md` §21.

### `HttpClient`'s exact method signatures

The interface, verbatim (`docs/CONTRACT.md` §14) — a host's concrete client satisfies this
**structurally**, with no `implements` declaration and no import of this type required in the
host's own client module, since TypeScript is structurally typed:

```ts
interface HttpClient {
  get<T>(path: string, init?: RequestInit): Promise<T>;
  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  patch<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  delete<T>(path: string, init?: RequestInit): Promise<T>;
}

type HeaderSource = () => HeadersInit | Promise<HeadersInit>;
```

`put` is included alongside the more obvious `get`/`post`/`patch`/`delete` because an SDK
wrapping a DRF `ViewSet`'s full-update action needs to express it — a deliberate deviation from
an earlier draft that listed only four methods. There is no sixth `request()` method: that would
leak a host implementation's own internal shape into this interface rather than describing
behaviour, and appkit never implements `HttpClient` itself, only injects it.

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
import { ApiClientProvider, makeQueryClient } from "@hjtdev/appkit";
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

## Frontend usage — the pattern every consuming SDK follows

This is the pattern every future app package's frontend takes over appkit, worked out and
verified with zero friction against `playground/demo-sdk` (`playground/FINDINGS.md` §14). Three
layers, in order:

1. **`api/config.ts`** — a thin binding, never exported from the SDK's own `index.ts`:

   ```ts
   // api/config.ts — internal
   "use client";
   import { useApiClient } from "@hjtdev/appkit";

   export const useDemoConfig = () => useApiClient("demo", "/api/v1/demo");
   ```

2. **An instance-based manager** — the *only* place a raw HTTP call happens, also never
   exported:

   ```ts
   // api/manager.ts — internal
   import type { HttpClient } from "@hjtdev/appkit";

   export class DemoManager {
     constructor(
       private readonly client: HttpClient,
       private readonly basePath: string,
     ) {}

     list(): Promise<DemoItemPage> {
       return this.client.get<DemoItemPage>(`${this.basePath}/items/`);
     }
   }
   ```

3. **Hooks, reading from the binding** — the only layer the SDK's `index.ts` exports:

   ```ts
   // hooks/useDemoItems.ts
   import { useQuery } from "@tanstack/react-query";
   import { useDemoConfig } from "../api/config.js";
   import { DemoManager } from "../api/manager.js";

   export function useDemoItems() {
     const { client, basePath } = useDemoConfig();
     const manager = new DemoManager(client, basePath);
     return useQuery({ queryKey: ["demo", "items"], queryFn: () => manager.list() });
   }
   ```

A host never imports `api/config.ts` or a manager directly — only the hooks (and any query-key
factory a host needs for its own invalidation) are public. This is what keeps `useApiClient`'s
two-required-arguments, throws-on-empty-default design (see "Exports (frontend)" above) doing its
job: every SDK built this way gets the host's injected client and per-app base path without ever
touching `fetch` itself.

**One risk worth naming for SDK authors:** never list `react`/`@tanstack/react-query` as both a
`peerDependency` *and* a real `devDependency` install target without an npm workspace guaranteeing
dedupe — without one, a second, physically separate copy resolves, with its own `React.Context`
object, and `useQuery`/`useApiClient` silently break as if no provider were mounted at all
(reproduced and root-caused in `playground/FINDINGS.md` §13; the exact "two copies" failure mode
this package's own duplicate-copy guard exists to catch on appkit's side, but cannot catch for a
peer dependency it doesn't own).

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
