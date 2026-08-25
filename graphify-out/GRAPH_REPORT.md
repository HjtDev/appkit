# Graph Report - appkit  (2026-08-25)

## Corpus Check
- 112 files · ~113,159 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 954 nodes · 1549 edges · 52 communities (34 shown, 18 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 91 edges (avg confidence: 0.88)
- Token cost: 272,383 input · 8,490 output

## Community Hubs (Navigation)
- Jalali Dates & Errors (TS)
- Settings & File Detection
- Query-Param Validation & Sanitisation
- App Init & Throttle Scopes
- AppConfig System Checks
- Jalali Dates (Python)
- Pytest Fixtures (testing.py)
- Error Envelope & Pagination
- Frontend HttpClient & Provider
- Cache Namespacing
- Fernet Crypto
- Money & Text Helpers
- TS Compiler Config
- Media URL Absolutisation
- CachedListMixin
- Client IP Trust Boundary
- DRF Permission Classes
- TS Build Config
- EmailUser Model
- Frontend Dev Dependencies
- Exception Handler Test URLs
- Frontend Package Metadata
- Throttle Scope Test URLs
- React/Query Peer Deps
- Root NPM Scripts
- Workspace Package Config
- Import Boundary Test
- Test-Tree URLconf
- Test Django Settings
- ASGI Middleware Regression Test
- Bare-Install Import Smoke Test
- ESLint Dep
- ESLint/Pre-commit Config Docs
- jsdom Dep
- react-dom Dep
- jest-dom Testing Dep
- React Testing Library Dep
- Node Types Dep
- TypeScript Dep
- typescript-eslint Dep
- Vite React Plugin Dep
- EmailUser Test App Init
- Nested Throttle URLconf
- Workspace Root Package
- appkit Package Identity
- appkit README

## God Nodes (most connected - your core abstractions)
1. `validate_image()` - 26 edges
2. `client_ip()` - 20 edges
3. `golden()` - 19 edges
4. `_ids()` - 19 edges
5. `standard_exception_handler()` - 18 edges
6. `safe_filter_kwargs` - 17 edges
7. `compilerOptions` - 16 edges
8. `validate_upload()` - 15 edges
9. `absolute_url()` - 15 edges
10. `_request()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `toJalaali()` --semantically_similar_to--> `Jalali Vectors`  [INFERRED] [semantically similar]
  frontend/src/vendor/jalaali.ts → tests/fixtures/jalali-vectors.json
- `Pre-commit Configuration` --references--> `ESLint Configuration`  [INFERRED]
  .pre-commit-config.yaml → eslint.config.mjs
- `test_missing_images_extra_message_is_actionable()` --calls--> `validate_image()`  [INFERRED]
  tests/backend/test_bare_install.py → backend/src/appkit/files.py
- `test_request_id_filter_defaults_to_dash_outside_a_request_cycle()` --uses--> `RequestIDFilter`  [INFERRED]
  tests/backend/test_request_id.py → backend/src/appkit/request_id.py
- `test_request_id_filter_reads_the_contextvar_when_set()` --uses--> `RequestIDFilter`  [INFERRED]
  tests/backend/test_request_id.py → backend/src/appkit/request_id.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **AppKit Backend Core Modules** — backend_src_appkit_cache, backend_src_appkit_exceptions, backend_src_appkit_request_id, backend_src_appkit_conf [EXTRACTED 1.00]
- **AppKit Validation & Security** — backend_src_appkit_validation, backend_src_appkit_files, backend_src_appkit_net, backend_src_appkit_permissions [INFERRED 0.85]
- **Appkit Validation Logic** — backend_src_appkit_validation_validate_query_params, backend_src_appkit_validation_safe_filter_kwargs, backend_src_appkit_validation_sanitize_html [EXTRACTED 0.90]
- **Appkit Architecture Documentation** — docs_app_design, docs_base_design, docs_claude_code_guide_app [EXTRACTED 1.00]
- **Frontend SDK Contract** — frontend_src_client, frontend_src_provider, frontend_src_errors [EXTRACTED 1.00]
- **Cross-Half Consistent Utilities** — frontend_src_dates, frontend_src_text, frontend_src_money [EXTRACTED 1.00]
- **Cross-Half Semantic Agreement** — tests_fixtures_jalali_vectors, tests_fixtures_error_codes, frontend_src_text_truncate, frontend_src_vendor_jalaali_tojalaali [EXTRACTED 1.00]
- **API Client Injection Flow** — frontend_src_provider_apiclientprovider, frontend_src_provider_useapiclient, frontend_src_provider_decorateclient [EXTRACTED 1.00]

## Communities (52 total, 18 thin omitted)

### Community 0 - "Jalali Dates & Errors (TS)"
Cohesion: 0.05
Nodes (64): calendarDateIn(), compileFormat(), DIRECTIVE_REGEX, formatJalali(), fromJalali(), fromJalaliChecked(), JalaliDate, pad() (+56 more)

### Community 1 - "Settings & File Detection"
Cohesion: 0.05
Nodes (64): get_setting(), Any, Settings access layer for appkit's ``APPKIT`` settings dict. Internal-but-…, Single-member enum backing :data:`UNSET`. Naming this class directly — as…, Read an ``APPKIT`` setting, falling back to appkit's documented default. Reads…, _Unset, _check_extension_agreement(), detect_mimetype() (+56 more)

### Community 2 - "Query-Param Validation & Sanitisation"
Cohesion: 0.05
Nodes (58): appkit.validation, ALLOWED_LOOKUPS, _coerce_filter_value, Any, Query-param validation, HTML sanitisation, and an ORM lookup allowlist for…, `nh3`-based allowlist HTML sanitisation. `allowed_tags=None` uses the…, Removes all tags, returning plain text. For fields that must never contain…, Pure membership check against `ALLOWED_LOOKUPS`. Never raises. (+50 more)

### Community 3 - "App Init & Throttle Scopes"
Cohesion: 0.06
Nodes (56): appkit — the shared Django + DRF foundation every app package and host in this…, Mechanical construction of DRF throttle-scope strings from the app-namespace…, `throttle_scope("notifications", "list")` -> `"notifications_list"`. Enforces…, throttle_scope(), override_settings, _ids(), `appkit.checks` — every system check registered by `AppKitConfig.ready()`…, Default test-tree URLconf mounts only the unscoped `ping` view. (+48 more)

### Community 4 - "AppConfig System Checks"
Cohesion: 0.06
Nodes (50): AppConfig, AppKitConfig, appkit's ``AppConfig``. ``INSTALLED_APPS`` membership is confirmed, not merely…, check_exception_handler(), check_logging_filter(), check_middleware_order(), check_request_id_middleware(), check_throttle_scopes() (+42 more)

### Community 5 - "Jalali Dates (Python)"
Cohesion: 0.08
Nodes (49): _compile_format(), format_jalali(), from_jalali(), parse_jalali(), date, Gregorian <-> Jalali conversion, formatting, and parsing using stdlib types…, Builds a matching regex for `fmt`, one named group per first occurrence of a…, The inverse of `format_jalali`. Runs `to_english_digits` internally first —… (+41 more)

### Community 6 - "Pytest Fixtures (testing.py)"
Cohesion: 0.07
Nodes (47): APIClient, Backend Project Config, appkit_admin_client(), appkit_admin_user(), appkit_api_client(), appkit_assert_error_envelope(), appkit_auth_client(), appkit_clear_cache() (+39 more)

### Community 7 - "Error Envelope & Pagination"
Cohesion: 0.07
Nodes (42): _code_for(), _message_and_details(), Any, Exception, Response, The single DRF exception handler producing the standard error envelope.…, DRF `EXCEPTION_HANDLER` producing the envelope described in this module's…, Splits DRF's raw `response.data` into a flat message plus a details dict. A… (+34 more)

### Community 8 - "Frontend HttpClient & Provider"
Cohesion: 0.07
Nodes (19): Appkit Public Contract, Integration Guide, HeaderSource, HttpClient, ApiClientContext, ApiClientContextValue, ApiClientProvider(), ApiClientProviderProps (+11 more)

### Community 9 - "Cache Namespacing"
Cohesion: 0.08
Nodes (38): build_cache_key(), cache_endpoint(), cached_call(), invalidate_namespace(), namespace_version(), _normalize_part(), Cache namespace versioning, key building, get-or-set, and endpoint-level…, Builds a stable, namespace-versioned cache key.… (+30 more)

### Community 10 - "Fernet Crypto"
Cohesion: 0.09
Nodes (32): Cipher, _fernet_class(), generate_key(), Fernet symmetric encryption primitive taking its key at construction time.…, Lazily imports `cryptography.fernet.Fernet`, behind the `crypto` extra. A…, Fernet symmetric encryption, keyed at construction — never from Django…, Builds the underlying `Fernet` cipher from `key`. Raises: ImportError: if the…, Returns a URL-safe token string. Never raises for any `str` input. (+24 more)

### Community 11 - "Money & Text Helpers"
Cohesion: 0.08
Nodes (32): format_amount(), parse_amount(), Integer money parsing/formatting with fixed ASCII grouping. Flagged in…, Parses a digit string or `int` into an `int` amount. Accepts Persian/Arabic-…, Thousands-grouped string using a fixed ASCII `,` separator, regardless of…, Shared string helpers whose semantics must match the frontend half. Flagged in…, Truncates `value` to `length` characters (codepoints), suffix included in the…, Normalises Persian and Arabic-Indic digits to ASCII. Never raises; characters… (+24 more)

### Community 12 - "TS Compiler Config"
Cohesion: 0.06
Nodes (31): compilerOptions, allowJs, esModuleInterop, isolatedModules, jsx, lib, module, moduleResolution (+23 more)

### Community 13 - "Media URL Absolutisation"
Cohesion: 0.11
Nodes (27): absolute_url(), file_url(), _is_absolute(), HttpRequest, Request, File-location/URL formatting — absolutizing media URLs. Kept as a separate…, Absolutizes a `FieldFile`/URL string, or `None` for an unset value. `None` and…, Absolutizes `url` against `request` (or `APPKIT["SITE_URL"]` when there is… (+19 more)

### Community 14 - "CachedListMixin"
Cohesion: 0.09
Nodes (22): Request, `per_user=False` shares one cache entry across every caller — valid only where…, _user_cache_token(), CachedListMixin, Any, Response, Caches a `ListAPIView`'s serialized data per user and querystring. Set…, BaseAuthentication (+14 more)

### Community 15 - "Client IP Trust Boundary"
Cohesion: 0.13
Nodes (28): client_ip(), _normalize_candidate(), HttpRequest, Request, Trust-boundary parsing of proxy headers to resolve the real client IP. Public…, Validates a single `X-Forwarded-For` entry, stripping brackets/port where…, Resolves the real client IP, trusting only the proxy-appended `X-Forwarded-For`…, parametrize (+20 more)

### Community 16 - "DRF Permission Classes"
Cohesion: 0.15
Nodes (21): IsAppAdmin, IsObjectOwner, Any, APIView, Request, Shared DRF permission classes. Public surface (docs/CONTRACT.md §2.6),…, Gates the custom admin-dashboard API surface (`APP-DESIGN.md` §5's second admin…, Denies access to another user's object — the IDOR case `APP-DESIGN.md` §7.4 and… (+13 more)

### Community 17 - "TS Build Config"
Cohesion: 0.10
Nodes (19): compilerOptions, declaration, declarationMap, noEmit, outDir, removeComments, rootDir, types (+11 more)

### Community 18 - "EmailUser Model"
Cohesion: 0.15
Nodes (12): BaseUserManager, django_db, EmailUser, EmailUserManager, Meta, AbstractBaseUser, A minimal, email-keyed custom user model — the non-`username` `USERNAME_FIELD`…, A deliberately minimal user model keyed on `email`, not `username` — `username`… (+4 more)

### Community 19 - "Frontend Dev Dependencies"
Cohesion: 0.12
Nodes (17): eslint-config-prettier, eslint-plugin-react-hooks, devDependencies, eslint-config-prettier, eslint-plugin-react-hooks, msw, prettier, @types/react (+9 more)

### Community 20 - "Exception Handler Test URLs"
Cohesion: 0.16
Nodes (10): AnonRateThrottle, _FixedRateThrottle, APIView, Response, Scratch URLconf for `appkit.exceptions` integration tests only — the two cases…, A hardcoded 1/min rate, so the test doesn't need to touch…, First GET succeeds; the second (same client/IP) is throttled and gets Retry-…, BasicAuthentication supplies a real `authenticate_header`, so an… (+2 more)

### Community 21 - "Frontend Package Metadata"
Cohesion: 0.15
Nodes (12): description, exports, files, dist, license, main, name, sideEffects (+4 more)

### Community 22 - "Throttle Scope Test URLs"
Cohesion: 0.21
Nodes (9): _KnownScopeView, APIView, HttpResponse, Scratch URLconf for appkit.checks.check_throttle_scopes (appkit.W004) tests…, Declares a throttle_scope with (deliberately) no matching…, Declares a throttle_scope that IS covered by the test settings'…, No throttle_scope at all — must never appear in check_throttle_scopes's…, _ScopedView (+1 more)

### Community 23 - "React/Query Peer Deps"
Cohesion: 0.29
Nodes (7): react, @tanstack/react-query, peerDependencies, react, @tanstack/react-query, react, @tanstack/react-query

### Community 24 - "Root NPM Scripts"
Cohesion: 0.33
Nodes (6): scripts, build, format, format:check, lint, test

### Community 25 - "Workspace Package Config"
Cohesion: 0.33
Nodes (5): description, name, private, workspaces, frontend

### Community 26 - "Import Boundary Test"
Cohesion: 0.40
Nodes (4): parametrize, Proves the flake8-tidy-imports banned-api block in backend/pyproject.toml…, `from <module> import x` inside src/appkit must be rejected by ruff's TID251…, test_host_module_import_is_banned()

### Community 27 - "Test-Tree URLconf"
Cohesion: 0.40
Nodes (4): ping(), HttpRequest, HttpResponse, Test-tree URLconf. appkit ships no urlpatterns of its own (docs/CONTRACT.md…

## Knowledge Gaps
- **113 isolated node(s):** `appkit`, `name`, `version`, `description`, `license` (+108 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `golden()` connect `Jalali Dates (Python)` to `Jalali Dates & Errors (TS)`, `Money & Text Helpers`, `Error Envelope & Pagination`?**
  _High betweenness centrality (0.365) - this node is a cross-community bridge._
- **Why does `Error Codes` connect `Jalali Dates & Errors (TS)` to `Jalali Dates (Python)`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `override_settings` (e.g. with `test_cached_call_unset_resolves_from_appkit_cache_timeout_setting()` and `test_e001_when_middleware_is_absent()`) actually correct?**
  _`override_settings` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `golden()` (e.g. with `test_every_golden_vector_round_trips_gregorian_to_jalali_to_gregorian()` and `test_every_golden_vector_round_trips_jalali_to_gregorian_to_jalali()`) actually correct?**
  _`golden()` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `appkit`, `name`, `version` to the rest of the system?**
  _113 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Jalali Dates & Errors (TS)` be split into smaller, more focused modules?**
  _Cohesion score 0.053703703703703705 - nodes in this community are weakly interconnected._
- **Should `Settings & File Detection` be split into smaller, more focused modules?**
  _Cohesion score 0.053994732221246705 - nodes in this community are weakly interconnected._