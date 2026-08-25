# Changelog

All notable changes to appkit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is semantic across both
halves under one tag (`CLAUDE.md`'s Semver triggers).

## [1.0.0] — 2026-08-26

Initial release. Nothing consumes appkit yet, so there is no prior version to diff against —
this entry is a "what you need to know before you wire this up" briefing for the first
consuming author, not a change list.

### Added

- **Backend** (`appkit.*`): `cache`, `mixins`, `exceptions`, `request_id`, `crypto` (`crypto`
  extra), `permissions`, `pagination`, `validation`, `files` (`images` extra), `net`, `media`,
  `text`, `dates`, `money`, `throttling`, `testing` (opt-in pytest plugin), and the internal-but-
  stable `conf`. See `README.md`'s Exports (backend) section for the full per-module surface.
- **Frontend** (`appkit`, npm): `HttpClient`/`HeaderSource` types, `ApiClientProvider`/
  `useApiClient`, the error-envelope helpers (`ApiError`, `isApiError`, `isApiErrorEnvelope`,
  `apiErrorFromEnvelope`), `makeQueryClient`, and cross-half utilities (`truncate`,
  `toEnglishDigits`/`toPersianDigits`, `parseAmount`/`formatAmount`, the Jalali date helpers,
  `mediaUrl`). Everything importable is re-exported from `src/index.ts` — no other path is public.
- Persian (`fa`) translation catalogue for the four user-facing strings appkit's exception
  handler and `AppConfig` verbose name carry, shipped in the wheel.

### The error envelope — ten codes, not nine

Every error response from `appkit.exceptions.standard_exception_handler` has the shape:

```json
{"error": {"code": "validation_error", "message": "...", "details": {}, "request_id": "..."}}
```

`details` is always present (`{}` when there's nothing field-level); `request_id` matches
`appkit.request_id.request_id_var`. The code set is closed at exactly these ten values —
anything a client needs to branch on belongs in `details`, never as a new top-level `code`:

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
| 10 | `error` | *varies* (415, 406, or whatever the raising `APIException` set) | The documented catch-all — any `APIException` DRF resolved but that isn't one of the nine specific types above |

**`"error"` is a documented member of the set, not an omission.** For it, the HTTP `status` is
authoritative, not `code` — a client reading `"error"` checks the status to know what happened.
A specific code (e.g. `unsupported_media_type` for 415) may be carved out of `"error"` in a
future **minor** version; this is the one place the code set can shift without a major bump.
Every other rename or removal of a `code` value is a major bump.

### System checks — seven IDs, six functions

`AppKitConfig.ready()` registers six check functions producing seven IDs. Two Errors block
`manage.py check`; five Warnings are silenceable via Django's `SILENCED_SYSTEM_CHECKS`.

| ID | Level | Function | Fires when |
|---|---|---|---|
| `appkit.E001` | Error | `check_request_id_middleware` | `RequestIDMiddleware` absent from `MIDDLEWARE` |
| `appkit.E002` | Error | `check_exception_handler` | `EXCEPTION_HANDLER` unset or still DRF's own default |
| `appkit.W001` | Warning | `check_exception_handler` | `EXCEPTION_HANDLER` set to neither DRF's default nor appkit's |
| `appkit.W002` | Warning | `check_middleware_order` | `RequestIDMiddleware` ordered after `SecurityMiddleware` |
| `appkit.W003` | Warning | `check_unknown_settings_keys` | `APPKIT` dict has a key absent from `appkit.conf.DEFAULTS` (catches typos) |
| `appkit.W004` | Warning | `check_throttle_scopes` | A view's `throttle_scope` has no matching `DEFAULT_THROTTLE_RATES` entry |
| `appkit.W005` | Warning | `check_logging_filter` | `LOGGING` is configured but no handler references `RequestIDFilter` |

### Testing — the pytest plugin, and the collision it exists to avoid

`appkit.testing` is opt-in only: add `-p appkit.testing` to your own `addopts`. It is never
loaded automatically (no `pytest11` entry point) — see `README.md`'s Testing section for why.

**Every fixture name carries an `appkit_` prefix — this is not just a style choice.**
pytest-django ships its own `admin_user` and `admin_client` fixtures, and empirically,
wherever `db`/`django_db` is in play, pytest-django's versions win that name collision
**silently** — requesting the bare names returns pytest-django's plain Django `User`/`Client`,
never appkit's reflectively-built ones, with no warning anywhere. Use the prefixed names:
`appkit_api_client`, `appkit_user`, `appkit_admin_user`, `appkit_auth_client`,
`appkit_admin_client`, `appkit_frozen_request_id`, `appkit_clear_cache`, and the plain helper
function `appkit_assert_error_envelope(response, *, code=..., status=...)`.

`appkit_user`/`appkit_admin_user` build through `get_user_model().USERNAME_FIELD` reflectively,
so they work against an email-based custom user model, not just `username`-based ones.
`appkit_clear_cache` is deliberately **not** `autouse` — under `pytest -n auto` against a shared
Redis, an autouse cache-clear would clear another xdist worker's in-flight test data.

### Extras — two, and they compose

- `appkit[crypto]` — installs `cryptography>=42,<51` for `appkit.crypto.Cipher`.
- `appkit[images]` — installs `pillow>=10,<13` for `appkit.files.validate_image`.
- `appkit[crypto,images]` is a valid combined install.
- A missing extra never raises a bare `ImportError`: both paths import their extra lazily and
  re-raise naming the exact fix (`Install with: uv add "appkit[crypto]"` /
  `pip install "appkit[crypto]"`).

### Host action — required wiring for a first install

Since this is the first release, the entire install is the host action:

- Add `"appkit"` to `INSTALLED_APPS`.
- Add `appkit.request_id.RequestIDMiddleware` to `MIDDLEWARE`, **before** anything that logs and
  **after** `SecurityMiddleware` if present (`appkit.E001`/`W002`).
- Set `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "appkit.exceptions.standard_exception_handler"`
  (`appkit.E002`).
- Mount `ApiClientProvider` once at the frontend's root, injecting a host-built `HttpClient` —
  appkit ships the interface and the provider/hook pair only, never a concrete client.
- See `README.md`'s Settings, `.env` keys, and Usage sections for the complete config block.

### Known — zero required `.env` keys

`appkit.crypto.Cipher` takes its key as a constructor argument and never reads a `FERNET_KEY`
setting or any other `.env` value itself — key sourcing is entirely the host's call.
