# CONTRACT.md — appkit's public contract

Written per `CLAUDE-CODE-GUIDE-APP.md` §2, Phase 0: the full public surface, frozen before any
implementation exists. This document is what `README.md`'s config block (`APP-DESIGN.md` §8)
is generated from once code exists — not the other way around. Every entry here is something
that cannot change without a **major** version bump (`CLAUDE.md`'s Semver triggers).

**Session 1 of 2.** This file covers the **backend** half only. Session 2 appends the frontend
half (`appkit`'s TypeScript SDK contract) to the bottom of this same document. No implementation
code exists yet; nothing under `../base-scaffold/` (a separate project) is modified by this
document — findings against it are flagged inline instead.

---

## 0. Standard Phase 0 items — confirmed "none" / "not applicable"

| # | Item | Status | Why |
|---|---|---|---|
| 1 | Models | **None** | appkit has no persistent state. Cache namespace versions live in Redis (via Django's cache API), not a table. No migrations, no admin. |
| 2 | Signals emitted | **None** | Nothing in this surface has an "event happened" shape — appkit is helpers and contracts, not a producer of domain events. |
| 3 | Services (`services.py`) | **N/A** | The entire module surface below (§2) *is* appkit's public callable interface — there is no separate services layer, because there's no app-specific business logic to wrap it around. |
| 4 | Endpoints | **None** | No views, no `urlpatterns`, nothing to `include()`. See §10, "What appkit deliberately does not contain" — the absence is a decision, not an omission, and it's the reason the media-URL helper lives at `appkit.media`, never `appkit.urls`. |
| 5 | Settings / `.env` | See §7 | Four optional settings keys, **zero required or optional `.env` keys**. |
| 6 | Frontend hooks | Session 2 | `useApiClient` (§12 of `APP-DESIGN.md`) is a contract/DI hook, not a data-fetching hook — there is no `useX` data hook in appkit, by design. |
| 7 | Celery / `django.tasks` + schedule | **None** | Deliberate — see `README.md`'s "What appkit deliberately does not provide". A shared dependency that drags in a task runner forces every consuming app *and* host to care about it. |

Two things that are registrations but not any of the seven above, and are covered on their own
terms: appkit's `AppConfig` (§6) and the pytest plugin's explicit opt-in (§2.16).

---

## 1. The error envelope — verbatim, plus the drift found and resolved

Reproduced character-for-character from `BASE-DESIGN.md` §3 and
`../base-scaffold/backend/tools/mixins.py`:

```json
{"error": {"code": "validation_error", "message": "...", "details": {}, "request_id": "..."}}
```

- `details` is **always present** — `{}` when nothing is field-level, so a client never has to
  branch on whether the key exists.
- `request_id` is the same correlation ID `appkit.request_id.request_id_var` carries.
- `code` is a stable, machine-readable string. Adding one is additive; renaming or removing one
  is a **major** bump.
- Headers DRF already set (`Retry-After` on `throttled`, `WWW-Authenticate` on
  `not_authenticated`/`authentication_failed`) are untouched — the handler only ever rewrites
  `response.data`.
- A plain Django `Http404`/`PermissionDenied` is converted to its DRF equivalent *before* code
  lookup, so `get_object_or_404`/`.DoesNotExist` land on `not_found`, not the catch-all.
- An unhandled exception (DRF's handler returns `None`) is logged via `logger.exception` before
  being turned into a `server_error` envelope, so it still reaches Sentry/whatever handler the
  host has. `message` is generic (`"Internal server error."`) with `DEBUG` off, and carries the
  real exception text with `DEBUG` on.

### The code set is **TEN**, not nine — this is a documented drift correction

`../base-scaffold/backend/tools/mixins.py`'s `_code_for` returns `"error"` for any
`APIException` DRF didn't already resolve to one of eight specific types (`UnsupportedMediaType`
→ 415, `NotAcceptable` → 406, or a bare `APIException` some other library raises). Every source
document (`BASE-DESIGN.md` §3, this repo's prior `README.md`/`CLAUDE.md`) states "nine". That
undercount is fixed here, not perpetuated:

| # | `code` | HTTP status | Fires when |
|---|---|---|---|
| 1 | `validation_error` | 400 | `serializers.ValidationError` |
| 2 | `parse_error` | 400 | Malformed request body |
| 3 | `not_authenticated` | 401 | No credentials supplied |
| 4 | `authentication_failed` | 401 | Credentials supplied but invalid |
| 5 | `permission_denied` | 403 | `PermissionDenied` (DRF or Django) |
| 6 | `not_found` | 404 | `Http404` / `NotFound` |
| 7 | `method_not_allowed` | 405 | Verb not supported on this view |
| 8 | `throttled` | 429 | Rate limit hit |
| 9 | `server_error` | 500 | Unhandled exception |
| 10 | **`error`** | *varies* (415, 406, or whatever the raising `APIException` set) | **The documented catch-all** — any `APIException` DRF resolved to a response but that isn't one of the nine specific types above. |

Four rules that make `"error"` a first-class, not an afterthought — stated in this table, in
the eventual README table, and in the doc comment of session 2's `ApiErrorCode` type, not only
in prose here:

1. **`"error"` is the documented catch-all.** It is what the handler already emits; a contract
   that denied this shape would be lying about what clients actually receive.
2. **For `"error"`, the HTTP `status` is authoritative, not `code`.** A client seeing `"error"`
   reads the status code to know what happened — 415 is a client mistake it can fix; treating
   it as `server_error` would send the caller looking at appkit's logs for a problem in their
   own request.
3. **A specific code may be carved out of `"error"` in a future MINOR version** — e.g. adding
   `unsupported_media_type` for 415. Additive for a caller branching on the specific codes;
   a real behaviour change for a caller matching `"error"` against that status. **This is the
   one place the code set can shift without a major bump** — called out explicitly so nobody
   is surprised by it later.
4. Session 2's `ApiErrorCode` union carries all **ten** values and is exhaustive with no
   fallthrough case, so a client `switch (error.code)` type-checks against the real set.

**Decided, so four apps don't each reinvent this:** a domain-specific error identity
(`"insufficient_funds"`, `"slug_taken"`) belongs in `details`, never as a new top-level `code`.
The value of a closed, ten-member code set is that it stays closed — an open one is just DRF's
per-exception `default_code` with extra steps, and every app inventing its own top-level codes
is ten different envelopes wearing one contract's name.

**Corrective action — "nine" is stated as fact in five places, four inside this repo's own
docs:**

| File | Location | Action |
|---|---|---|
| `README.md` | line 127 (exports table) | Corrected in this session — see the diff. |
| `README.md` | line 207 (caveats section) | Corrected — this was the line that *predicted* today's resolution; it now records the resolution instead of flagging it as open. |
| `CLAUDE.md` | line 92 (Semver triggers) | Corrected — "one of the nine" → "one of the ten". |
| `docs/BASE-DESIGN.md` | line 172 | **Not edited — separate project, outside this repo's scope.** Flagged here for the user to apply upstream. |
| `docs/CLAUDE-CODE-GUIDE-BASE.md` | line 464 | Checked — unrelated use of the word "nine" (phase count), not the error codes. No action. |
| `docs/APP-DESIGN.md` | — | Checked — §4 quotes the envelope shape but never states a numeric count. No action. |

---

## 2. Module-by-module export contract

Thirteen importable modules. Every export below states its full signature, return type,
exceptions raised, whether it's public API or an internal helper, and (per the 95% coverage
gate) the non-obvious failure path its test suite must cover. `Public` entries appear in
`__all__`; `Internal` entries exist in the module but are not part of the versioned contract —
changing them freely is not a semver event.

Deliberately **absent** from this list versus the session prompt's module inventory, each
flagged as a considered deviation:

- **No `appkit.logging`.** Decision, §5 below: the `RequestIDFilter` lives in
  `appkit.request_id`, alongside the `ContextVar` and middleware it serves — exactly how the
  scaffold co-locates all three in one file today.
- **No `appkit.urls`.** Decision, §10: appkit ships no `urlpatterns` at all.
- **`appkit.net` and `appkit.media` are two modules, not one**, despite both starting life as
  "URL-ish" — see §2.10-2.11 for why they're kept apart.

### 2.1 `appkit.cache`

```python
def namespace_version(namespace: str) -> int: ...
def invalidate_namespace(namespace: str) -> int: ...
def build_cache_key(namespace: str, *parts: object) -> str: ...
def cached_call[T](key: str, timeout: int | None, producer: Callable[[], T]) -> T: ...

def cache_endpoint(
    *,
    namespace: str,
    timeout: int | None = UNSET,
    per_user: bool = True,
    vary_headers: Sequence[str] = (),
    cache_statuses: Container[int] = (200,),
) -> Callable[[F], F]: ...
```

All **Public**.

- `namespace_version(namespace)` — returns the namespace's current version, seeding it on first
  use. **Changed from the scaffold:** seeds from `int(time.time())`, not the literal `1`. The
  scaffold's `invalidate_namespace` is get-then-increment against Django's cache API and is not
  atomic — already flagged as a known caveat in this repo's `README.md`. The consequence that
  was not previously written down is worse than a race: if the version key is evicted (e.g.
  under Redis `allkeys-lru` memory pressure) and reseeds at `1`, every key built against a
  *higher* version before the eviction becomes reachable again — silently resurrecting data an
  earlier `invalidate_namespace` call explicitly invalidated. Seeding from a wall-clock second
  makes any reseed monotonically ahead of every version that could plausibly have been issued
  before it. **Consequence for callers:** `namespace_version`'s return value is now **opaque**
  — never assume it starts at `1`, only that `invalidate_namespace` always returns something
  strictly greater than what came before it in the same process's view. Never raises.
- `invalidate_namespace(namespace)` — bumps and returns the new version. Never raises (calls
  `namespace_version` first to guarantee the key exists before `cache.incr`).
- `build_cache_key(namespace, *parts)` — `namespace:version:part1:...`; parts longer than 40
  chars or containing anything outside `[A-Za-z0-9\-_.]` are hashed (`sha256`, first 16 hex
  chars) rather than embedded raw. **`:` is deliberately excluded from the safe set**, unlike
  the scaffold's equivalent charset — it's the join delimiter used one line above, so treating
  it as "safe" inside a part would let a part embed it raw and forge extra
  `namespace:version:...` segments, exactly contradicting the next sentence. **Failure path to
  test:** a part containing a cache-backend delimiter (`:`) or something absurdly long (a raw
  user search query) must never blow up key length or let a delimiter smuggle a second segment
  into the key — this is the "user-controlled key fragment is a real Redis footgun" the session
  prompt calls out by name. Never raises.
- `cached_call(key, timeout, producer)` — get-or-set; `producer` runs at most once per miss.
  **Non-obvious failure path:** a `producer` returning `None` is never actually cached — Django's
  `.get()` can't distinguish "miss" from "cached `None`". Documented behaviour, not a bug;
  callers caching a value that's legitimately `None` must wrap it (e.g. a sentinel or a
  one-element tuple) themselves. Never raises on its own; propagates whatever `producer` raises.
- **`timeout=None` means "cache forever"** (Django's own cache semantics) — it therefore cannot
  double as "use the configured default". `cached_call`/`cache_endpoint` accept an internal
  `UNSET` sentinel (not part of the public signature's visible default value — it renders in
  docs as "omit the argument") to mean "use `APPKIT["CACHE_TIMEOUT"]`". This ambiguity is live
  in the scaffold's `cached_call` today and is fixed here rather than carried forward.
- `cache_endpoint(...)` — the new decorator wrapping a DRF view method (`list`/`retrieve`) the
  way `CachedListMixin` wraps `ListAPIView.list`, for views that aren't plain list views.
  - `namespace` is **required, no default** — an unprefixed key is exactly the two-apps-collide
    scenario `APP-DESIGN.md` §1.2 exists to prevent, so there is no safe default to fall back to.
  - `per_user=True` is the load-bearing default. **Non-obvious failure path:** with
    `per_user=False` on a permission-gated view, user A's response is served verbatim to user
    B — an authorization bypass via the cache layer, not a cache bug. `per_user=False` is valid
    *only* where the response is byte-identical for every caller including anonymous users.
    Every test suite using it must include a test proving the cache never crosses two distinct
    users' responses.
  - `vary_headers` — additional request headers folded into the cache key (e.g. `Accept-Language`
    for a bilingual endpoint) beyond user + full path.
  - `cache_statuses` — only responses whose status is in this set are cached; a 403/404 is never
    cached by default, since caching an authorization failure can make it outlive the state that
    caused it.
  - Raises `ImproperlyConfigured` at decoration time (import time) if `namespace` is empty.

### 2.2 `appkit.mixins`

```python
class CachedListMixin:
    cache_namespace: str          # REQUIRED — no default
    cache_timeout: int = UNSET    # UNSET -> APPKIT["CACHE_TIMEOUT"]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response: ...
```

**Public.**

- **Changed from the scaffold: `cache_namespace` is required**, not `"" -> falls back to the
  view's class name`. Two apps each shipping a `NotificationListView` collide in the host's one
  shared Redis instance — precisely the collision `APP-DESIGN.md` §1.2 exists to prevent — and a
  class-name-derived default is a silent trap the moment two apps use a common name. There is no
  host-wide-safe default, so there isn't one.
- Must precede the generic view in MRO (`class MyListView(CachedListMixin, generics.ListAPIView)`)
  — documented, not enforced; a `TypeError`/`AttributeError` at first request is the natural
  failure if it's ordered wrong, since `super().list()` wouldn't resolve.
- **Non-obvious failure path:** caches `response.data` (a plain list of serialized dicts), never
  the `Response` object — a `Response` carries renderer/request state that isn't safe to pickle
  into a cache backend. A test must assert the *second* (cached) call returns data equal to,
  but not the same object as, the first call's queryset-backed result.
- Raises `ImproperlyConfigured` at first `list()` call if `cache_namespace` is empty.

### 2.3 `appkit.exceptions`

```python
ERROR_CODES: Final[tuple[str, ...]]  # the ten, in the order given in §1

def standard_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None: ...
```

**Public.** `standard_exception_handler` is wired via `REST_FRAMEWORK["EXCEPTION_HANDLER"]`
(§8), never used as a per-view mixin — that's what makes it apply to every DRF-raised error,
not only views that remember to opt in.

- Returns `None` only when DRF's own `exception_handler` would (an exception that isn't an
  `APIException`/`Http404`/`PermissionDenied` *and* wasn't already converted to a 500 envelope
  — practically, this function never actually returns `None` itself; the one `None`-shaped
  path is fully absorbed into the `server_error` branch, matching the source).
- **Non-obvious failure path:** an `APIException` whose `.detail` is a nested structure (a
  serializer's per-field errors, which DRF represents as a dict of lists) must flatten to
  `{"error": {..., "details": {<field>: [...]}}}` without losing which field each message
  belongs to — the naive `str(detail)` collapse used for the flat cases must not fire here.
- Never raises on its own; logs (`logger.exception`) rather than re-raising for the
  unhandled-exception path, so Sentry/the host's own logging still sees it.

### 2.4 `appkit.request_id`

```python
request_id_var: ContextVar[str]  # default "-"

class RequestIDMiddleware:
    sync_capable: bool = False
    async_capable: bool = True
    def __init__(self, get_response: Callable[[HttpRequest], Awaitable[HttpResponse]]) -> None: ...
    async def __call__(self, request: HttpRequest) -> HttpResponse: ...

class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool: ...
```

All **Public.** Ports the scaffold's `config/logging.py` behaviour intact — this is the one
module in this surface where "port, don't reimplement" (per the session's framing) applies
most literally, since Phase 2/3 of the scaffold already worked out its sharp edges:

- **Token-based reset in a `finally`.** `request_id_var.set(...)` returns a token;
  `request_id_var.reset(token)` runs in `finally`, not just after a successful response — under
  ASGI concurrency, a set-without-reset leaks one request's ID into whatever coroutine runs next
  on the same task (most visibly, a Celery task enqueued mid-request, or a wholly unrelated
  request if the framework recycles the task). **Non-obvious failure path to test explicitly:**
  a view that raises must still reset the contextvar — assert the var is back to `"-"` after a
  simulated exception, not only after a 200.
- **`markcoroutinefunction(self)` in `__init__`**, required and tested. `sync_capable`/
  `async_capable` only tell Django's own `load_middleware` how to build *this* middleware's
  wrapper; a separate check — `inspect.iscoroutinefunction(instance)` — is what any *outer*
  middleware (e.g. `SecurityMiddleware`) uses to decide whether to `await` it. Omitting the mark
  breaks every real request, ASGI and WSGI both, with an unawaited-coroutine error three layers
  from the actual cause. **Non-obvious failure path:** a regression test must exercise the
  middleware through at least one wrapping middleware (not call `__call__` directly), or this
  exact class of bug passes a unit test while failing every real request.
- **Inbound `X-Request-ID` is accepted only if it looks safe**: length-capped at 64 chars,
  matched against `^[A-Za-z0-9-]+$`. Anything longer or containing anything else (including
  newlines/control characters that could inject a second log line) is discarded and a fresh
  `uuid4().hex` is minted instead — never echoed back to the client unsanitized, never raises.
- **Echoed on the response** unconditionally, via `response["X-Request-ID"] = request_id`, so a
  client can correlate its own request against server logs even on a 500.
- `RequestIDFilter.filter` **never raises** — logging outside a request cycle (management
  commands, Celery tasks, process startup) must still work, defaulting `record.request_id` to
  `"-"`. This is the fixture `appkit.testing`'s `appkit_frozen_request_id` exists to make
  assertable.
- Belongs near the top of `MIDDLEWARE`, after `SecurityMiddleware`, before anything that logs —
  the ordering `appkit.W002` (§6) checks for.
- **Django's own `django.request` auto-logger (the built-in 4xx/5xx logging) never carries
  `request_id`, structurally, regardless of `MIDDLEWARE` ordering.** Found and root-caused via
  `playground/` (`playground/FINDINGS.md`, Phase 6), against Django's own source
  (`django/core/handlers/base.py`): `BaseHandler.get_response_async` `await`s the entire
  middleware chain — including `RequestIDMiddleware` — to completion before calling
  `log_response()` for a 4xx/5xx response, by which point `RequestIDMiddleware`'s own
  `finally: request_id_var.reset(token)` has already run. This is not a bug to fix here — the
  only alternative is not resetting the contextvar, which reopens the concurrency leak the first
  bullet above exists to prevent. Correlation is intact everywhere that matters: the response's
  own `X-Request-ID` header, and any logger *application code* calls during request handling
  (a view, `standard_exception_handler`'s own `logger.exception(...)`). Only Django's automatic,
  built-in request logging is exempt — worth a unit test asserting on `caplog` for the
  `django.request` logger specifically, so this doesn't get re-discovered expecting different
  behaviour.

### 2.5 `appkit.crypto`

```python
class Cipher:
    def __init__(self, key: str | bytes) -> None: ...
    def encrypt(self, value: str) -> str: ...
    def decrypt(self, token: str) -> str: ...

def generate_key() -> str: ...
```

**Public. Requires the `crypto` extra** (§8) — `pip install "hjtdev-appkit[crypto]"` /
`uv add "hjtdev-appkit[crypto]"`.

- **Takes its key at construction time; never reads Django settings.** See §5 for the full
  reasoning — appkit ships the *mechanism*, never assumes a `FERNET_KEY`-shaped setting exists,
  and therefore contributes zero required `.env` keys to any host.
- `Cipher(key)` — `key` must be a valid Fernet key (44-byte urlsafe-base64). **Raises
  `ImproperlyConfigured`** — not the raw `cryptography` `ValueError`/`TypeError` — naming
  `generate_key()` as the fix, ported from the scaffold's existing message.
- `encrypt(value)` — returns a URL-safe token string. Never raises for any `str` input.
- `decrypt(token)` — **raises `cryptography.fernet.InvalidToken`** for a tampered, expired
  (if a TTL was used), or wrong-key token — never silently returns garbage. This is the
  behaviour a caller must not swallow blindly; the existing test names it explicitly
  (`test_tampered_token_is_rejected`, `test_token_from_a_different_key_is_rejected`) and both
  port unchanged.
- `generate_key()` — thin wrapper over `Fernet.generate_key().decode()`, so callers don't need
  to `import cryptography` themselves just to provision a key.
- **Missing-extra failure path, tested explicitly:** importing `appkit.crypto` without the
  `crypto` extra installed raises `ImportError` with a message naming the fix
  (`Install with: uv add "hjtdev-appkit[crypto]"` / `pip install "hjtdev-appkit[crypto]"`), not a bare
  `ModuleNotFoundError: No module named 'cryptography'` three frames deep. The `import
  cryptography` happens lazily inside the module, wrapped in `try/except ImportError`, and
  re-raised with the actionable message — this path is unit-tested by simulating the import
  failure, since a broken error message is otherwise only discovered by whoever hits it.
- Existing scaffold test coverage ports unchanged (round-trip, non-ASCII round-trip, ciphertext
  differs from plaintext, two encryptions of the same input differ, tampered/wrong-key token
  rejection, invalid-key `ImproperlyConfigured`) — only the key's *source* changes from
  `settings.FERNET_KEY` to a constructor argument.

### 2.6 `appkit.permissions`

```python
class IsAppAdmin(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool: ...

class IsObjectOwner(BasePermission):
    owner_field: str = "user"
    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool: ...
```

Both **Public.**

- `IsAppAdmin` — `request.user.is_authenticated and request.user.is_staff`. Relies only on what
  Django's user model already guarantees everywhere (`APP-DESIGN.md` §5), never on another
  app's model. Never raises.
- `IsObjectOwner` — **addition beyond the session prompt's module list**, justified by
  `APP-DESIGN.md` §7.4's mandated test ("403 for another user's object — the IDOR case") and
  §9's security checklist naming IDOR explicitly. Compares `getattr(obj, self.owner_field, None)
  == request.user`. **Non-obvious failure path:** `owner_field` pointing at a nonexistent
  attribute must deny access (return `False`), never raise `AttributeError` mid-permission-check
  — a misconfigured `owner_field` failing open is worse than it failing closed with a wrong
  answer, and only a closed failure is safe by default. Anonymous users are always denied,
  never reach the `getattr` comparison.

### 2.7 `appkit.pagination`

```python
class DefaultPagination(PageNumberPagination):
    page_size: int = 25
    page_size_query_param: str = "page_size"
    max_page_size: int = 100
```

**Public.** A view that can return unbounded data sets an explicit `pagination_class` per
`APP-DESIGN.md` §4 — this is the shared default that saves every app from re-declaring the same
three numbers. `max_page_size` caps `?page_size=` so a client can't request a page large enough
to defeat pagination's purpose entirely.

### 2.8 `appkit.validation`

```python
def validate_query_params[S: Serializer](serializer_class: type[S], params: QueryDict) -> S: ...
def sanitize_html(value: str, *, allowed_tags: Iterable[str] | None = None) -> str: ...
def strip_html(value: str) -> str: ...

ALLOWED_LOOKUPS: Final[frozenset[str]]
def validate_lookup(lookup: str) -> bool: ...
def safe_filter_kwargs(
    params: QueryDict, allowed_fields: Iterable[str], *, allow_relations: bool = False
) -> dict[str, Any]: ...
```

All **Public.**

- `validate_query_params(serializer_class, params)` — runs `params` (a `QueryDict`) through a
  serializer for read-side validation (typed, bounded query params), returning the *validated*
  serializer instance. **Raises `rest_framework.exceptions.ValidationError`** on invalid input —
  deliberately DRF's own exception, so it flows straight into `standard_exception_handler`
  without a translation layer. This is the "thin helper for validating `request.query_params`
  through a serializer", explicitly **not** a parallel validation framework
  (`README.md`'s scope boundary) — no new declaration syntax, just DRF serializers pointed at
  `request.query_params` instead of `request.data`.
- `sanitize_html(value, allowed_tags=None)` — `nh3`-based allowlist sanitisation; `None` uses a
  documented minimal default tag set (`p`, `br`, `strong`, `em`, `a`, `ul`, `ol`, `li`). Requires
  the **hard** `nh3` dependency (§9) — no extra needed. Never raises; malformed HTML is repaired,
  not rejected, matching `nh3`'s own behaviour. **Non-obvious failure path:** `<script>` and
  `on*=` event-handler attributes must be stripped even when nested inside an otherwise-allowed
  tag (`<a onmouseover="...">`), not only at the top level — this is the one behaviour a test
  suite must assert directly rather than trust to the library, since "we sanitise HTML" is a
  security claim, not a formatting one.
- `strip_html(value)` — removes all tags, returning plain text (`allowed_tags=()`  under the
  hood). For fields that must never contain markup at all (a display name), not fields that may
  contain safe rich text.
- `ALLOWED_LOOKUPS` — the ORM lookup allowlist: `exact`, `iexact`, `contains`, `icontains`,
  `startswith`, `endswith`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull`, `range`. **Corrected during
  implementation (Phase 4), flagged as a contradiction rather than a gap:** an earlier draft of
  this section named the first member "`eq`/exact" — Django has no `eq` lookup at all, so only
  `exact` goes in the set. Admitting a literal `"eq"` string would let a caller build
  `filter(x__eq=...)` through this exact allowlist and get a `FieldError` from the ORM, which is
  precisely the failure mode this function exists to prevent before it reaches `.filter()`.
  **`regex` and `iregex` are excluded on purpose** — a user-controlled regex against Postgres is
  a ReDoS vector, and this allowlist's whole job is to be the thing an app checks before building
  a `filter(**kwargs)` from user input.
- `validate_lookup(lookup)` — `True`/`False`, no exception; a pure membership check against
  `ALLOWED_LOOKUPS`, split out so an app can compose its own filtering logic without going
  through `safe_filter_kwargs`.
- `safe_filter_kwargs(params, allowed_fields, allow_relations=False)` — builds a `.filter()`-safe
  kwargs dict from raw query params: only `allowed_fields` may appear, only `ALLOWED_LOOKUPS`
  suffixes are accepted (`?status__icontains=x` passes if `status` is allowed;
  `?status__regex=x` never does), and unknown params are dropped, not errored — a client typo
  degrades to "no filter applied", not a 500. **`allow_relations=False` is the load-bearing
  default and the whole point of this function's existence:** with it, `field__related__field`
  double-underscore traversal is rejected outright — `?user__email__icontains=` cannot be used
  to exfiltrate another table's data through a filter an app author only meant to expose one
  field of. **Non-obvious failure path, mandatory test:** a field name containing `__` that
  collides with a legitimate allowed field plus a lookup suffix (e.g. `allowed_fields=["created_at"]`
  and `?created_at__gte=x`) must resolve correctly while `?created_at__related__gte=x` (three
  segments) is rejected even though the first segment matches — the parser must count segments,
  not just check a prefix. **Value coercion, decided during implementation (Phase 4) — §2 didn't
  specify one:** the raw query-param string is coerced per lookup before landing in the returned
  dict — `in`/`range` split on `,` into a list, `isnull` parsed into a real `bool`, every other
  lookup passed through as the raw string. The `isnull` coercion specifically is not optional:
  without it, `?x__isnull=false` would filter as `True` (any non-empty string is truthy in
  Python), a silent wrong-results bug rather than a style choice.

### 2.9 `appkit.files`

```python
@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    format: str

def detect_mimetype(data: bytes) -> str: ...

def validate_upload(
    file: UploadedFile,
    *,
    allowed_mimetypes: Iterable[str],
    max_bytes: int = UNSET,
) -> None: ...

def validate_image(
    file: UploadedFile,
    *,
    max_bytes: int = UNSET,
    max_dimensions: tuple[int, int] | None = None,
    allow_svg: bool = False,
) -> ImageInfo: ...
```

All **Public.**

- `detect_mimetype(data)` — magic-byte sniffing via `puremagic` (§9), **never** the
  client-supplied `Content-Type` header and never the filename extension — both are
  attacker-controlled and routinely wrong. Returns `"application/octet-stream"` for anything
  unrecognised rather than raising, so a caller decides what "unknown" means for its own upload
  policy.
- `validate_upload(file, allowed_mimetypes, max_bytes=UNSET)` — sniffs, checks the detected
  mimetype against `allowed_mimetypes`, checks size, checks that the file's *extension* agrees
  with the *detected* mimetype via an explicit, hardcoded table (`.jpg`/`.jpeg` ↔
  `image/jpeg`, etc.) — **never `mimetypes.guess_extension`**, because the stdlib's answer
  depends on the host OS's `/etc/mime.types` and disagrees across systems for the exact image
  formats this function exists to check. `max_bytes=UNSET` resolves to
  `APPKIT["MAX_UPLOAD_BYTES"]`. **Raises `django.core.exceptions.ValidationError`** (the DRF
  serializer-friendly one) naming which check failed. **Non-obvious failure path, the single
  most important test in this module:** sniffing consumes the file stream (`file.read()` or
  equivalent); the implementation **must `file.seek(0)` in a `finally`**, restoring the read
  position regardless of outcome — without it, whatever saves the file afterward (a serializer's
  `.save()`) writes a truncated-to-empty file, a corruption bug invisible to any test that
  doesn't specifically re-read the file after calling `validate_upload`. This is explicitly a
  finding from reviewing the source pattern, not something to skip.
- **`APPKIT["MAX_UPLOAD_BYTES"]` is a semantic/business-rule limit, not a DoS control** — by the
  time this function runs, Django has already buffered the request body (up to
  `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE`) or spilled it to a temp file.
  `README.md`/`CONTRACT.md` both point hosts at Django's own settings for the actual
  memory/disk DoS boundary — this function's limit is "reject a 50 MB avatar", not "prevent a
  request from exhausting server memory".
- `validate_image(file, max_bytes=UNSET, max_dimensions=None, allow_svg=False)` — everything
  `validate_upload` does, restricted to image mimetypes, plus a decompression-bomb-aware
  dimension check (reads header dimensions before fully decoding) when `max_dimensions` is
  given. **Requires the `images` extra** (`Pillow`) for anything beyond header-only dimension
  reads; raises the same actionable `ImportError` pattern as `appkit.crypto` if the extra is
  missing and dimension checking was requested. **SVG is rejected unless `allow_svg=True` is
  explicitly passed** — SVG is XML, and XML is a script-execution vector (embedded `<script>`,
  external entity references) that magic-byte sniffing alone happily approves as "a valid file
  of the claimed type." Opting in is a real decision an app author makes, not a default.
  Returns `ImageInfo(width, height, format)` on success. **SVG's `ImageInfo`, decided during
  implementation (Phase 4) — §2 doesn't specify one:** when `allow_svg=True`, dimensions are
  read from the SVG root element's `width`/`height` attributes via a bounded regex scan, never
  by handing the file to Pillow (which doesn't support SVG at all — the `images` extra is never
  needed on this path). Neither attribute is guaranteed present on a valid SVG (a
  `viewBox`-only document is legal XML), and either can be malformed; both cases resolve to `0`
  rather than raising, and `max_dimensions` is skipped when a dimension is `0` rather than being
  compared against a value known to be meaningless.

### 2.10 `appkit.net`

```python
def client_ip(request: HttpRequest | Request) -> str: ...
```

**Public — the module's only export**, deliberately narrower than the session prompt's
inventory (which bundled absolute-URL conversion in here too — see §2.11 for why that moved
out).

- **Trusts only the proxy-appended `X-Forwarded-For` entry, never the leftmost,
  client-controlled one.** This is a finding against the base-scaffold's actual deployed
  behaviour, verified directly against the installed `uvicorn==0.52.4` source
  (`uvicorn/middleware/proxy_headers.py`), not assumed: with the scaffold's documented prod
  command (`--proxy-headers --forwarded-allow-ips "*"`, `BASE-DESIGN.md`),
  `_TrustedHosts.always_trust` is `True`, and `get_trusted_client_address` returns
  `x_forwarded_for_hosts[0]` — **the leftmost entry, which is exactly the one a client can set
  themselves** — into ASGI `scope["client"]`, i.e. Django's own `request.META["REMOTE_ADDR"]`
  is spoofable end-to-end in that exact deployment. `appkit.net.client_ip` therefore does not
  read `REMOTE_ADDR` for its answer; it parses the raw `X-Forwarded-For` header itself and reads
  from the **right**: nginx's `$proxy_add_x_forwarded_for` *appends* its own peer address to
  whatever it received, so with `APPKIT["TRUSTED_PROXY_COUNT"]` (default `1`) trusted proxies in
  front, the real client is `parts[-N]`. Each candidate entry is validated through
  `ipaddress.ip_address()` (brackets/port stripped first for `IPv6`/`host:port` forms); a header
  with fewer entries than `TRUSTED_PROXY_COUNT` falls back to the connection's own remote
  address with a logged warning, rather than returning a spoofable value silently.
  **Recommendation flagged back to the base-scaffold project, not applied here (separate repo,
  outside this session's scope):** narrow `--forwarded-allow-ips` to the real nginx address
  instead of `"*"`, which would let uvicorn's own trust logic do this correctly without
  appkit needing to re-parse the header at all.
- Never raises — an absent or malformed header returns the direct connection's address (with a
  warning logged), since "I can't determine the real client IP precisely" should degrade to
  "best available answer", not crash the request. **Non-obvious failure path, mandatory test:**
  an `X-Forwarded-For` header with *more* entries than `TRUSTED_PROXY_COUNT` (a client
  pre-pending fake hops to push their real IP further left) must still resolve to the
  `TRUSTED_PROXY_COUNT`-th-from-the-right entry, proving the count-from-the-right logic isn't
  accidentally count-from-the-left with extra steps.
- **`TRUSTED_PROXY_COUNT <= 0` falls back to `REMOTE_ADDR` rather than resolving the header at
  all — decided during implementation (Phase 4), and written down here explicitly because it's
  security-relevant, not merely a code detail.** §2's original text specifies `parts[-N]` for
  `N = TRUSTED_PROXY_COUNT` but doesn't state what happens at `N <= 0`. Python's negative-index
  semantics make this a real trap: `parts[-0]` is `parts[0]` — the leftmost, client-controlled
  entry this whole function exists to distrust. A host that misconfigures
  `APPKIT["TRUSTED_PROXY_COUNT"]` to `0` (or a negative value, e.g. via a bad environment-driven
  default) must not silently start trusting client-supplied IPs; it degrades to the same
  direct-connection fallback as a too-short header, with the same logged warning. No new
  settings key — this is a boundary case of the existing one.

### 2.11 `appkit.media`

```python
def file_url(
    value: FieldFile | str | None, *, request: HttpRequest | Request | None = None
) -> str | None: ...

def absolute_url(
    url: str | None, *, request: HttpRequest | Request | None = None
) -> str | None: ...
```

Both **Public.** **Kept in a separate module from `appkit.net`, deliberately** — the two share
only the surface-level word "URL". `appkit.net` is transport/trust-boundary logic
(proxy-header parsing, a security-sensitive read of the request); `appkit.media` is file-location
formatting. Both happen to take an optional `request` argument, and that's precisely the trap:
a later session could plausibly "simplify" by merging them into one `request`-utilities module,
after which proxy-trust logic and media-URL formatting get refactored together for no reason
related to either one's actual job. Keeping them apart is what prevents that merge from ever
looking like a reasonable simplification. (`appkit.uris` was considered and rejected for the
same reason in reverse — it invites generic URI/query-string helpers that aren't in scope at
all.)

- **Never raises on the ordinary path.** `file_url(None)` and `file_url("")` both return `None`
  — a serializer calling this on every optional `ImageField`/`FileField` must not have to guard
  against an empty field itself. (Django's own `FieldFile.url` raises `ValueError` on an empty
  field; this function absorbs that.)
- **Raises only when genuinely misconfigured:** if `request` is `None` **and**
  `APPKIT["SITE_URL"]` is unset (empty string, the default), both functions raise
  `ImproperlyConfigured` naming `APPKIT["SITE_URL"]` as the fix. Silently returning a relative
  URL in that case is exactly how a broken image link ends up in a Celery-rendered email
  nobody notices until a customer complains — failing loudly at the point of misconfiguration
  is strictly better than a passing test and a broken production email.
- **Already-absolute input passes through unchanged.** A `FieldFile` backed by an S3/CDN storage
  backend, or `MEDIA_URL` pointing off-host, must not be double-prefixed into something like
  `https://api.example.com/https://cdn.example.com/x.png`. Detected via `urllib.parse.urlparse`
  having a non-empty `scheme`/`netloc`. **Explicit test**, not an assumption.
- **With `request`**, uses `request.build_absolute_uri(...)` — this is what makes the function
  correct in dev, staging, and prod with **zero configuration**, since Django/DRF already put
  a real request in scope everywhere a serializer runs. **Non-obvious failure path, tested
  rather than assumed:** the scaffold's prod deployment is uvicorn behind nginx with
  `--proxy-headers` and `TRUST_PROXY_SSL_HEADER`/`SECURE_PROXY_SSL_HEADER` configured
  (`BASE-DESIGN.md`). `build_absolute_uri()` must yield `https://` under that configuration, not
  `http://` — an `http://` result here means every media URL served in production is mixed
  content that browsers silently block. The test simulates the real proxy header
  (`HTTP_X_FORWARDED_PROTO: https`) with `SECURE_PROXY_SSL_HEADER` set, exactly as
  `BASE-DESIGN.md`'s own healthcheck does for the same reason, and asserts the scheme.
- **Without `request`** (Celery task, management command, email template), falls back to
  `APPKIT["SITE_URL"]` as the base — this is the one place that setting is read.
- **Which one is authoritative, stated so app authors don't default to shipping relative
  paths and pushing the work onto every client:** the **backend** absolutizes — in serializer
  output wherever a request exists, and via `SITE_URL` in tasks/emails where it doesn't. A URL
  absolutized server-side is correct for *every* consumer, including non-browser ones (a mobile
  client, a webhook payload). Session 2's frontend `mediaUrl()` exists only as the fallback for
  a response that happens to carry a relative path (a legacy endpoint, or an app that
  deliberately returns one) — it absolutizes against the frontend's own **API origin**
  (`NEXT_PUBLIC_API_URL`), which is a different origin from the site itself in this scaffold
  (`:3000` vs `:8000`), not the "site origin" a naive implementation might reach for. Both
  halves share the same edge behaviour: `null`/`undefined` in → `null` out; already-absolute
  passes through unchanged.

### 2.12 `appkit.text`

```python
def truncate(value: str, length: int, *, suffix: str = "…") -> str: ...
def to_english_digits(value: str) -> str: ...
def to_persian_digits(value: str) -> str: ...
```

All **Public.** **Flagged as the weakest module in this contract:** `django.utils.text.Truncator`
already does word/HTML-aware truncation, so `truncate` alone would not justify a module. It's
kept, narrowed to exactly this signature, for one concrete reason: session 2 ships a frontend
`truncate` with matching semantics (same suffix, same length-counting rule), so a value rendered
both server-side (an admin list, an email) and client-side truncates identically instead of two
independently-tuned implementations drifting apart one character at a time.

- `truncate(value, length, suffix="…")` — truncates by character count including the suffix
  (`truncate("hello world", 8)` → `"hello w…"`, 8 chars total), never mid-multi-byte-codepoint.
  Never raises; `length <= len(suffix)` returns just the suffix, clamped, rather than erroring
  on a degenerate input.
- `to_english_digits` / `to_persian_digits` — the part of this module with **no stdlib
  equivalent**, and the actual justification for `appkit.text` existing at all:
  Persian-keyboard digits (`۰۱۲۳۴۵۶۷۸۹`, and the Arabic-Indic set `٠١٢٣٤٥٦٧٨٩`) arrive in real
  query params, form fields, and price inputs from any Persian-locale keyboard, and both
  `appkit.dates.parse_jalali` and `appkit.money.parse_amount` (§2.13, §2.14) need this
  conversion internally before they can parse anything — pulled out as a public function rather
  than a private helper because callers legitimately need it standalone (e.g. normalizing a
  phone number field before regex validation). Pure character-mapping; never raises, passes
  through unrecognised characters unchanged.

### 2.13 `appkit.dates`

```python
def to_jalali(value: date | datetime) -> tuple[int, int, int]: ...
def from_jalali(year: int, month: int, day: int) -> date: ...
def format_jalali(value: date | datetime, fmt: str = "%Y/%m/%d") -> str: ...
def parse_jalali(value: str, fmt: str = "%Y/%m/%d") -> date: ...
```

All **Public.**

- **No third-party type in any signature.** All four take/return stdlib `date`/`datetime`/`str`
  only — `jdatetime`/`jalali-core` (§9) stay entirely internal implementation detail, so a
  future major version bump in either dependency can never force an appkit major bump; it's an
  internal swap.
- `to_jalali(value)` — returns `(year, month, day)` as a plain tuple, not a `jdatetime.date`, for
  the same signature-hygiene reason above. Never raises for any valid `date`/`datetime`.
- `from_jalali(year, month, day)` — **raises `ValueError`** for an invalid Jalali calendar date
  (e.g. day 31 in a 30-day Jalali month, or an invalid leap day) — the same exception shape
  `datetime.date(...)` itself raises for an invalid Gregorian date, so callers don't need a
  Jalali-specific except clause.
- `format_jalali(value, fmt="%Y/%m/%d")` — `strftime`-style format string applied to the Jalali
  representation. Never raises for a valid `date`/`datetime` input; an unsupported format
  directive raises `ValueError` (mirrors stdlib `strftime`'s own failure mode).
- `parse_jalali(value, fmt="%Y/%m/%d")` — the inverse; runs `to_english_digits` internally first
  (Persian-keyboard input is the common real-world case for a date typed by a user, not pasted).
  **Raises `ValueError`** for a string that doesn't match `fmt` or names an invalid Jalali date —
  never returns a best-guess/partial result.

### 2.14 `appkit.money`

```python
def parse_amount(value: str | int) -> int: ...
def format_amount(value: int, *, currency: str = "") -> str: ...
```

Both **Public. Flagged as the second-weakest module** — only apps handling money need it, but
it survives the "does every app need this" bar only barely and is kept deliberately tiny (two
functions, zero dependencies) rather than grown into a currency/locale framework.

- `parse_amount(value)` — accepts a digit string (including Persian/Arabic-Indic digits, via
  `to_english_digits` internally) or an `int`; strips thousands separators (`,`/`٬`). **Rejects
  `float` outright, raising `TypeError`** — a caller passing `12000.0` gets an explicit error,
  not a silently-accepted binary float. Binary floating point cannot represent most decimal
  currency amounts exactly, so a float arriving in a money-parsing function is a defect in the
  caller, not a valid input format this function should paper over. **Raises `ValueError`** for
  a string that isn't a valid integer after normalization (letters, multiple decimal points,
  empty string). **Also rejects `bool` with `TypeError`, decided during implementation (Phase
  4) — §2 is silent on it:** `bool` is an `int` subclass in Python, so `parse_amount(True)`
  would otherwise silently succeed and return `1`. A caller passing a boolean into a
  money-parsing function is a defect in the caller in the same way a `float` is — excluding it
  is the reading consistent with the `float` rule already stated, not a separate carve-out.
- `format_amount(value, currency="")` — thousands-grouped string (`1000000` → `"1,000,000"`,
  or `"1,000,000 IRT"` with `currency="IRT"`). Never raises for any `int` input, including
  negative values (`-500` → `"-500"`) and `0`.

### 2.15 `appkit.throttling`

```python
def throttle_scope(app_namespace: str, action: str) -> str: ...
```

**Public.** Enforces `APP-DESIGN.md` §1.2's prefix convention mechanically instead of leaving
every app to remember it by hand: `throttle_scope("notifications", "list")` →
`"notifications_list"`. **Raises `ValueError`** if either argument is empty or contains an
underscore itself (which would make the resulting scope ambiguous to split back apart, and more
practically, signals a caller passing an already-prefixed value by mistake).

Paired with **`appkit.W004`** (§6): a system check, not a runtime function, so it's documented
here rather than duplicated as a second export. It walks every view reachable from
`ROOT_URLCONF`, collects declared `throttle_scope` values, and warns for any with no matching
`DEFAULT_THROTTLE_RATES` entry — directly answering `APP-DESIGN.md` §7.4's named failure: "a
typo'd `throttle_scope` fails open, silently," since DRF only raises at request time, once per
request, never at startup.

**Complementary with W004, not a definition of it:** `throttle_scope()` enforces the naming
*format* at the point of declaration; W004 checks *registration* only and is indifferent to
format (it never rejects a scope for being unprefixed, hyphenated, or otherwise not something
`throttle_scope()` would itself produce — a host using DRF's own built-in `anon`/`user` scopes
must not warn). Neither check substitutes for the other.

### 2.16 `appkit.conf`

```python
UNSET: Final[object]             # sentinel: "fall back to the APPKIT default", never None
DEFAULTS: Final[dict[str, Any]]  # see §7 for the full dict + defaults
def get_setting(key: str) -> Any: ...
```

**Internal-but-stable** — not re-exported from a top-level `appkit` namespace, but every app
inspecting appkit's own defaults (none currently need to) or a host writing a test against a
specific `APPKIT` key would import this directly, so its shape is held to the same "don't break
it silently" standard as a public module even though it's one layer down. Follows
`APP-DESIGN.md` §3.5's `conf.py` pattern exactly: `get_setting(key)` reads
`settings.APPKIT.get(key, DEFAULTS[key])`, so a host omitting a key gets the documented default
rather than a `KeyError`/`AttributeError` deep inside a view. `get_setting` raises `KeyError`
only for a `key` that isn't in `DEFAULTS` at all — a programming error inside appkit itself,
never a host-facing failure mode.

### 2.17 `appkit.testing` — the pytest plugin

**Opt-in is explicit** — `-p appkit.testing` in the consumer's own `addopts`
(`tool.pytest.ini_options`), never automatic. Two rejected alternatives, both considered and
both wrong for this ecosystem:

- A `pytest11` entry point would auto-load these fixtures into **every** host's test suite the
  moment `appkit` is merely installed (which is always, transitively) — invisible magic adding
  fixtures nobody asked for into a namespace they didn't opt into.
- `pytest_plugins = ["appkit.testing"]` only works from the **rootdir** conftest in pytest 7+;
  an app package's own `testpaths = ["../tests/backend"]` (`APP-DESIGN.md` §7.1) means the
  package's own conftest isn't the rootdir conftest, so this silently wouldn't even work as a
  default for the app packages that need it most.

**Every fixture name below carries an `appkit_` prefix — decided during implementation (Phase
4), and stated here as a correction to an earlier draft of this section, which used bare names
(`api_client`, `user`, `admin_user`, `auth_client`, `admin_client`, `frozen_request_id`,
`clear_cache`).** `APP-DESIGN.md` §1.2's namespacing rule ("anything appkit contributes to a
shared namespace carries a prefix, no exceptions") applies to pytest's fixture registry exactly
as much as it applies to cache keys or settings keys — it's the same kind of flat, shared
namespace, just one pytest owns instead of Django's cache backend. The concrete evidence this
convention exists to prevent, found during this module's own implementation, not hypothesised:
pytest-django ships its own built-in fixtures literally named `admin_user` and `admin_client`,
and empirically (verified directly against the installed pytest-django, not assumed)
pytest-django's versions win that name collision **silently** wherever `db`/`django_db` is in
play — requesting bare `admin_user`/`admin_client` returns pytest-django's plain Django
`User`/`Client`, never appkit's reflectively-built ones, with no warning anywhere. `user` and
`api_client` hadn't collided with anything at the time of writing — but "hasn't collided yet"
is precisely the condition the prefix rule exists to guard against, which is why the fix is
prefixing every name this module exposes, not the two that happened to collide first.

```python
@pytest.fixture
def appkit_api_client() -> APIClient: ...

@pytest.fixture
def appkit_user(db) -> AbstractBaseUser: ...

@pytest.fixture
def appkit_admin_user(db) -> AbstractBaseUser: ...

@pytest.fixture
def appkit_auth_client(appkit_api_client, appkit_user) -> APIClient: ...

@pytest.fixture
def appkit_admin_client(appkit_api_client, appkit_admin_user) -> APIClient: ...

@pytest.fixture
def appkit_frozen_request_id() -> Iterator[str]: ...

@pytest.fixture
def appkit_clear_cache() -> None: ...

def appkit_assert_error_envelope(response: Response, *, code: str, status: int) -> None: ...
```

- `appkit_user`/`appkit_admin_user` build through `get_user_model().USERNAME_FIELD`
  **reflectively**, not a hardcoded `create_user(username=...)` call — a host on an email-based
  custom user model (`USERNAME_FIELD = "email"`, the common case for a fresh Django project in
  2026) would break immediately on a fixture that assumes `username`. **Non-obvious failure
  path, tested directly:** the fixture must be exercised against a settings module using a
  non-`username` `USERNAME_FIELD` to prove the reflection actually works, not just against the
  plugin's own default test settings which might happen to use the common case.
- `appkit_clear_cache` is **deliberately not `autouse`**. Under `pytest -n auto`
  (`pytest-xdist`, `APP-DESIGN.md` §7.6) against a single shared Redis instance, an autouse
  fixture clearing the cache between every test would clear another xdist worker's in-flight
  test data too — intermittent, worker-count-dependent failures that are miserable to diagnose.
  Documented recommendation: use Django's `LocMemCache` for the test settings module (isolated
  per process) or a distinct Redis DB index per xdist worker if a real cache backend's
  behaviour is under test.
- `appkit_frozen_request_id` — yields a fixed request-ID string and asserts it's restored to
  `"-"` (or the prior value) on fixture teardown, making `RequestIDMiddleware`'s
  reset-in-`finally` contract (§2.4) directly assertable from a consuming app's own tests, not
  just appkit's.
- `appkit_assert_error_envelope(response, code=..., status=...)` — **addition beyond the session
  prompt's inventory**, justified directly by `APP-DESIGN.md` §7.4's minimum test bar applying
  to *every* app: without a shared assertion, nine installed apps hand-roll nine slightly
  different envelope assertions (some checking `details`, some not; some checking `request_id`
  is non-empty, some not), and a real envelope-shape regression in appkit itself would show up
  as nine different flavors of test failure instead of one clear one. Raises the test
  framework's own `AssertionError` with a diff-friendly message on mismatch — same substitutable
  from `assert` directly, not a bespoke passing/failing type. Prefixed for consistency with the
  rest of this module's surface even though, as a plain function rather than a fixture, it was
  never at risk of the same collision.

---

## 3. `FERNET_KEY` — resolved as call-time-only; zero required `.env` keys (item D)

`appkit.crypto.Cipher` takes its key as a constructor argument. It never reads
`settings.FERNET_KEY` or any other Django setting.

**The three options weighed:**

1. **Read `settings.FERNET_KEY`** — rejected. It would make `FERNET_KEY` a *required* setting
   for every host that installs *any* app, even one that never touches encryption, and it
   directly contradicts `BASE-DESIGN.md` §3's own boundary table: `encrypt`/`decrypt` "stays in
   `tools/`, permanently — wraps the host's own `FERNET_KEY`. An app needing encryption uses its
   own documented `.env` key and its own cipher — never the host's `tools.crypto`."
2. **Both** (settings-read with a call-time override) — rejected. A convenience default that
   silently reads host settings becomes load-bearing the moment one app relies on it, and two
   unrelated callers sharing one host-level key for different data is exactly the coupling the
   boundary table exists to prevent — a "default" here is not actually safer, just less visible.
3. **Take the key at call time (chosen)** — resolves the apparent tension between "appkit
   ships the mechanism" and "the host owns `FERNET_KEY` permanently" rather than picking a side:
   applying `BASE-DESIGN.md` §3's own stated test — *does this depend on host configuration?* —
   a key-taking `Cipher` depends on **none**. `tools/crypto.py` keeps its `FERNET_KEY` exactly
   where it is and builds its own `Cipher(settings.FERNET_KEY)` from it; an app declaring
   `hjtdev-appkit[crypto]` builds a `Cipher` from **its own** documented `.env` key. Only the primitive
   itself — "wrap Fernet safely, with a clear error on a bad key" — is shared, which is the
   named alternative to four apps each hand-rolling that primitive independently
   (`APP-DESIGN.md` §4's "bundles its own equivalent").

**Combined with the extras decision (§9) into one rule, stated once here and cross-referenced
from §7 and §9:**

> `appkit.crypto` is an optional extra (`hjtdev-appkit[crypto]`) that takes its key at call time.
> appkit therefore requires **no `.env` key and no settings key** for encryption, under any
> install combination. An app declaring `hjtdev-appkit[crypto]` is what makes *a* key necessary for
> *that app* — and that key is the app's **own** documented `.env` key, never the host's
> `FERNET_KEY` and never a key appkit itself names. The host scaffold's `FERNET_KEY` stays
> exactly where `BASE-DESIGN.md` §3 already puts it: owned by `tools/crypto.py`, for
> `config/`/`core/` code only, entirely untouched by anything in this document.

**Consequence — the headline of §7: appkit has no required `.env` key at all**, under any
combination of extras. This is the single most valuable property of this contract, since
`README.md` §8 makes every key something every host must configure.

Behaviour otherwise carries over unchanged from `../base-scaffold/backend/tools/crypto.py`,
including its full existing test coverage (§2.5) — only the key's *source* changes.

---

## 4. `build_logging_config` stays with the host (item E)

**appkit does not offer a `build_logging_config`-equivalent helper.** It ships exactly the three
things `BASE-DESIGN.md` §3's boundary table assigns to it — `request_id_var`,
`RequestIDMiddleware`, `RequestIDFilter`, all three in `appkit.request_id` (§2.4) — and nothing
that decides *how* logs are rendered.

The dev-console-vs-prod-JSON choice, and the `structlog` `_add_request_id` processor that
carries the ID into structlog's own event dicts, are **host policy**, not something a shared
dependency has any business deciding — matching `BASE-DESIGN.md` §3's table verbatim
("`build_logging_config()`, the structlog `_add_request_id` processor — stays in
`config/logging.py`, permanently"). A shared dependency baking in one opinion about log
rendering would be exactly the kind of host-specific assumption `CLAUDE.md`'s working agreement
warns against ("whenever you're about to rely on something existing outside this package,
stop").

**Consequence: `appkit.logging` does not exist as a module.** The `RequestIDFilter` lives in
`appkit.request_id` instead — co-located with the `ContextVar` and middleware it exists to
serve, exactly how the scaffold's own `config/logging.py` co-locates all three today, and named
so `from appkit.request_id import RequestIDFilter` reads as "the thing that serves the request
ID", not as a logging-config helper that happens to live elsewhere. Flagged explicitly as a
deviation from the session prompt's `logging.py` module name.

**Mechanically, this means:**

```python
# backend/config/logging.py — everything else in build_logging_config() is unchanged;
# only where these two names come from changes:
from appkit.request_id import RequestIDFilter, request_id_var
```

The host's own `_add_request_id` structlog processor becomes three lines calling
`request_id_var.get()` — the `ContextVar` **object identity** is the only thing that has to be
shared between appkit and the host's logging config, and importing it from one place is what
guarantees appkit's middleware and the host's log formatter are reading the same variable.

**No `structlog` dependency in appkit** — a direct consequence, listed again in §9's dependency
table for completeness.

---

## 5. `INSTALLED_APPS` — confirmed yes, with concrete system checks (item F)

**Confirmed, not merely left standing.** `INSTALLED_APPS += ["appkit"]`,
`AppConfig` at `appkit.apps.AppKitConfig`:

```python
class AppKitConfig(AppConfig):
    name = "appkit"
    verbose_name = _("App Kit")  # translatable, per APP-DESIGN.md §2's apps.py convention
    # No default_auto_field — appkit defines no models.

    def ready(self) -> None:
        from django.core.checks import register
        from appkit import checks
        register(checks.check_request_id_middleware)
        register(checks.check_exception_handler)
        register(checks.check_middleware_order)
        register(checks.check_unknown_settings_keys)
        register(checks.check_throttle_scopes)
        register(checks.check_logging_filter)
```

**Why yes, and why the lean's reason (1) is now a concrete requirement, not a hedge:**

1. **Translations become real, not speculative.** `standard_exception_handler` (§2.3) generates
   three user-facing strings of its own — `"Validation failed."`, `"Request failed."`,
   `"Internal server error."` — none of which come from a serializer field DRF would otherwise
   translate. Wrapped in `gettext_lazy` with a shipped `locale/` directory, these are only
   discovered by Django's translation machinery when appkit is a real, `INSTALLED_APPS` member —
   not merely an importable package. DRF's own `JSONEncoder` resolves lazy translation strings
   before serializing, so this is safe to do directly in the envelope with no extra step.
   **Behaviour change from the scaffold, recorded:** the scaffold's equivalent strings are plain
   `str` literals today.
2. **System checks that fail loudly instead of degrading silently** — the strongest of the
   original three reasons, and the one this document turns into an actual table (§6).
3. Future management commands — unchanged from the original lean, still speculative, still
   cheap to have the slot available for.

**Known limit, stated plainly:** every check below only runs if the host got
`INSTALLED_APPS` itself right — the one wiring mistake nothing inside appkit can self-detect,
since Django never invokes `ready()` on an app that isn't listed. `README.md` and
`INTEGRATION-GUIDE.md` §2 step 5 both carry this caveat next to the wiring instructions, not
buried here alone.

---

## 6. System checks registered by `AppKitConfig.ready()`

**Seven functions, eight IDs** — the mapping is stated once here, not left as an inference from
the `ready()` code block: `appkit.E001` → `check_request_id_middleware`; `appkit.E002` and
`appkit.W001` → `check_exception_handler` (one function, since both inspect the same setting);
`appkit.W002` → `check_middleware_order`; `appkit.W003` → `check_unknown_settings_keys`;
`appkit.W004` → `check_throttle_scopes`; `appkit.W005` → `check_logging_filter`; `appkit.W006` →
`check_num_proxies_throttle_agreement`.

| ID | Level | Fires when | Why this one is silent otherwise |
|---|---|---|---|
| `appkit.E001` | **Error** | `appkit.request_id.RequestIDMiddleware` is absent from `MIDDLEWARE`. | Every error envelope's `request_id` field silently reads `"-"`, and no log line correlates to any other — a debugging capability quietly missing, with no exception anywhere pointing at the cause. |
| `appkit.E002` | **Error** | `REST_FRAMEWORK["EXCEPTION_HANDLER"]` is unset, or still DRF's own default (`rest_framework.views.exception_handler`). | Every app's client expects the §1 envelope; without this wired, DRF's raw `{"detail": "..."}` shape ships instead, and different apps' clients silently disagree about error shape. |
| `appkit.W001` | Warning | `EXCEPTION_HANDLER` is set to something that is **neither** DRF's default **nor** `appkit.exceptions.standard_exception_handler`. | A host wrapping appkit's handler in its own (to add a field, say) is legitimate — this can't be an Error, only a nudge to confirm it's deliberate. **Silenceable** via Django's standard `SILENCED_SYSTEM_CHECKS`. |
| `appkit.W002` | Warning | `RequestIDMiddleware` is present but ordered **before** `SecurityMiddleware` in `MIDDLEWARE` (only evaluated when `SecurityMiddleware` is present at all). | Both scaffold docs and this contract's own wiring block specify the order; a swap doesn't crash anything; it just means the request ID is assigned before security headers are considered, which is order-of-operations debt worth flagging, not blocking. |
| `appkit.W003` | Warning | The host's `APPKIT` dict contains a key not present in `appkit.conf.DEFAULTS`. | A typo (`APPKIT = {"CACHE_TIMOUT": 30}`) would otherwise silently use the *default* `CACHE_TIMEOUT` forever, with the typo'd key simply ignored — exactly the class of bug `conf.py`'s whole design (§3.5) exists to prevent, closed the rest of the way by a check that actually looks at what keys were provided. |
| `appkit.W004` | Warning | A view reachable by walking `ROOT_URLCONF` declares a `throttle_scope` string with no matching entry in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`. | `APP-DESIGN.md` §7.4 names this exact failure by description: "a typo'd `throttle_scope` fails open, silently" — DRF only raises `AssertionError` for a missing rate at request time, per request, so it can ship to production and pass every test that doesn't happen to exercise that exact view under throttling. |
| `appkit.W005` | Warning | `settings.LOGGING` is configured (and `LOGGING_CONFIG` is not `None`), but no handler in it references a filter resolving to `appkit.request_id.RequestIDFilter` (or a subclass of it). Skipped entirely when `LOGGING` is unset/empty or `LOGGING_CONFIG is None`. | The middleware runs and the contextvar is set regardless, so nothing errors — but any handler reading the raw `LogRecord` (a `%`-style file handler, a mail-admins handler) stamps `request_id="-"` on every line forever. This is exactly the silent-degradation shape the other checks exist to catch, normally only discovered while correlating a production incident. |
| `appkit.W006` | Warning | Two independent conditions, both reported at this ID with distinct messages: (a) `REST_FRAMEWORK["NUM_PROXIES"]` is set and disagrees with `APPKIT["TRUSTED_PROXY_COUNT"]`; (b) `NUM_PROXIES` is unset (`None`, whether omitted or explicit) while any `SimpleRateThrottle` subclass is configured, globally via `DEFAULT_THROTTLE_CLASSES` or on any view reached by walking `ROOT_URLCONF`. | DRF's `SimpleRateThrottle.get_ident()` does its own `X-Forwarded-For` parsing that appkit has no way to inject `client_ip()`'s trusted-hop logic into. With `NUM_PROXIES` unset, `get_ident()` joins the **entire** header into the bucket key — not the untrusted leftmost entry, the whole chain — so a client prepending fake hops gets a fresh bucket on every request, making the throttle a no-op for exactly the client it exists to slow down. |

**`appkit.W004`'s detection scope, stated plainly so a clean run isn't misread as full
coverage.** Reliably detected: `throttle_scope` as a class attribute on a class-based view reached
via `pattern.callback.view_class` or `.cls` (DRF's `as_view()` sets both), including
`@api_view`-decorated function views (DRF wraps these in a real class). **Not detectable, and not
attempted:** a scope assigned at runtime inside `initial()`/`get_throttles()`, a viewset choosing a
scope per-action, or a scope on a plain function view with no DRF wrapper at all. **Also not
attempted, by design:** validating the scope's *naming format* — W004 checks registration only;
`appkit.throttling.throttle_scope` (§2.15) is the naming-convention half, and a scope W004 finds
no rate for is reported exactly the same regardless of whether it looks like `app_action` or not.

**Proposed, not implemented in this phase:** the reverse mismatch — a
`DEFAULT_THROTTLE_RATES` entry that no reachable view's `throttle_scope` ever uses. Usually a typo
or a leftover from a removed app, the same class of bug as W004's forward direction — recorded here
as an open proposal rather than added silently, for a decision in a future phase.

**`appkit.W006`'s trigger is deliberately every `SimpleRateThrottle` subclass, not only
`ScopedRateThrottle`.** An earlier draft of this check considered scoping it to
`ScopedRateThrottle` alone, since it pairs naturally with `appkit.throttling.throttle_scope`
(§2.15) — but the spoofable-bucket flaw lives in `SimpleRateThrottle.get_ident()` itself, and
every subclass inherits it unchanged: `AnonRateThrottle`, `UserRateThrottle`, and any host-defined
subclass are exactly as spoofable as `ScopedRateThrottle` with `NUM_PROXIES` unset. A host using
only `AnonRateThrottle` would have gotten silence from the narrower version for the identical
hazard. Detection resolves each configured class and checks `issubclass(cls, SimpleRateThrottle)`
rather than name-matching against DRF's own built-ins, specifically so a host's own subclass is
covered too.

**Two further scoping decisions, both leaving stated gaps rather than false confidence:**

- **A subclass overriding `get_ident` is excluded** — checked as `cls.get_ident is
  BaseThrottle.get_ident`, `True` for every DRF built-in and any subclass that doesn't touch it,
  `False` the moment one does. DRF's whole-header-join behaviour isn't in play for a class that
  parses `X-Forwarded-For` itself, and warning about it would be a false positive this check
  cannot resolve without re-implementing that subclass's own logic.
- **Throttle classes are gathered two ways**, sharing one `ROOT_URLCONF` traversal with
  `appkit.W004` (`_collect_throttle_info`): the raw `REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`
  setting, and each reachable view's own `throttle_classes` attribute — the second is what catches
  a host that sets `throttle_classes` directly on a view with no global default configured at all,
  which reading the raw setting alone would never see. **Not detectable, and not attempted**,
  matching W004's own stated limit: a throttle wired up via `get_throttles()` overridden at
  runtime, or via a permission class doing its own rate limiting outside DRF's throttle machinery
  entirely. A clean `appkit.W006` run is not proof neither exists somewhere.

**`appkit.W005` and §12's cut `LOGGING`-fragment constant are not the same thing, despite both
touching `LOGGING`.** The constant §12 rejected would have been appkit *shipping* a fragment of
host log-rendering policy — exactly what §4 keeps out. W005 ships no fragment and mandates no
rendering; it only inspects a `LOGGING` dict the host already chose to configure, warns rather than
errors, and is silenceable like every other warning here.

---

## 7. Settings and `.env` keys

```python
# backend/config/settings.py — optional; every key below has a documented default
APPKIT = {
    "CACHE_TIMEOUT": 60,                    # optional — cache_endpoint / CachedListMixin default
    "TRUSTED_PROXY_COUNT": 1,               # optional — trusted hops appended to X-Forwarded-For
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,   # optional — appkit.files' semantic size cap
    "SITE_URL": "",                         # optional-but-conditionally-required, see below
}
```

**Four settings keys, all read through `appkit.conf.get_setting` (§2.16), all optional at the
Python level.**

**`SITE_URL` is optional-but-conditionally-required** — the same shape of rule as §3's
`FERNET_KEY` reconciliation, stated here so the pattern reads as one deliberate design rather
than two unrelated defaults that happen to look alike:

> A host that never renders a media URL outside an active request cycle — no Celery-rendered
> emails, no background-task-generated links — never needs `SITE_URL`, and `appkit.media`'s
> functions (§2.11) are fully operational without it. It becomes required only the first time
> `file_url`/`absolute_url` is called with `request=None`, at which point its absence raises
> `ImproperlyConfigured` naming the setting directly, rather than emitting a broken relative URL
> that fails silently downstream (an email client, a mobile app) where nobody is positioned to
> notice.

**Zero `.env` keys — required or optional — under any installed extra.** This is a direct,
deliberate consequence of §3's decision on `FERNET_KEY` and holds regardless of whether a host
installs `hjtdev-appkit[crypto]`, `hjtdev-appkit[images]`, both, or neither: every credential/secret this
surface ever touches is an **app's** documented `.env` key, never appkit's own. Stated as the
single most valuable property of this contract, since `APP-DESIGN.md` §8 makes every declared
key something every host must go configure.

---

## 8. Host wiring block

Copy-pasteable as written — this becomes `README.md`'s config block and
`INTEGRATION-GUIDE.md` §2 step 5 verbatim once code exists.

```python
# backend/config/settings.py

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
    "CACHE_TIMEOUT": 60,
    "TRUSTED_PROXY_COUNT": 1,
    "MAX_UPLOAD_BYTES": 10 * 1024 * 1024,
    "SITE_URL": "",  # required only if any code path calls appkit.media with no request
}
```

```python
# backend/config/logging.py — the LOGGING dict's own filters/handlers wiring is UNCHANGED;
# only where these two names come from changes, from a local definition to an import:
from appkit.request_id import RequestIDFilter, request_id_var
```

```
# .env — nothing to add. appkit declares zero required or optional keys of its own.
```

**No URL mount section** — appkit ships no `urlpatterns` (§10). `README.md`'s eventual config
block states this explicitly rather than simply omitting the section, per §10.

---

## 9. Python dependencies (`H-backend`)

`APP-DESIGN.md` §1.1's range rule applied at maximum strictness: appkit is the single most
widely shared dependency in the entire ecosystem, so an exact pin here is the worst possible
place for one, full stop.

**Every figure below is verified against the PyPI JSON API and OSV.dev's vulnerability
database directly** — not recalled from training data — since a dependency decision this
consequential (every app's, every host's) deserves current numbers, not a guess.

| Package | Latest seen | Transitive deps | Wheel coverage | OSV advisories (lifetime) | Verdict |
|---|---|---|---|---|---|
| `django` | — | — | — | — | hard, platform (`>=5.2,<7.0`) |
| `djangorestframework` | — | — | — | — | hard, platform (`>=3.15,<4.0`) |
| `nh3` | 0.3.7 | **none** | Rust `abi3` wheels: manylinux, **musllinux** (Alpine), macOS, Windows; x86_64/aarch64/armv7l/i686/ppc64le/ppc64/s390x/riscv64. 0.6–1.5 MB. | **0** | **hard** (`>=0.2,<1.0`) |
| `puremagic` | 2.2.0 | **none** | `py3-none-any`, pure Python, no build step. 0.07 MB. | **0** | **hard** (`>=2,<3`) |
| `jdatetime` | 6.1.0 | `jalali-core>=1.0` (itself `py3-none-any`, ~10 KB, zero further deps) | `py3-none-any`. 0.01 MB. | **0** | **hard** (`>=5,<7`) |
| `cryptography` | 50.0.0 | `cffi>=2.0.0` | Platform wheels only, no any-platform wheel. 5.4 MB. | **42** | **extra `[crypto]`** (`>=42,<51`) |
| `pillow` | 12.3.0 | none at runtime | Platform wheels only, no any-platform wheel. 7.2 MB. | **153** | **extra `[images]`** (`>=10,<13`) |

### Per-library reasoning

**`nh3` — hard dependency.** The concern going in was that a Rust extension with no
any-platform wheel forces a compiler toolchain somewhere in the ecosystem's build matrix. The
verified wheel list rules that out directly: `abi3` wheels cover musllinux (Alpine, the
smallest/most common slim-container base) and every architecture a host plausibly runs, so
nothing compiles anywhere in practice. Combined with zero transitive dependencies and zero
advisories ever recorded, the cost argument for making it optional evaporates — and the
counter-argument for hard is concrete: an *optional* HTML sanitiser is a sanitiser some app
skips, and skipping it is a stored-XSS bug waiting for whichever app decided sanitisation wasn't
worth the extra. Alternatives considered: `bleach` (maintenance-mode; its own current
documentation recommends nh3 as the successor), `lxml_html_clean` and `html-sanitizer` (both
pull in `lxml` + `libxml2` — strictly worse on every one of the three axes above).

**`puremagic` chosen over `filetype`; `python-magic` disqualified outright.** `python-magic`
requires the system `libmagic` shared library, which `python:*-slim` and Alpine base images do
not ship by default — precisely the "works on a developer's machine, `OSError` at runtime in
whatever container the host actually deploys" failure mode, unacceptable for a dependency that
installs into an arbitrary, unknown host's image. Between the two pure-Python contenders:
`filetype` is smaller (20 KB) and functionally adequate, but its last release was version 1.2.0
in 2022 — effectively dormant. `puremagic` (70 KB) is actively maintained through its 2.x line
and carries a larger signature database. Fifty extra kilobytes buys an upstream that still
responds to new file-format signatures.

**`jdatetime` — one thing corrected in this contract rather than left implicit:** it is **not**
dependency-free, as an earlier draft of this section assumed before verification. It pulls in
`jalali-core>=1.0`, which is itself trivial (pure Python, `py3-none-any`, ~10 KB, no further
dependencies of its own) — worth naming explicitly here rather than letting whoever runs
`uv tree` at Phase 1 discover a second package they weren't expecting. Range set to `>=5,<7`
against the verified current `6.1.0`; `APP-DESIGN.md` §10.1's `resolution-matrix` job's
`lowest-direct` leg is what actually proves a `5.x` resolution still passes the suite — if it
doesn't, Phase 1 narrows the floor to `>=6,<7` rather than shipping an unverified lower bound.
Runner-up `persiantools` (6.2.0, 30 KB, genuinely zero dependencies, zero advisories, actively
maintained) would hand us digit conversion for free and was seriously considered — rejected only
because `jdatetime`'s API mirrors the stdlib `datetime` module directly, which keeps
`appkit.dates`'s internal wrapper thinner than adapting a differently-shaped API would.
Also rejected: `convertdate` (drags in `pymeeus`), `khayyam` (unmaintained since 2016, C
extension — the exact `libmagic`-style deployment risk again), `django-jalali` (a model-field
library — structurally out of scope, since appkit ships no models at all).

**`cryptography` and `pillow` — extras, and the advisory counts alone make the case.** 42 and
153 lifetime advisories respectively, against zero for every hard dependency above; each is
also 5–7 MB with no any-platform wheel, meaning every host resolves a platform-specific binary
for a capability it may never use. These are precisely the dependencies an app should have to
ask for by name, not receive by default through a transitive chain nobody chose.

### Extras — mechanics, all of which are part of this contract, not implementation detail

```toml
[project.optional-dependencies]
crypto = ["cryptography>=42,<51"]
images = ["pillow>=10,<13"]
```

- **A missing extra fails with an actionable message, never a bare `ImportError`.** Both
  `appkit.crypto` and the Pillow-dependent path of `appkit.files.validate_image` import their
  extra lazily, inside the function/module that needs it, wrapped in
  `try/except ImportError`, re-raised naming the exact fix
  (`Install with: uv add "hjtdev-appkit[crypto]"` / `pip install "hjtdev-appkit[crypto]"`). **This error path
  itself is unit-tested** by simulating the missing import — a broken error message is otherwise
  only ever discovered by whoever actually hits it in production.
- **The base-scaffold interaction is stated explicitly, so nobody assumes an isolation that
  doesn't exist:** `BASE-DESIGN.md` §4.2 already makes `cryptography` a **hard host**
  dependency, for `tools/crypto.py`'s own `FERNET_KEY`-backed cipher — meaning a standard
  scaffold-based host has `cryptography` installed regardless of whether any installed app ever
  declares `hjtdev-appkit[crypto]`. The extra's real, narrower benefit: (a) an app that never encrypts
  anything doesn't itself declare the dependency, keeping its own footprint honest, and (b) a
  project that strips crypto out of the base scaffold entirely (a project with no field-level
  encryption need at all) can actually avoid pulling `cryptography` in through appkit.
- **Extras compose:** `hjtdev-appkit[crypto,images]` is a valid, expected install for an app needing
  both. Each extra gets one line in `README.md`'s installation section naming what it enables
  and who needs it.
- **CI gains a bare-install matrix leg** (extending `APP-DESIGN.md` §10.1's existing
  `resolution-matrix` job): install `appkit` with **neither** extra and run the full suite. This
  is what proves the core surface imports cleanly with neither optional dependency present, and
  that the missing-extra error messages are the intended clear ones rather than untested
  aspiration — nothing today would catch a stray top-level `import cryptography` anywhere in
  appkit's own code quietly making an extra mandatory in practice despite `pyproject.toml`
  saying otherwise.

**The two-leg test strategy is itself part of this contract, not an implementation detail —**
stated here explicitly so an app consuming `hjtdev-appkit[crypto]`/`hjtdev-appkit[images]` understands that
appkit's own guarantees about those extras come from a *specifically configured* run, not from
`uv run pytest` alone:

- **Gate leg (authoritative, ≥95% coverage):** `uv run --extra crypto --extra images pytest`.
  Extras-dependent tests carry a `requires_extra` pytest marker and import their extra at
  module level with a plain `import` — never `pytest.importorskip` — so a misconfigured gate
  run fails loudly (a collection error) rather than silently passing with the security-relevant
  crypto/image tests absent. A `pytest_configure` guard in `tests/backend/conftest.py` checks
  both extras are importable before collection even starts, for the same reason.
- **Bare-install leg (proves the core stands alone):**
  `uv run --exact pytest -m "not requires_extra" --no-cov`. `--exact` matters: `uv run` syncs
  *inexactly* by default, so without it a prior gate run's `cryptography`/`pillow` stay
  installed and this leg silently runs with both extras present anyway.

### Deliberately not depended on

`drf-spectacular` (every app declares it directly; nothing in appkit introspects an OpenAPI
schema), `python-decouple` (§3's decision leaves no `.env` key for appkit to read, ever),
`structlog` (§4's decision — log rendering is host policy), `celery`/`redis`-as-a-client-library
/`django-filter` (no task runner, no direct Redis client beyond Django's own cache API, no
generic filtering framework — see `README.md`'s existing "what appkit deliberately does not
provide").

**No third-party type leaks into any public signature**, restated as a dependency-hygiene rule
rather than a per-module note: `appkit.dates` takes/returns stdlib `date`/`datetime`/`str` only
(`jdatetime`/`jalali-core` stay internal); `appkit.files.detect_mimetype` returns a plain `str`
(`puremagic` stays internal); `appkit.validation.sanitize_html` returns a plain `str` (`nh3`
stays internal). A major-version bump in any of these three dependencies can therefore never
force an appkit major bump on its own — it's an internal implementation swap, invisible to
every consumer's type checker.

---

## 10. What appkit deliberately does not contain

An explicit section, mirrored into `README.md`'s wiring block once code exists — because in an
ecosystem where every other app package has a URL mount, a `services.py`, and a settings dict
full of required keys, an *absence* here reads as an oversight unless it's stated as a decision.

- **appkit exposes no `urlpatterns` and is never `include()`d anywhere, by any host.** Stated
  positively, not just left off the standard-items table (§0 item 4) — a reader scanning for the
  URL-mounting section of appkit's eventual README should find a line saying so, not silence
  where every other app's README has a code block.
- **Module-name collision audit against Django/Celery/DRF auto-discovery conventions —
  performed, one legitimate hit, everything else confirmed absent:**

  | Name | Auto-discovered by | Status in appkit |
  |---|---|---|
  | `apps.py` | Django app loading | **Present** — legitimate, exists precisely because §5 confirms `INSTALLED_APPS` membership. |
  | `models.py` | Django app loading (`makemigrations` et al.) | Absent — no persistent state (§0 item 1). |
  | `admin.py` | `admin.autodiscover()` | Absent — no models to register. |
  | `views.py` / `serializers.py` | Convention, not auto-discovery, but every app-package reader expects them | Absent — no endpoints (§0 item 4). |
  | `signals.py` | Convention via `ready()` | Absent — no events (§0 item 2). |
  | `urls.py` | `include()` | **Deliberately absent** — see above; this is the name a host might most plausibly guess wrong. |
  | `factories.py` | `APP-DESIGN.md` §7.3's third public test surface | Absent — no models means nothing to factory. |
  | `migrations/`, `templatetags/`, `management/` | Django app loading / template engine / `manage.py` | Absent. |
  | `tasks.py` | **Celery's `autodiscover_tasks()`**, walking every `INSTALLED_APPS` entry | **Deliberately, permanently absent — see below.** |
  | `checks.py` | *Not* auto-discovered by Django | Present, safe — registered explicitly from `AppKitConfig.ready()` (§5), never picked up implicitly. |

  `tasks.py` is the sharpest trap on this list, and **§5's own "yes" to `INSTALLED_APPS` is what
  makes it sharp**: before that decision, an `appkit/tasks.py` would just be a file nobody
  imports. After it, `celery.autodiscover_tasks()` (which every `BASE-DESIGN.md`-based host runs,
  walking every `INSTALLED_APPS` entry) would pick up any `appkit/tasks.py` **automatically**,
  turning appkit into a task producer silently, directly contradicting `README.md`'s explicit
  "no Celery / `django.tasks`" stance. Recorded here as a standing constraint on every future
  session touching this package, not merely today's absence.
- **No `factories.py`**, since appkit defines no models at all — `APP-DESIGN.md` §7.3's
  third public test surface is genuinely not applicable here, and §10.1's CI
  `no-inter-app-imports` job's factories-import grep has nothing in this package to ever match.

---

## 11. Scope review — what's here, what almost wasn't, why nothing survives on one app's behalf

- **`appkit.text` and `appkit.money` are this contract's two weakest modules**, named as such
  rather than smoothed over. `appkit.text` survives past `truncate` alone (which
  `django.utils.text.Truncator` already provides) only because session 2's frontend ships a
  matching `truncate`, and matching client/server truncation is worth one small shared function;
  `to_english_digits`/`to_persian_digits` earn their place independently, since
  `parse_jalali`/`parse_amount` both depend on them internally and no stdlib equivalent exists.
  `appkit.money` stays at exactly two functions, zero dependencies — a deliberate ceiling against
  ever growing into a currency/locale framework.
- **Nothing in this surface survives because exactly one future app wants it.** Every module
  was checked against "would a second and third app independently need this," not merely the
  first app that happens to get built. `services.py`-shaped domain logic, anything ledger- or
  order-specific, and anything ORM-model-shaped were all rejected on this basis during review.
- **Four additions beyond the session prompt's original module inventory — all confirmed and
  built into §2 above, not appended as an afterthought:** `IsObjectOwner` (§2.6),
  `appkit.W004`/the throttle-scope check (§2.15, §6), `to_english_digits`/`to_persian_digits`
  (§2.12), and `appkit_assert_error_envelope` (§2.17). Each maps directly to a specific requirement
  `APP-DESIGN.md` §7.4 or §9 already places on *every* app, which is the bar an addition to this
  surface has to clear — "convenient" is not that bar; "every app is already required to do this
  and would otherwise reimplement it nine times" is.

---

## 12. Self-review against `CLAUDE-CODE-GUIDE-APP.md` §2

- **Is every signature minimal?** Checked per entry; every optional keyword argument in §2 maps
  to a specific documented failure it exists to prevent (`per_user` → cross-user cache leakage;
  `allow_relations` → filter-based data exfiltration; `allow_svg` → an XML script-execution
  vector). Candidates that could not clear that bar were cut during drafting rather than left
  in "for completeness": a standalone `get_request_id()` accessor (redundant with the public
  `request_id_var` itself), `IsAppAdminOrReadOnly` (a composition any app can write in three
  lines from `IsAppAdmin`), a `LOGGING`-fragment constant (would re-couple appkit to the exact
  host policy §4 keeps out), a separate `ErrorCode` enum living alongside the `ERROR_CODES`
  tuple (one representation of the same ten values, not two), and a per-app custom error code
  mechanism (rejected in §1 — `details` is where domain-specific identity belongs). **Not the
  same cut as `appkit.W005` (§6):** the rejected constant would have *shipped* a piece of host
  log-rendering policy; W005 ships nothing and mandates no rendering, it only inspects a
  `LOGGING` dict the host already configured and warns, silenceably, if it's missing one wire.
- **Would a consuming app use each helper without reading its source?** Applied as a literal
  test per entry, and two failed it on first pass — fixed here rather than merely documented
  around, per this same guide's instruction to treat that as a shape problem, not a docs
  problem: `cached_call`'s original `timeout=None` was ambiguous between "no timeout" and "use
  the default" (resolved with the `UNSET` sentinel, §2.1), and `namespace_version`'s return
  value silently changed meaning when the seeding strategy changed (resolved by documenting it
  as opaque rather than leaving the old "starts at 1" assumption implicit, §2.1).
- **Is anything reaching outside?** No `tools.*` import, no `core.*` import, no import of any
  app package, and no assumption about a host beyond the four documented `APPKIT` keys (§7) —
  checked against every module in §2. The one place a host's own app (the auth system) is even
  referenced is `appkit.testing`'s use of `get_user_model()`, which is Django's own sanctioned
  indirection (`APP-DESIGN.md` §2's "Referencing the host's user model"), not a concrete import.

---

*End of backend contract.*

---

# Frontend contract (Session 2 of 2)

`appkit`'s TypeScript SDK — the `HttpClient` interface, the shared provider/hook pair, and the
pure utilities every installed app's own frontend package depends on. Written to the same
discipline as the backend half: every entry below is something that cannot change without a
**major** version bump (`CLAUDE.md`'s Semver triggers), stated with its full signature, its
failure path, and — where it deviates from a source document — the reasoning for the deviation.

Source material read, not modified — a separate project; findings against it are flagged inline
rather than fixed there:

- `../base-scaffold/frontend/lib/api-client.ts` — the fetcher every host page (and every
  installed app's own low-level client, per `BASE-DESIGN.md` §3/§8.1) plugs into today.
- `../base-scaffold/frontend/lib/query-client.ts` — the shared `QueryClient` factory.

---

## 13. The boundary, stated before any signature

appkit's frontend half is **three things**: the `HttpClient` **interface** (§14), the shared
`ApiClientProvider`/`useApiClient` **pair** (§15), and a set of **pure utilities** (§17–§18) that
take their inputs as arguments and touch nothing ambient. It is **not**: a client
implementation, a `fetch` call, a reader of `process.env`/`NEXT_PUBLIC_*`, or a token store.

> appkit never reads, stores, refreshes, or inspects a token. It invokes opaque callbacks the
> host supplies and merges their output into request headers.

The host keeps constructing the real client — it reads `NEXT_PUBLIC_API_URL`, handles CSRF,
decides the credentials mode, all host configuration (`APP-DESIGN.md` §12,
`BASE-DESIGN.md` §3) — and injects it through the provider. An appkit-shipped client
implementation would have to read the host's environment itself, which is exactly the coupling
this architecture exists to prevent.

**Standing trigger for every future session touching this half:** if any part of this contract
starts requiring appkit to know a URL, a token, or an env var, that's the boundary being
crossed. Stop.

---

## 14. `HttpClient` — the injected interface

```ts
export interface HttpClient {
  get<T>(path: string, init?: RequestInit): Promise<T>;
  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  patch<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  delete<T>(path: string, init?: RequestInit): Promise<T>;
}
```

**Public.** Five methods — **a deliberate deviation from `APP-DESIGN.md` §12's excerpt**, which
lists only `get`/`post`/`patch`/`delete`. `put` is added because:

1. The scaffold's own `ApiClient` (`api-client.ts:197-203`) already implements it — including it
   here costs the scaffold zero changes.
2. An SDK wrapping a DRF `ViewSet`'s full-update action (`PUT`, distinct from `PATCH`'s partial
   update) needs to express it. Without `put` in the interface, that SDK either can't type its
   manager method against `HttpClient` at all, or reaches for `request()` — which isn't part of
   this interface (below) — defeating the point of a typed contract.
3. Adding a required method to `HttpClient` **after** v1.0.0 ships is a MAJOR bump for every host
   whose concrete client doesn't yet implement it. Getting the method count right now, while the
   only cost is "one more line," is cheaper than a future major bump forcing every host to add a
   `put` they may not have needed yet.

**`request()` is deliberately not part of this interface.** It's the host implementation's own
internal method (`api-client.ts:110-183` is the whole reason `get`/`post`/`put`/`patch`/`delete`
can be this thin) — exposing it here would make the interface leak implementation shape instead
of describing behaviour.

**Structural satisfaction, not nominal.** TypeScript is structurally typed, so the scaffold's
concrete `ApiClient` satisfies `HttpClient` by having the right methods — no `implements`
declaration, no import of appkit's type required in the host's own `api-client.ts` for this to
type-check (`APP-DESIGN.md` §12, "SDK-to-host client contract").

---

## 15. `ApiClientProvider` / `useApiClient`

```ts
export interface ApiClientProviderProps {
  /** Any client satisfying HttpClient — normally the host's frontend/lib/api-client.ts
   *  apiClient, passed in as-is. */
  client: HttpClient;
  /** basePath per installed app, keyed by the app's own namespace (§1.2 of APP-DESIGN.md). */
  basePaths?: Record<string, string>;
  /** Composable per-request header sources — see §16. Must be a stable reference; see the
   *  memoisation contract below. */
  headerSources?: ReadonlyArray<HeaderSource>;
  children: React.ReactNode;
}

export function ApiClientProvider(props: ApiClientProviderProps): React.ReactElement;

/** Called from an app's own api/config.ts, never directly by a host. `key` is this app's
 *  namespace; `defaultBasePath` is what the app's own README suggests if the host's
 *  basePaths map has no entry for `key`. Both arguments are REQUIRED. */
export function useApiClient(
  key: string,
  defaultBasePath: string,
): { client: HttpClient; basePath: string };
```

Both **Public.**

- **`defaultBasePath` is required, no default** — the same "no host-wide-safe default" reasoning
  §2.2's `cache_namespace` already establishes on the backend half. A missing or typo'd entry in
  the host's `basePaths` map falls back to **the calling app's own default**, never to `""` or
  `/`; there is no code path in which a `basePath` resolves to something that would make a
  manager method's `${basePath}/...` construct a same-origin root request. `useApiClient` throws
  a descriptive error at call time if `defaultBasePath` is empty — a programming error inside the
  calling app, not a host-facing failure.
- **Normalisation:** a trailing slash on either the resolved `basePath` or a manager's own
  leading slash is stripped before concatenation, so `basePath + path` can never produce a
  double slash. Documented once here rather than per-app, since every SDK's manager relies on it.
- **The provider-missing error names the file to edit, not just the failing hook** — this is the
  literal requirement, not paraphrased:
  ```
  useApiClient("notifications") was called outside an <ApiClientProvider>. Mount it once in
  frontend/app/providers.tsx — see appkit's README, "Usage — mounting the shared provider".
  ```
  Deliberate, matching `APP-DESIGN.md` §12's own reasoning: a hook that silently returned
  `client: undefined` would fail three layers away, inside a `fetch` call, with an error that
  says nothing about a missing provider.
- **The context object itself is not exported.** A host (or a confused app) cannot construct a
  second `ApiClientProvider`-compatible context by hand — `ApiClientProvider` and `useApiClient`
  are the only two ways to reach it, matching the "one entrypoint" rule (§21).
- **Memoisation contract, stated as a failure path with a mandatory test:** the client
  `useApiClient` returns is the injected `client`, decorated once with `headerSources` merging
  (§16), memoised on `[client, headerSources]`. **A host passing an inline array literal
  (`headerSources={[...]}`) as a JSX prop defeats this memoisation** — a new array identity every
  render invalidates every installed app's own `useMemo`'d manager (`APP-DESIGN.md` §12,
  "Manager & hook conventions"), reconstructing it on every render. Test: render with a stable
  `headerSources` ref across two re-renders and assert the manager instance is referentially
  unchanged; render with an inline array and assert it is **not** — the second case documents the
  footgun rather than silently tolerating it.
- **`basePaths` trade-off, restated from `APP-DESIGN.md` §12, not reopened:** the key is
  stringly-typed and unenforced by the compiler. A typo in the host's map silently falls back to
  the calling app's own default rather than failing to build — mitigated by each app's README
  documenting its exact key, and by `INTEGRATION-GUIDE.md` §2 step 11 making it an explicit
  wiring step. Escape hatch for an app needing a differently-configured client (an auth app on
  `credentials: "include"`): nest a second `ApiClientProvider` deeper in the tree; the same React
  context resolution rules that make this work for any context make it work here.

---

## 16. Header injection — merge semantics

```ts
export type HeaderSource = () => HeadersInit | Promise<HeadersInit>;
```

**Public** (the type; sources themselves are host/app-supplied, never appkit's). The mechanism a
host uses to attach per-request headers — the future JWT app's `Authorization` header being the
motivating case — without appkit knowing anything about auth. Left unspecified, this is exactly
the kind of decision that gets made ad hoc by whoever writes the first app that needs it; stated
here so it's made once, correctly, for every app that ever needs it after.

Requirements, made mechanical rather than left to convention:

1. **Order and precedence.** `headerSources` are invoked **left-to-right**; a manager's own
   `init.headers` for that call is applied **last**. Later always wins over earlier. This is what
   lets two independent sources — an auth app's `Authorization` and a tenant-scoping app's
   `X-Tenant-ID`, say — compose without either one having to know the other exists.
2. **Normalisation.** All three `HeadersInit` forms a source or `init.headers` may produce
   (a plain object, an array of `[name, value]` pairs, or a `Headers` instance) are normalised
   through the `Headers` constructor before merging — a source is free to return whichever shape
   is most convenient for it.
3. **Case-insensitive keys.** Header names are compared case-insensitively during the merge, so
   `authorization` from one source and `Authorization` from another/`init.headers` collapse to
   **one** header (the later value), never two headers with the same semantic name reaching the
   wire. `Headers` already gives this for free once normalised through it — stated explicitly
   here because it's the property a hand-rolled object-spread merge (`{...a, ...b}`) would get
   wrong for `Authorization` vs `authorization`.
4. **Failure is fatal, not silent.** A source that throws synchronously or returns a rejected
   promise **fails the request** — the decorated client's call rejects before the underlying
   `client.get/post/...` is ever invoked. The rejection is wrapped naming which source failed
   (by array index, since sources are anonymous functions):
   `Header source #1 threw while building request headers: <original error>`.
   **Non-obvious failure path, the reason this rule exists:** a source that silently drops out on
   error (the request proceeding without its header) turns a wiring bug into a **401 that reads
   like an auth bug** — the caller debugs "why did my token expire" when the real cause is "the
   header source threw and got swallowed." Failing loudly keeps the two failure classes distinct.
5. **Async is supported.** Sources are awaited **in order**, not raced — a JWT app's source doing
   a synchronous refresh-if-expired check before returning `{ Authorization: ... }` is the
   motivating shape, and ordering guarantees a later source can rely on an earlier one having
   already resolved (e.g. a logging header that reads a value an auth source set into a shared
   in-memory store as a side effect — discouraged in general, but not made impossible by racing).
6. **No retry-on-401 anywhere in this mechanism.** See §J — a source can build a fresh header
   from already-valid state, but *detecting* a 401 and retrying the call is explicitly the host
   client's responsibility, not something `headerSources` or the decorator wraps.

**Mandated tests**, the composition surface being exactly what a hand-written per-app
implementation would get wrong piecemeal: two sources with overlapping keys (later wins); two
sources whose overlapping key differs only in case (still collapses to one header); one async
source; one source that throws (request rejects, others' headers never reach the wire); a call's
own `init.headers` overriding both sources; and an MSW-backed test asserting the merged header
actually arrives on the wire request, not just that the merge function returns the right object.

---

## 17. `ApiError`, the envelope types, and the pure parsing helpers

```ts
/** The ten codes from the backend contract's §1, verbatim and in the same order. Exhaustive —
 *  a `switch (error.code)` over this union type-checks against the real, closed set. */
export type ApiErrorCode =
  | "validation_error"
  | "parse_error"
  | "not_authenticated"
  | "authentication_failed"
  | "permission_denied"
  | "not_found"
  | "method_not_allowed"
  | "throttled"
  | "server_error"
  | "error"; // the documented catch-all — see §1's four rules, reproduced below

/** This client's own code for a response that isn't the envelope at all (an nginx error page,
 *  a truncated body, a non-JSON 500) — kept OUT of ApiErrorCode so that union stays a true,
 *  unmodified mirror of the ten codes the backend actually emits. */
export type ClientErrorCode = "unknown_error";

export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode;
    message: string;
    details: Record<string, unknown>;
    request_id: string | null;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | ClientErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;
  readonly retryAfter: string | null;
  /** The raw, un-parsed response body — present only on the ClientErrorCode ("unknown_error")
   *  path, so a caller debugging "the server sent something weird" doesn't have to reproduce
   *  the request to see what it actually was. */
  readonly body?: unknown;
  /** The raw wire value of `error.code` when it fell outside the closed ApiErrorCode set —
   *  `null` for every known code. Only apiErrorFromEnvelope ever sets this (see below). */
  readonly unrecognizedCode: string | null;

  constructor(
    message: string,
    options: {
      status: number;
      code: ApiErrorCode | ClientErrorCode;
      details?: Record<string, unknown>;
      requestId?: string | null;
      retryAfter?: string | null;
      body?: unknown;
      unrecognizedCode?: string | null;
    },
  );
}

/** Brand check, not `instanceof` — still correct if two copies of appkit ever land in one
 *  tree (§21's duplicate-copy safeguard), since `instanceof` across two module instances of
 *  the same class fails even for a "real" ApiError. */
export function isApiError(value: unknown): value is ApiError;

/** Pure. Validates, does not assume: `data` must be an object with an `error` object whose
 *  `code` is a non-empty string, `message` is a string, `details` is an object, and
 *  `request_id` is a string or null. Deliberately forward-compatible on `code` — a value
 *  outside the ten-member ApiErrorCode union still passes, so a host on an older minor keeps
 *  message/details/request_id when the backend emits a code this SDK doesn't know yet (see
 *  the narrowing note below). */
export function isApiErrorEnvelope(data: unknown): data is ApiErrorEnvelope;

/** Pure. Never throws while constructing an error — a non-envelope `body` (HTML, empty,
 *  null, valid-JSON-non-envelope) produces a well-formed ApiError with code "unknown_error"
 *  and `body` set to the raw input. A well-shaped envelope with a `code` outside the ten is a
 *  third case: `code` degrades to "error" (the documented catch-all) while `message`/
 *  `details`/`request_id` are preserved exactly as a known code would be, and the raw value
 *  survives on `unrecognizedCode`. */
export function apiErrorFromEnvelope(input: {
  status: number;
  body: unknown;
  requestId: string | null;
  retryAfter: string | null;
}): ApiError;
```

All **Public.**

- **Mirrors §1's envelope character-for-character**, including the four rules about `"error"`
  being the documented catch-all — reproduced in `ApiErrorCode`'s own doc comment (matching this
  document's own §1 rule 4: the union carries all ten values with no fallthrough case, "not only
  in prose"). **This is the drift-correction §1 already made, now load-bearing on this half
  too**: a frontend contract that shipped a nine-member union would be the exact bug the backend
  session found and fixed, reintroduced from the other side.
- **Purity is a rule, not a property of today's implementation.** `isApiErrorEnvelope` and
  `apiErrorFromEnvelope` import nothing beyond `ApiErrorCode`/`ApiErrorEnvelope`/`ApiError`
  themselves — no `fetch`, no `Response`, no `baseUrl`, no `process.env`. This is what keeps
  these two functions on the interface side of §13's boundary: they operate on **already-fetched
  data** (a status code, a parsed-or-unparsed body, header values the caller already read), never
  on a live request. A future session adding a `fetch` call to either function is the boundary
  violation §13 warns about, concretely.
- **`isApiErrorEnvelope` validates shape, not the closed code set** — the literal requirement:
  `data` must be a non-null object with an `error` property that is itself an object;
  `error.code` must be a **non-empty string** (not necessarily a member of the ten-value
  `ApiErrorCode` union); `error.message` must be a string; `error.details` must be an object;
  `error.request_id` must be a string or `null`. **This is a deliberate change from an earlier
  version, which rejected the whole envelope on an unrecognised `code`.** README documents that
  a future minor version may carve a new, more specific code out of `"error"` (§1's four rules)
  — a host on an older minor still needs to parse that response, and rejecting the envelope over
  the one field it doesn't recognise yet threw away `message`/`details`/`request_id` too, not
  just the code. A malformed or third-party body (a proxy emitting its own
  `{"error": {"code": "gateway_timeout", ...}}` shape, say) is still rejected if `code` is
  missing, non-string, or empty — this only widens what counts as a *recognised shape*, not what
  counts as *no shape at all*.

  **This is a narrow, deliberate unsoundness against the `data is ApiErrorEnvelope` return
  type**: `error.code` is typed as the closed `ApiErrorCode` union, but a value outside that
  union can genuinely reach here at runtime once this guard passes. It's safe in practice
  because the one caller every host is expected to use, `apiErrorFromEnvelope` below, normalises
  any such value to `"error"` before it can escape as a typed `ApiErrorCode` — so a
  `switch (apiError.code)` downstream stays exhaustive. A caller invoking this guard directly and
  trusting `envelope.error.code` as a union member without re-checking inherits this narrowing.
- **`apiErrorFromEnvelope` never throws while constructing an error** — this is the single most
  important behaviour in this module, matching the framing of the backend's most important
  per-module test (§2.9's `file_url` seek-restore). A parser that can itself throw on the
  malformed-input path it exists to handle turns "the server returned something unexpected" into
  an unhandled exception three layers from the actual problem — the same failure shape §15's
  provider-missing error and §16's header-source-failure both exist to prevent by naming the
  cause instead. Header-derived values (`requestId`, `retryAfter`) are **read by the caller**
  (the host's concrete client, which has the live `Response`) and passed in — this function never
  touches `Response` itself, keeping it pure per the rule above.
- **A well-shaped envelope with an unrecognised `code` is a third outcome, distinct from both
  the success path and `"unknown_error"`.** `code` degrades to `"error"` — the same catch-all a
  future specific code would have been carved out of — while `message`, `details`, and
  `request_id` are preserved exactly as a known code would be; the raw wire value survives on
  `ApiError.unrecognizedCode` (`null` for every known code), so a caller that cares can still
  tell "a code we don't have a name for yet" apart from an ordinary `"error"` response, without
  that distinction ever leaking into the `code` union itself. Falling through to
  `"unknown_error"` — which loses `message`/`details`/`request_id` — is reserved for a body that
  isn't the envelope shape at all.
- **Mandated tests, the exact adversarial-input list, not a happy-path sample:** an HTML body (an
  nginx error page), an empty body, `null`, valid JSON that isn't an envelope shape at all, a
  well-formed envelope with a `code` outside the ten (must pass `isApiErrorEnvelope` and degrade
  to `"error"` with `unrecognizedCode` set and `message`/`details`/`request_id` intact — not fall
  through to `"unknown_error"`), an envelope missing `details` (still correctly rejected — this
  is a shape failure, not a code failure), and a 204 (empty body, success status —
  `apiErrorFromEnvelope` is never called on this path by a correctly-written caller, but the
  function itself must not crash if it somehow is).
- **Follow-up flagged for the base-scaffold, not applied here (separate repo, outside this
  session's scope):** `../base-scaffold/frontend/lib/api-client.ts` currently parses the envelope
  inline (`isEnvelope`, lines 63-67) and declares its own `ApiError` (lines 29-54) rather than
  importing appkit's. Once appkit v1.0.0 ships, the scaffold's `ApiClient.request()` should call
  `isApiErrorEnvelope`/`apiErrorFromEnvelope` and construct appkit's `ApiError`, so the host and
  every installed SDK's retry predicate (§20) agree on what an error *is* via one class, not two
  structurally-similar ones. The same file's doc comment (line 21) also states "nine" codes —
  the identical drift §1 already corrected on the backend half, now visible on this one too.

---

## 18. Utilities that must agree with the backend

```ts
export function truncate(value: string, length: number, suffix?: string): string; // suffix default "…"
export function toEnglishDigits(value: string): string;
export function toPersianDigits(value: string): string;

export function parseAmount(value: string | number): number;
export function formatAmount(value: number, currency?: string): string; // currency default ""

export interface JalaliDate { year: number; month: number; day: number; }
export function toJalali(value: string | JalaliDate): JalaliDate; // string is "YYYY-MM-DD"
export function fromJalali(value: JalaliDate): string; // returns "YYYY-MM-DD"
export function formatJalali(value: JalaliDate, fmt?: string): string; // fmt default "%Y/%m/%d"
export function parseJalali(value: string, fmt?: string): JalaliDate;
/** The explicit bridge from an instant to a calendar date in a given zone — see the timezone
 *  rule below. `timeZone` is a required IANA name; there is no default. */
export function calendarDateIn(instant: Date | string, timeZone: string): JalaliDate;

export function mediaUrl(value: string | null | undefined, baseUrl: string): string | null;
```

All **Public.** Each mirrors a §2.11–§2.14 backend counterpart; the pairing and where behaviour
must match, stated per function rather than assumed from the name:

- **`truncate` ↔ §2.12's `truncate`.** Same suffix default (`"…"`), same total-length-including-
  suffix counting rule (`truncate("hello world", 8)` → `"hello w…"`, matching the backend
  example exactly), same degenerate case (`length <= suffix.length` returns the clamped suffix).
  **Counts Unicode codepoints, not UTF-16 code units** — implemented via `Array.from(value)`,
  never bare `.length`/`.slice()` indexing, because a string containing an astral character (most
  emoji, some combining sequences) has `.length` values that disagree with Python's `len()` on
  the identical string. **Non-obvious failure path, mandatory test:** truncating a string
  containing an emoji or a combining character must produce the same character-count result a
  Python `len()`-based truncation of the identical string would, not a UTF-16-unit-based one that
  can split a surrogate pair mid-codepoint.
- **`toEnglishDigits`/`toPersianDigits` ↔ §2.12's identical pair.** Same two source digit sets
  (Persian `۰۱۲۳۴۵۶۷۸۹`, Arabic-Indic `٠١٢٣٤٥٦٧٨٩`), same pass-through-unrecognised-characters
  behaviour, never raises. Used internally by `parseAmount` and `parseJalali`, exactly mirroring
  how `appkit.money.parse_amount`/`appkit.dates.parse_jalali` use their Python counterparts
  internally (§2.12).
- **`parseAmount` ↔ §2.14's `parse_amount` — the one place JS's lack of an int type forces a
  documented divergence in *shape*, not in *intent*.** Accepts a digit string (Persian/
  Arabic-Indic digits normalised via `toEnglishDigits` first) or a `number`, strips thousands
  separators (`,`/`٬`). **Rejects a non-integer `number` outright, throwing `TypeError`** —
  mirroring the backend's float rejection, since JS has no separate int/float type and a
  currency amount arriving as `12000.5` is the identical defect-in-the-caller case §2.14
  documents, just detectable via `Number.isInteger` instead of `isinstance(value, float)`.
  **Additionally throws `RangeError`** for a value (or a parsed string) exceeding
  `Number.MAX_SAFE_INTEGER` — the backend's `int` has no such ceiling, so this is a real
  divergence, stated rather than hidden: a JS caller handling an amount near or beyond 2^53 must
  keep it as a string end-to-end and never round-trip it through `parseAmount`/`formatAmount`.
  **Raises the same `ValueError`-equivalent (a plain `Error`)** for a string that isn't a valid
  integer after normalisation.
- **`formatAmount` ↔ §2.14's `format_amount`.** Same thousands-grouping shape
  (`1000000` → `"1,000,000"`, `"1,000,000 IRT"` with `currency: "IRT"`), same never-raises
  contract including negative values and `0`. **Uses an explicit ASCII `,` separator, never
  `Intl.NumberFormat`** — `Intl.NumberFormat`'s grouping character is locale-dependent (a
  `fa-IR` locale renders `٬`, a `de-DE` locale renders `.`), and a locale-dependent formatter
  here would make the *same* `formatAmount(1000000)` call render differently across two
  browsers, disagreeing with the backend's fixed-format `format_amount` for no reason tied to the
  actual data. **Digits:** both halves emit **Latin** digits by default in this function;
  `toPersianDigits` is an explicit, separate call a caller makes on the *result* if
  Persian-digit rendering is wanted — keeping `formatAmount`'s own contract fixed regardless of
  locale.
- **Jalali conversion — the four core functions plus the explicit timezone bridge.** No
  third-party or ambient-clock type in any signature — `toJalali`/`fromJalali`/`formatJalali`/
  `parseJalali` take/return the plain `JalaliDate` shape or a `"YYYY-MM-DD"` string only, same
  signature-hygiene reasoning as §2.13's "no third-party type in any signature." **`month names
  ship on neither half in v1.0.0`** — `formatJalali`'s `fmt` supports only the numeric directives
  `%Y %m %d %H %M %S %%`; an unrecognised directive throws, mirroring `strftime`'s own failure
  mode exactly as §2.13's `format_jalali` already documents. This removes an entire divergence
  class (Persian month-name spelling/dialect disagreeing between an admin-rendered email and a
  client-rendered page) by not shipping the feature at all in v1.0.0, rather than shipping two
  independently-tuned name tables that drift.

  **Naming wart in `toJalali(value: string | JalaliDate): JalaliDate`, flagged rather than
  silently resolved during Phase 5.** The `JalaliDate` branch of that *input* is a **Gregorian**
  `{year, month, day}` triple — only the *return* value is actually Jalali. The `JalaliDate`
  shape is reused as a plain, calendar-agnostic `{year, month, day}` container for the input
  case, which reads oddly at a call site (`toJalali({year: 2024, month: 3, day: 20})` looks like
  it's naming a Jalali date; it isn't). This paragraph's own prose only ever justified excluding
  `Date`/an instant from the signature, never explained why the object branch is typed with the
  Jalali shape rather than a distinct `GregorianDate`. Kept as written here — shipping the
  signature literally as specified, superset-widening it later (e.g. a separate
  `GregorianDate` type) is additive; narrowing it after v1.0.0 would be a MAJOR bump — with the
  wart named explicitly in `src/dates.ts`'s own doc comment so a caller isn't left to infer it.

  **The timezone rule — decided here because correct arithmetic alone still produces a wrong
  answer without it:**

  > The **backend decides the calendar date**; the **frontend only formats and parses it**.
  > Date-only API fields are serialized `"YYYY-MM-DD"`. Backend `appkit.dates.to_jalali`
  > localises a `datetime` via `django.utils.timezone.localtime()` (Django's own `TIME_ZONE`
  > setting) before extracting the Jalali date — a naive `datetime` is treated as already-local.
  > No new `APPKIT` setting is introduced for this. **`toJalali`/`fromJalali` on the frontend
  > accept only a date-only value** (a `"YYYY-MM-DD"` string or a `JalaliDate`), **never a raw
  > `Date`/instant** — this is what makes it impossible for the frontend half to silently
  > re-derive "today" using the browser's own local timezone and disagree with the calendar
  > date the backend already committed to. `calendarDateIn(instant, timeZone)` is the one
  > explicit escape hatch for a caller holding a real ISO instant (a `created_at` timestamp, say)
  > who needs *a* calendar date from it — `timeZone` is a **required** IANA zone name with no
  > default, and a host wires it to the same zone as Django's `TIME_ZONE`, so the one place a
  > timezone decision is made is explicit and visible at the call site, never implicit in
  > `new Date().getTimezoneOffset()`.

  **Non-obvious failure path, mandatory test:** `calendarDateIn` at a day boundary — an instant
  at `23:30 UTC` with `timeZone: "Asia/Tehran"` (UTC+3:30) must resolve to the **next** calendar
  day, proving the function actually localises rather than truncating the instant's UTC date.

- **`mediaUrl` ↔ §2.11's `file_url`/`absolute_url` — the counterpart §2.11 explicitly promised,
  now delivered with the argument that keeps it inside the boundary.** `mediaUrl(value, baseUrl)`
  takes its base **as an argument**, never reading `NEXT_PUBLIC_API_URL` itself — this is the
  literal mechanism that keeps §13's boundary intact for the one function in this contract that
  would otherwise have the strongest pull toward reading an env var directly. The host's own code
  (or an app's manager, which already has the injected `basePath`/client) supplies `baseUrl`;
  `mediaUrl` itself stays pure. Edge behaviour mirrors the backend exactly, per §2.11's own
  closing paragraph: `null`/`undefined` in → `null` out; an already-absolute URL (detected the
  same way — `scheme`/authority present) passes through unchanged, never double-prefixed.
  **Which one is authoritative, restated from §2.11 so this function's scope reads as
  deliberately narrow, not incomplete:** the backend absolutizes wherever a request exists (every
  ordinary API response) and via `SITE_URL` where it doesn't (emails, background tasks) — this
  frontend function exists only as the fallback for a response that happens to carry a relative
  path (a legacy endpoint, an app that deliberately returns one), absolutizing against the
  frontend's own **API origin**, not the site origin.

---

## 19. The shared-fixture rule — one file, both suites

Stated as a general mechanism this contract commits to, not a per-utility footnote:

> Any behaviour that must agree across the two halves is verified by **one fixture file both
> test suites load**, never by two independently hand-written test files that happen to agree
> today. A divergence between the halves must be impossible to introduce by editing only one
> side's tests.

- **Location:** `tests/fixtures/*.json`, a directory shared by `tests/backend/` and
  `tests/frontend/` (`APP-DESIGN.md` §7.1's test-tree layout) — test-only, shipped in neither the
  Python nor the npm distributable.
- **Four fixture files this contract commits to:**
  - `error-codes.json` — the ten `code` values in the exact order given in §1. Both
    `appkit.exceptions.ERROR_CODES` (§2.3) and `ApiErrorCode` (§17) are asserted against this
    file rather than against each other's source directly — this is what turns "session 1 and
    session 2 agreed by hand" (currently the actual state of things, since this document itself
    was the only thing keeping them in sync) into a fact a test enforces.
  - `jalali-vectors.json` — see coverage below.
  - `money-vectors.json` — a table of `{input, output}` pairs covering `parse_amount`/
    `parseAmount`'s normalisation (Persian/Arabic-Indic digit inputs, thousands-separator
    variants) and `format_amount`/`formatAmount`'s grouping, including `0` and a negative value.
  - `truncate-vectors.json` — length/suffix/expected-output triples, including the emoji and
    combining-character cases §18 names explicitly.
- **Jalali vector coverage, enumerated so a future implementation phase doesn't generate a round
  number of arbitrary dates instead of the cases that actually catch algorithm disagreements:**
  - Every leap year in the 33-year Jalali cycle, and the non-leap years immediately adjacent to
    each — leap-year *boundary* years are where two "correct-looking" algorithms most often
    diverge.
  - Esfand 29 vs. Esfand 30 in both a leap and a non-leap year — named in §2.13's own drafting
    notes as the single most common Jalali bug class.
  - Farvardin 1 (Nowruz) across several years, including years where the corresponding Gregorian
    date itself shifts (Nowruz drifts between March 20 and March 21).
  - The month-length boundary: the first six 31-day months vs. the next five 30-day months.
  - Gregorian leap years, including a century year (2000 — a Gregorian leap year; 2100 — not).
  - Dates well outside the near present — Jalali years in the 1300s and 1450s — since an
    algorithm disagreement is more likely to surface away from the current decade than within it.
  - **Every vector round-tripped in both directions** — Gregorian→Jalali→Gregorian and
    Jalali→Gregorian→Jalali must both return the original input.
- **Jalali implementation — recommendation: vendor the arithmetic, don't take a runtime
  dependency on it.** `jalaali-js` is stable but low-activity — evaluated and not disqualifying
  on its own, but the conversion itself is fixed, well-defined arithmetic (the standard
  33-year-cycle algorithm) that needs no upstream updates once correct, which is precisely the
  profile of code that's safer vendored than depended on: a vendored ~120-line implementation
  (MIT-equivalent, attributed in a header comment) keeps the frontend half's **zero runtime
  `dependencies`** property (§22) intact, and the golden-vector fixture above is what makes
  vendoring safe rather than reckless — a vendored implementation with no test coverage would be
  the worse choice. Alternatives considered: taking `jalaali-js` as a real dependency (rejected —
  the only benefit over vendoring is not maintaining ~120 lines, at the cost of a runtime
  dependency this package otherwise has none of); the platform's own `Intl` with
  `calendar: "persian"` (rejected — the result depends on the runtime's ICU version and data,
  which is exactly the kind of environment-dependent divergence the golden-vector fixture exists
  to eliminate; two hosts on different Node/browser ICU builds could disagree on the identical
  input).
- **Implemented in Phase 5 as `frontend/src/vendor/jalaali.ts`, ~250 lines, not the ~120
  estimated above** — the estimate undercounted; the real figure once ported to typed TS with
  the full `jalCal`/`d2j`/`j2d`/`g2d`/`d2g` break-point machinery is roughly double. Provenance:
  ported from `jalaali-js` v1.2.8 (https://github.com/jalaali/jalaali-js), MIT, © 2020 Behrang
  Norouzinia — full licence text reproduced in `frontend/src/vendor/jalaali.ts`'s header comment
  and in `frontend/THIRD-PARTY-NOTICES.md` (shipped in the npm tarball via `package.json`
  `files`). Verified against all 79 `round_trip` vectors above (both directions) and all 4
  `invalid` vectors before vendoring, matching `jdatetime`/`jalali-core`'s FarsiWeb-lineage
  output exactly across the full 1300s–1450s Jalali span despite the two implementations
  deriving leap years by different routes (Borkowski's 33-year break-point table here vs.
  FarsiWeb's `jalali.c` port on the backend). **Intentionally frozen — this is not expected to
  track upstream `jalaali-js` releases.** The arithmetic is fixed; a future session asked
  "should this be updated" should read this note rather than re-deriving the answer. Internal to
  appkit: not exported from `src/index.ts`, not covered by appkit's own semver, covered by the
  same 95% coverage gate as every other module (vendoring doesn't lower the bar).

---

## 20. `makeQueryClient`

```ts
export function makeQueryClient(): QueryClient;
```

**Public.** A **factory, never a module-level singleton** — ported unchanged from
`../base-scaffold/frontend/lib/query-client.ts:19-37`, including its full reasoning: Next.js
renders on the server, and a module-level `QueryClient` would be shared across every concurrent
request/user, leaking one visitor's cached data into another's response. A host calls this
exactly once per browser session, inside `useState`, in `frontend/app/providers.tsx` (§23).

- Same defaults as the scaffold's version: `staleTime: 60_000`, `refetchOnWindowFocus: false`,
  and the 4xx-vs-5xx-aware retry predicate (never retry a 4xx — the response won't change on
  retry; retry a network failure or 5xx up to twice).
- **The retry predicate checks `isApiError(error)` (§17's brand check), not
  `error instanceof ApiError`** — the reasoning is the same one that motivates the brand check
  in the first place: an `instanceof` check fails silently across two module instances of the
  same class (the exact "two copies of appkit" scenario §21's duplicate-copy safeguard exists to
  detect), which would make the retry predicate treat every `ApiError` as an unrecognised error
  and retry a 400 needlessly.
- **Zero parameters in v1.0.0.** The documented escape hatch for a host wanting different
  defaults is `const qc = makeQueryClient(); qc.setDefaultOptions({...})` — react-query's own
  public API, not a new appkit surface. Adding an optional config parameter later (e.g.
  `makeQueryClient(overrides?: Partial<QueryClientConfig>)`) is additive, not a breaking change,
  so there's no cost to deferring it until a real host need appears.

---

## 21. `src/index.ts` — the complete export list

Per `APP-DESIGN.md` §12's "one entrypoint" rule: everything a host or an installed app can use is
exported from here; nothing under an internal path is ever imported directly. The `exports` map
in `package.json` (§22) makes this enforced by Node's resolver, not merely by convention.

```ts
// frontend/src/index.ts

export type { HttpClient, HeaderSource } from "./client";
export { ApiClientProvider, useApiClient } from "./provider";
export type { ApiClientProviderProps } from "./provider";

export {
  ApiError,
  isApiError,
  isApiErrorEnvelope,
  apiErrorFromEnvelope,
} from "./errors";
export type { ApiErrorCode, ClientErrorCode, ApiErrorEnvelope } from "./errors";

export { makeQueryClient } from "./query-client";

export {
  truncate,
  toEnglishDigits,
  toPersianDigits,
} from "./text";
export { parseAmount, formatAmount } from "./money";
export {
  toJalali,
  fromJalali,
  formatJalali,
  parseJalali,
  calendarDateIn,
} from "./dates";
export type { JalaliDate } from "./dates";
export { mediaUrl } from "./media";
```

**Explicitly not exported, each with the one-line reason a future session would otherwise
"helpfully" add it back in:**

- **No concrete client, no `apiClient` singleton, no `getApiBaseUrl`.** These are the exact host
  configuration §13 exists to keep out — a host builds and owns its own.
- **No `QueryClient` singleton** — only the factory; a singleton is the SSR cache-leak bug
  `makeQueryClient`'s whole shape exists to prevent (§20).
- **No `ApiClientContext`** (the React context object itself) — only the provider/hook pair, so a
  second, incompatible provider can't be hand-built against the same context (§15).
- **No manager or config-hook shapes** (`NotificationsManager`, `useNotificationsConfig`-style
  helpers) — those are per-app internals (`APP-DESIGN.md` §12, "Manager & hook conventions"),
  never appkit's to define or export.
- **No UI components, including a `share()` helper** — appkit is an SDK contract, not a component
  library (`CLAUDE.md`'s scope boundary table; restated in §J).
- **No storage helpers** (`localStorage`/`sessionStorage` wrappers) — nothing in this package
  reads or writes browser storage, matching the frontend security checklist
  (`APP-DESIGN.md` §12) and this document's own §13.

**Duplicate-copy safeguard.** A dev-only (stripped in production builds via
`process.env.NODE_ENV` guard, matching how React itself gates its own dev warnings) registration
on a `globalThis` symbol keyed by appkit's own package name: if a second copy of appkit's module
registers the same symbol, both log a console warning naming the failure mode
(`APP-DESIGN.md` §12's "two copies of appkit... useApiClient would silently return null in half
the tree"). This converts a silent, hard-to-diagnose `null` into a named, actionable console
warning at the moment it happens, rather than three layers later inside a manager's `fetch` call
— the same "name the actual cause" principle behind §15's provider-missing error and §16's
header-source-failure wrapping. Paired with `isApiError`'s brand check (§17), which stays correct
even when this safeguard's warning goes unread.

---

## 22. `package.json` shape and the install protocol (H-frontend)

```json
{
  "name": "@hjtdev/appkit",
  "version": "1.0.1",
  "type": "module",
  "sideEffects": false,
  "repository": { "type": "git", "url": "git+https://github.com/HjtDev/appkit.git", "directory": "frontend" },
  "homepage": "https://github.com/HjtDev/appkit#readme",
  "bugs": "https://github.com/HjtDev/appkit/issues",
  "publishConfig": { "access": "public" },
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": { ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" } },
  "files": ["dist"],
  "peerDependencies": {
    "react": ">=18",
    "@tanstack/react-query": ">=5"
  },
  "devDependencies": {
    "vitest": "^4.0.0",
    "msw": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "typescript": "^5.0.0"
  },
  "scripts": {
    "build": "tsc -p tsconfig.build.json",
    "prepare": "tsc -p tsconfig.build.json",
    "test": "vitest",
    "lint": "eslint src"
  }
}
```

- **`name: "@hjtdev/appkit"`, not the bare `appkit`** — the unscoped name is an unrelated package
  already registered on the public npm registry (v1.0.1 as of this writing too, coincidentally),
  so a scoped name is not a style choice but the only name available. `publishConfig.access:
  "public"` is required on every publish of a scoped package — npm otherwise defaults a scoped
  package to a *private* (paid) publish and the release fails.
  The backend half hits the same collision on PyPI (a bare `appkit` there is `AppKit`, an
  unrelated Webkit desktop framework) and takes the direct analogue of this fix:
  `backend/pyproject.toml`'s `[project] name` is `"hjtdev-appkit"`, not `"appkit"` — a
  distribution-name-only change, since PyPI has no scope mechanism. The importable module is
  unaffected either way: `import appkit` everywhere, on both packages, always.
  **`provenance` is deliberately NOT in `publishConfig`.** It was there in an earlier draft, on
  the theory that it would be a harmless no-op outside CI — verified wrong the hard way, while
  bootstrapping the very first publish of this package: `publishConfig.provenance: true` makes
  `npm publish` unconditionally attempt Sigstore provenance generation, which **hard-fails**
  (`npm error EUSAGE Automatic provenance generation not supported for provider: null`) the
  moment it isn't run inside a supported CI OIDC context — including the one-time manual
  bootstrap publish every trusted-publishing setup requires (`APP-DESIGN.md` §11.1), since
  trusted publishing can't be configured on a package that doesn't exist yet. `--provenance` is
  instead passed as an explicit CLI flag only on the CI job's own `npm publish` step
  (`APP-DESIGN.md` §10.1) — provenance where it's actually verifiable, no silent requirement
  that every future manual publish remember `--no-provenance`. `repository` is still required,
  for that CI-flag provenance to link back to this source.
- **`homepage`/`bugs` point at the GitHub repo, and a real `frontend/README.md` sits next to
  `package.json`.** All three were missing through v2.0.0 — npm's registry stored the literal
  string `"ERROR: No README data found!"` for this package's readme field, verified directly
  against the live registry entry, because npm reads a package's README relative to the directory
  actually being published (`frontend/`, this job's `working-directory`), never the repo root two
  levels up. `frontend/README.md` is a committed, generated **copy** of the root `README.md` —
  never hand-edited on its own — kept in sync by `make sync-readmes` and enforced by CI's
  `readme-contract` job (`APP-DESIGN.md` §8, §10.1). The backend half hit the identical bug on
  PyPI (empty `description`, no `Project-URL`s) for the identical reason; the fix is
  `backend/pyproject.toml`'s `readme = "README.md"` (not `"../README.md"`, `APP-DESIGN.md` §3.1)
  plus a `[project.urls]` table.
- **`prepare` builds `dist/` before `npm publish` packs it** — the same script a git-installed
  copy would need to run for itself, kept here so `npm publish`'s local pack step and a
  contributor's own local install never diverge in what gets shipped.
- **`exports` map declares only `"."`** — same enforcement `APP-DESIGN.md` §12 already
  establishes for every app SDK, applied to appkit itself: a host importing
  `@hjtdev/appkit/dist/provider` and coupling to an internal path is a mistake Node's resolver
  refuses to allow, not a convention a host has to remember to respect.
- **`sideEffects: false`** — every export here is a pure function, a class, or a component with
  no top-level side effect (the duplicate-copy safeguard in §21 runs inside a module-scope
  `if (process.env.NODE_ENV !== "production")` guard specifically so the module stays tree-shake
  and side-effect-free in production terms). This lets a bundler drop unused exports from a
  host's bundle — a host using only `ApiClientProvider`/`useApiClient` shouldn't pay for
  `toJalali`'s code in its bundle.
- **`peerDependencies`: `react >=18`, `@tanstack/react-query >=5` — matching `CLAUDE.md`'s wide-
  range rule at maximum strictness, the same reasoning `docs/CONTRACT.md` §9 already applied to
  the backend half.** **Zero runtime `dependencies`** — the property §19's vendoring
  recommendation exists specifically to protect; a hard dependency here would be the single most
  widely-propagated dependency in the entire frontend ecosystem, exactly analogous to §9's "an
  exact pin here is the worst possible place for one" but for *any* dependency at all, not merely
  a pinned one.
- **`devDependencies`: Vitest 4.x** (matching `APP-DESIGN.md` §7.7's "an app package's
  `devDependencies` should track the same major [as the scaffold's own baseline], not an older
  one" — appkit holds itself to the same rule it documents for every app), MSW for the header-
  injection and envelope-parsing tests' HTTP-layer mocking, `@testing-library/react` for the
  hook/provider tests, TypeScript for the build.
- **`@hjtdev/appkit` is a `peerDependency` of every installed app's own SDK, never a regular
  dependency — and the host installs `@hjtdev/appkit` itself explicitly, once, per
  `APP-DESIGN.md` §12 and `INTEGRATION-GUIDE.md` §2 step 3.** On the registry, npm *does* dedupe
  two compatible `peerDependency` ranges declared by two different installed apps into one
  resolved copy — this is no longer working around an npm limitation (v1.0.0's `github:` install
  had exactly that limitation, since npm cannot dedupe two separately-specified git refs the way
  it dedupes two registry ranges; that defect is why this package is on the registry at all now).
  The explicit host-level install is instead the ordinary peer-dependency convention: a
  `peerDependency` documents "this SDK needs a copy of X in the tree" without npm auto-installing
  one, so *something* still has to put that one copy there. **Verification step for a host,
  worth stating in the README directly:** `npm ls @hjtdev/appkit` after installing every app
  should show exactly one resolved copy, not two at different paths — still worth checking, since
  a host that pins two incompatible major ranges across two apps' peer dependencies can still end
  up with two copies even on the registry.
- **Version agreement across `pyproject.toml`, `package.json`, and `CHANGELOG.md` under one tag**
  — `CLAUDE.md` rule 5, restated here because this is the file that would otherwise drift first.

---

## 23. Host wiring (I-frontend)

Joins §8's backend wiring block — together they're what becomes `README.md`'s full config block
and `INTEGRATION-GUIDE.md` §2 steps 3/11 verbatim once code exists.

```tsx
// frontend/app/providers.tsx — mounted once, not once per installed app
"use client";

import { useState, useMemo } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ApiClientProvider, makeQueryClient } from "@hjtdev/appkit";
import { apiClient } from "@/lib/api-client";
import { getAuthHeaders } from "@/lib/auth"; // host's own — appkit knows nothing about it

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());

  // Stable reference — see §15's memoisation contract. An inline array literal here
  // defeats every installed app's own manager memoisation.
  const headerSources = useMemo(() => [getAuthHeaders], []);

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

```
# .env — nothing to add for the frontend half either. appkit declares zero required or
# optional keys of its own, on either half (docs/CONTRACT.md §7).
```

Two host-side consequences worth stating explicitly, since both change existing scaffold files
(flagged for the user to apply, not applied here — separate repo):

- **`frontend/lib/query-client.ts` becomes a thin re-export**: `export { makeQueryClient } from
  "@hjtdev/appkit";` — the scaffold's own factory (`query-client.ts:19-37`) and appkit's §20 are, by
  design, the identical function; once appkit ships, the host should stop maintaining a second
  copy rather than keep both in sync by hand.
- **`frontend/lib/api-client.ts` should construct its `ApiError` via appkit's `apiErrorFromEnvelope`
  (§17) and its own `ApiError` class import, not its locally-declared one** — already flagged in
  §17's own follow-up note; repeated here because it's the same change this wiring block depends
  on for `makeQueryClient`'s retry predicate (§20) to recognise the host's own thrown errors via
  `isApiError`.

---

## J. What appkit deliberately does not contain — both halves

One line of reasoning each, so a future session doesn't re-litigate a settled decision:

- **No custom validation framework.** DRF serializers already do the work; `appkit.validation`
  (§2.8) adds a thin helper for validating `request.query_params` through a serializer, not a new
  declaration syntax.
- **No generic XSS/SQL-injection scanner.** The ORM already prevents SQL injection; string-
  scanning for `<script>` is a blocklist that provides false confidence, not real protection. The
  two real pieces are in scope instead: `nh3`-based HTML sanitisation and an ORM lookup-key
  allowlist (§2.8).
- **No Celery / `django.tasks` dependency, on either half.** A shared dependency that drags in a
  task runner forces every consuming app *and* host to care about it, whether or not they need
  one.
- **No UI components, including a `share()` helper.** The frontend half is an SDK contract —
  hooks, a provider, and a fetcher interface — not a component library. Anything UI-shaped
  belongs in a separate package if it's ever wanted at all.
- **No client implementation — interface and provider only, restated as the single most
  important line in this entire frontend contract.** §13 states the boundary; this line exists
  so the reason appears again, next to every other "deliberately absent" decision, where a future
  session scanning this list for "what's missing that I should add" sees it in the same place as
  everything else it must not add.
- **No retry-on-401 / token refresh, anywhere in `headerSources` or the decorated client
  (§16).** A real refresh loop needs to know the refresh endpoint, avoid an infinite retry loop
  on a refresh that itself fails, and dedupe concurrent refreshes triggered by simultaneous
  in-flight requests — all three are auth-specific knowledge appkit must never have. This is
  the host's concrete client's responsibility to implement, exactly as `BASE-DESIGN.md` §3
  already assigns CSRF/credentials handling to the host and not to appkit. **The eventual JWT
  app's own README must document that refresh belongs in the host's client**, not expect appkit
  to provide it — noted here so that app's author doesn't reach for a mechanism that was never
  going to exist.

---

## Cross-half consistency re-read

Both halves of `docs/CONTRACT.md` now exist. Re-read in full against each other, checked point by
point:

| Check | Result |
|---|---|
| The ten `code` values, backend §1 table vs. frontend §17's `ApiErrorCode` union | **Agree**, string for string, same order. Both are now pinned against `error-codes.json` (§19) rather than against each other by hand, closing the exact gap that let "nine" survive uncorrected in five places before session 1. |
| Envelope key names — `request_id` (backend, §1) vs. `requestId` (frontend, `ApiError`) | **Deliberate, stated divergence, not a bug:** the **wire** shape (`ApiErrorEnvelope.error.request_id`, §17) matches the backend's JSON key exactly, snake_case, because it's the literal bytes on the wire. The **parsed** `ApiError` class exposes `requestId`, camelCase, because it's a TypeScript class following TS naming convention once off the wire — same pattern the scaffold's own `ApiError` already uses today (`api-client.ts:29-54`). No inconsistency: the boundary between the two names is exactly the parse step `apiErrorFromEnvelope` performs. |
| `truncate` suffix and counting rule, §2.12 (backend) vs. §18 (frontend) | **Agree** — same default suffix, same total-length-including-suffix counting rule, same degenerate-input clamp. Backend counts Python `len()` (codepoints); frontend explicitly uses `Array.from` for the same reason, called out in §18 as the one place a naive port would silently disagree. |
| `parse_amount`/`parseAmount` numeric-type handling, §2.14 (backend) vs. §18 (frontend) | **Intentional divergence in shape, not intent** — backend rejects `float`, returns `int`; frontend rejects non-integer `number` via `Number.isInteger` and additionally rejects anything beyond `Number.MAX_SAFE_INTEGER` (a ceiling the backend's arbitrary-precision `int` doesn't have). Documented in §18 as a real, caller-facing difference — not swept under "should behave the same," since JS genuinely cannot represent what Python's `int` can. |
| `format_amount`/`formatAmount` separators, §2.14 vs. §18 | **Agree** — both use a fixed ASCII `,` thousands separator regardless of locale; frontend explicitly avoids `Intl.NumberFormat` for exactly this reason (§18). |
| `mediaUrl` vs. §2.11's promised counterpart | **Delivered as promised**, with the one addition §2.11 anticipated but didn't fully specify: `baseUrl` is an explicit argument, never read from `NEXT_PUBLIC_API_URL` internally — this is what keeps it inside §13's boundary while still fulfilling §2.11's closing paragraph. |
| §0 item 6 ("Frontend hooks — Session 2") | **Resolved.** `useApiClient` is confirmed as a contract/DI hook, not a data-fetching hook, per that item's own prediction — no `useX` data-fetching hook exists in appkit itself; every such hook lives in an installed app's own SDK, per `APP-DESIGN.md` §12's "Manager & hook conventions." |

No unresolved inconsistency found between the two halves as written.

*End of contract, both halves. `README.md`'s config block (`APP-DESIGN.md` §8/§12) is generated
from this document once code exists — not the other way around.*
