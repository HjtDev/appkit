# Changelog

All notable changes to appkit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is semantic across both
halves under one tag (`CLAUDE.md`'s Semver triggers).

## [2.0.0] — 2026-08-30

### Changed

- **Backend package published to the PyPI registry as `hjtdev-appkit`.** The bare `appkit` name
  is an unrelated, already-registered package (`AppKit`, a Webkit desktop app framework) — same
  situation, same fix, as `@hjtdev/appkit` on npm (v1.0.1, below). The *import* name is
  unaffected: `import appkit` still works exactly as before; only the installable/requirement
  name changed, the same way `python-dateutil` ships `import dateutil`.

  **Why this is 2.0.0, not a patch, unlike the frontend rename above.** v1.0.1's frontend rename
  shipped as a patch because nothing that worked was changing — no install command in that
  README ever actually resolved. This is the opposite case: `uv add
  "git+https://github.com/HjtDev/appkit.git@v1.0.1#subdirectory=backend"` has always worked, and
  any host that wrote the `[tool.uv.sources]` block this README documented has a real,
  functioning pin on the name `appkit`. Changing the requirement string breaks that pin. A
  version bump exists to warn a consumer about exactly this kind of change, so it gets one.

  **Host action:** replace any dependency on `appkit` with `hjtdev-appkit>=2.0,<3.0` —
  `uv remove appkit && uv add "hjtdev-appkit>=2.0,<3.0"` (or the `pip`/`requirements.txt`
  equivalent) — and delete the `[tool.uv.sources]` entry pointing at the git URL, if one was
  added per the old README. No import changes anywhere: `import appkit`,
  `INSTALLED_APPS += ["appkit"]`, `-p appkit.testing`, and every `appkit.*` module path are
  unchanged. See `README.md`'s "Installation — backend" section for the new install commands.

- **`npm publish` in the reusable CI's `publish-npm` job now bumps npm to latest before
  publishing.** Node 22 (this ecosystem's pinned `node-version`) bundles npm 10.9.x; npm trusted
  publishing (OIDC) requires npm ≥ 11.5.1. Every prior tag's `publish-npm` run hit its
  "already published — skipping" branch (the actual publish had been done by hand each time), so
  this floor was never exercised until this release's tag — the first one where `publish-npm`
  and the new `publish-pypi` job (below) both do real, first-time work. Fixed in the org-level
  `HjtDev/.github` repo, not here — no host action.

- **Added `publish-pypi` to `.github/workflows/ci.yml` itself**, not to the shared
  `app-package-ci.yml` — the one sanctioned exception to "all real logic lives in the reusable
  workflow" (`CLAUDE.md`, `APP-DESIGN.md` §10.1). PyPI's trusted-publisher model cannot validate
  a `workflow_call` job's *callee* — only GitHub Actions' own OIDC claim for the workflow file
  that is registered as the trusted publisher, which for this project is `ci.yml`. npm's
  trusted-publisher model has the opposite rule (it validates the *caller's* workflow name for
  `workflow_call`), which is why `publish-npm` correctly stays where it always was. No host
  action — this only affects this repo's own release automation.

## [1.0.1] — 2026-08-29

Every defect below came from a real consumer — base-scaffold — actually installing v1.0.0.
None of these are code-behavior regressions from that release; they're integration defects
v1.0.0 shipped with, only surfaced once something outside this repo depended on it.

**Why this is 1.0.1, not 2.0.0, despite the frontend package renaming and every import
changing.** Renaming a published package and changing its import specifier ordinarily meets
CLAUDE.md's own bar for a major bump. It ships as a patch here for one reason, stated openly
rather than left for a reader to wonder about: v1.0.0's frontend half was **uninstallable by
every command its own README documented** (below) — there is no working consumer whose imports
this breaks, because no install of `"appkit"` from git ever actually resolved the tagged
`frontend/` tree. base-scaffold had to vendor a tarball to proceed at all. A version bump exists
to warn existing consumers about a change to something that worked; nothing that worked is
changing here.

### Added

- **`appkit.W006`** (`check_num_proxies_throttle_agreement`) — warns when
  `REST_FRAMEWORK["NUM_PROXIES"]` disagrees with `APPKIT["TRUSTED_PROXY_COUNT"]`, or is unset
  while any `SimpleRateThrottle` subclass (`ScopedRateThrottle`, `AnonRateThrottle`,
  `UserRateThrottle`, or a host's own) is configured, globally or on any view. DRF's
  `SimpleRateThrottle.get_ident()` does its own `X-Forwarded-For` parsing that appkit cannot
  inject `client_ip()`'s trusted-hop logic into — with `NUM_PROXIES` unset, `get_ident()` joins
  the entire header into the throttle bucket key, making the throttle spoofable by a client that
  prepends fake hops. See `README.md`'s System checks table and `docs/CONTRACT.md` §6.
- **`ApiError.unrecognizedCode: string | null`** (frontend) — the raw wire value of `error.code`
  when `apiErrorFromEnvelope` degraded it to `"error"` because it fell outside the ten-member
  `ApiErrorCode` union; `null` for every known code. Purely additive — no existing field changed
  shape.

### Changed

- **Frontend package published to the npm registry as `@hjtdev/appkit`.** The bare `appkit` name
  is an unrelated, already-registered package. **Host action:** `npm uninstall appkit && npm
  install @hjtdev/appkit@^1.0.1`, then change every `from "appkit"` import to
  `from "@hjtdev/appkit"`, and the `peerDependencies`/`dependencies` key in any app SDK's own
  `package.json` the same way. This is the fix for the BLOCKER below.
- **`isApiErrorEnvelope` widened to accept any non-empty-string `code`, not only the ten known
  values** — forward-compatible with a future minor version carving a new, specific code out of
  `"error"` (README's own documented policy). Purely additive at the type level: the exported
  `ApiErrorCode`/`ApiErrorEnvelope` types are unchanged, and `apiErrorFromEnvelope` normalises
  any such value to `"error"` before it can reach a `switch (code)` anywhere, so nothing
  downstream that compiled against 1.0.0's types stops compiling. See `docs/CONTRACT.md` §17.
- README gained: `HttpClient`'s exact method signatures (previously only in `client.ts`'s own
  source comments), `client_ip()`'s trusted-hop algorithm (previously only the outcome was
  documented), and `appkit.testing`'s two deferred-import rationales (previously only in
  `testing.py`'s own source comments). No behavior changed; these were read-the-source gaps
  base-scaffold hit and reported.

### Removed

- **All private-repo authentication guidance** — SSH-agent instructions, `--mount=type=ssh`,
  the `GH_TOKEN`/`insteadOf` token flow — from `README.md`, `INTEGRATION-GUIDE.md`,
  `APP-DESIGN.md` (§1.2 deleted outright), and `BASE-DESIGN.md`'s example Dockerfiles. This
  repo, and every package in this ecosystem, is public; installing either half has never
  required a credential of any kind, and the docs no longer imply otherwise. **Host action:** if
  a consuming project added an SSH-agent CI step, a `--ssh default` buildx flag, or a
  `GH_TOKEN`/`insteadOf` git config specifically to install `appkit`, remove it — it was never
  load-bearing for a public repo and is now dead weight.
- Confirmed via `git log -p --all -- '*.env' '*.env.*' '*.pem' '*key*'` before writing any of the
  above: nothing real was ever committed to this repo's history (an empty `.env.example`
  placeholder and a system-check test fixture literally named for testing an unrecognised
  *settings* key, not a secret). Going public required no history remediation.

### BLOCKER fixed — the frontend half was uninstallable by every documented command

Verified directly, against the real repo, on npm 11.16.0: `npm install
"github:HjtDev/appkit#v1.0.0:frontend"` (README's own documented command) silently drops both
the tag and the subdirectory — npm logs `ignoring unknown key "v1.0.0"` and installs the
**default branch's entire repo root** instead. The `::path:frontend` form fares no better: it
reads package metadata from `frontend/package.json` but still packs and installs the **whole
repository**, `backend/` included, so `import "appkit"` fails with
`ERR_PACKAGE_PATH_NOT_EXPORTED`. Committing `frontend/dist` does not fix `::path:` either —
verified with a local git remote built specifically to test this — because `::path:` is
metadata-only; npm packs the repo root regardless of what's committed where. There is no
subdirectory-git-install form that works for this monorepo layout; a registry publish was the
only fix available, which is why the frontend half now installs from `@hjtdev/appkit` (see
"Changed" above) rather than a corrected git URL.

**Host action, the load-bearing one:** replace any `npm install "github:HjtDev/appkit#..."` —
in a `package.json`, a Dockerfile, a CI workflow — with `npm install @hjtdev/appkit`. The
backend half is unaffected: `uv`/`pip` correctly implement Git's `#subdirectory=` fragment, so
`git+https://github.com/HjtDev/appkit.git@v1.0.1#subdirectory=backend` continues to work exactly
as before, no auth, no change.

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
