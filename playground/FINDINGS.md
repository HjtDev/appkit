# Phase 6 playground — findings

`docs/APP-DESIGN.md` §11.2 / `docs/CLAUDE-CODE-GUIDE-APP.md`'s Phase 6 brief. Everything below was
observed against the real running stack (`docker compose -f playground/docker-compose.yml up`),
not reasoned about. Where a pytest asserts the behaviour, the file:test is named so it can be
re-run as proof. All 39 tests pass (`32 passed` under `-m live`, `7 passed` under `-m "not live"`)
as of this report.

Legend for **Fix belongs in**: `appkit` (the package itself) · `README.md` (the wiring block) ·
`CONTRACT.md` (the spec) · `APP-DESIGN.md` (the playground/SDK-authoring guidance) ·
`base-scaffold` (flagged only, per instructions — separate repo, out of scope here).

**Status: every finding scoped to this repo has been fixed** (a follow-up commit on this same
branch) — README.md's wiring block, CONTRACT.md's request-ID caveat, APP-DESIGN.md's playground/
SDK-authoring guidance, and `frontend/package.json`'s `prepare` script. Only the base-scaffold
nginx-config gap (§6) remains flagged-only, per instructions — separate repo. Each section below
still describes what was found in its original, as-discovered form; the "Fix belongs in" column
and the summary table at the bottom now note where each landed.

---

## 1. The wiring block itself

### 1.1 README.md's own wiring block doesn't match its declared canonical source

**Fix belongs in: README.md.** `docs/CONTRACT.md` §8 (lines 1052–1091) says of itself: *"Copy-
pasteable as written — this becomes README.md's config block ... verbatim once code exists."*
It isn't. `README.md` splits the same content into **three non-contiguous code fences**
(lines 66–73, 79–82, 89–107), interleaved with prose, in a **different order** than CONTRACT §8's
single contiguous block (`INSTALLED_APPS` first there; last in README). A host copy-pasting
README's blocks in order still produces a working project (verified — §1.2 below), but the two
documents disagreeing about their own canonical form is a real drift worth closing before v1.0.0:
regenerate README's block from CONTRACT §8 mechanically, or point CONTRACT §8 at README instead.

### 1.2 The paste boots, but only with additions the README never mentions

**Fix belongs in: README.md** (all five). Every item below was *required* for
`playground/backend/config/settings.py` to produce a working, fully-exercised project — each is
outside the banner-marked "APPKIT WIRING — VERBATIM FROM README.md" block, in the "HOST BASELINE"
half, and each is something a genuinely fresh host would not already have:

- **ASGI is required, not optional, and README never says so.**
  `appkit.request_id.RequestIDMiddleware` is `sync_capable = False` — a WSGI host (`runserver`,
  gunicorn+sync workers) cannot run it at all. Nothing in README's "Settings" section states this;
  a host following only the wiring block would discover it from a crash, not a hint. Recommend a
  one-line callout: *"Requires ASGI (uvicorn/daphne) — see `ASGI_APPLICATION`."*
- **`SECURE_PROXY_SSL_HEADER` / `TRUST_PROXY_SSL_HEADER` is never mentioned, but `absolute_url`
  depends on it.** `appkit/src/appkit/media.py`'s own docstring says `absolute_url` "already
  respects Django's `SECURE_PROXY_SSL_HEADER` handling" — true, but only if the host set it. A
  host that pastes only README's block gets `http://` media URLs behind a TLS-terminating proxy
  (mixed content) with zero warning from any appkit system check. Proven via
  `tests/live/test_media_https.py` *once the playground's own host-baseline sets it* — remove
  that baseline setting and the same test would fail with no appkit-side signal at all.
- **A working `CACHES` backend is required by `CachedListMixin`, and README's Settings section
  never says so.** `appkit.mixins.CachedListMixin` (used the moment any list view opts in) needs
  a real cache backend or every response degrades to Django's locmem default silently — no crash,
  just no caching, no isolation, and no signal that anything is wrong.
- **`ScopedRateThrottle`/`DEFAULT_THROTTLE_CLASSES` is never mentioned, and `throttle_scope()`
  is inert without it.** `appkit.throttling.throttle_scope()` and system check `appkit.W004`
  (`DEFAULT_THROTTLE_RATES` entries) together create the impression that declaring
  `throttle_scope = throttle_scope("demo", "list")` plus a matching rate is sufficient. It is not:
  DRF only enforces a `throttle_scope` class attribute if `DEFAULT_THROTTLE_CLASSES` includes
  `ScopedRateThrottle` (or the view sets `throttle_classes` itself). A host could pass `W004`
  cleanly and still ship an unthrottled endpoint. Worth a README line, or a new check.
- **No copy-pasteable `LOGGING` dict.** README:79–82 supplies only the `RequestIDFilter` import
  line, correctly noting a real host's `config/logging.py` already exists — but nothing in the
  repo shows the actual filter/handler shape except `checks.py`'s own hint string
  (`checks.py:338`). A minimal worked example (what this playground's own
  `config/logging.py` / `config/settings.py`'s `LOGGING` dict now is) would remove the last bit of
  guesswork for a genuinely greenfield host.

### 1.3 `docs/APP-DESIGN.md` §12's `HttpClient` excerpt is stale

**Fix belongs in: APP-DESIGN.md.** Its inline excerpt (lines ~1432–1437) shows four methods, no
`put`. `docs/CONTRACT.md` §14 already documents this as "a deliberate deviation" and is correct
(five methods, `frontend/src/client.ts:17-23` confirmed). The stale excerpt itself — not the
design decision — is what should be fixed or removed in favour of a cross-reference.

---

## 2. The system checks, both directions — `tests/live/test_checks.py`

**No appkit-side issues.** The positive case (`test_correctly_wired_playground_is_silent`) and
all seven negative cases (`test_broken_wiring_fires_exactly_its_own_id`, parametrized over
`playground/backend/config/broken/*.py`) pass, run against the real container via
`docker exec ... manage.py check`:

```
System check identified no issues (0 silenced).      # correctly-wired playground
appkit.E001   MIDDLEWARE missing RequestIDMiddleware
appkit.E002   EXCEPTION_HANDLER unset / DRF default
appkit.W001   EXCEPTION_HANDLER set to a third handler
appkit.W002   RequestIDMiddleware ordered before SecurityMiddleware
appkit.W003   unrecognised APPKIT key (CACHE_TIMOUT typo)
appkit.W004   throttle_scope with no matching DEFAULT_THROTTLE_RATES entry
appkit.W005   LOGGING configured, no RequestIDFilter-referencing handler
```

Each fires **only** its own ID — no cross-firing observed. This is the check the brief calls the
one only a real project can prove ("a correct host producing silence"), and it holds.

---

## 3. The error envelope, end to end — `tests/live/test_envelope_http.py`

**No appkit-side issues.** All ten `docs/CONTRACT.md` §1 codes triggered over real HTTP through
nginx, backend `standard_exception_handler` → frontend `apiErrorFromEnvelope` (proven separately,
§7 below, since the two need to agree with *each other*, not just the fixture independently):
`validation_error`, `parse_error`, `not_authenticated` (with `WWW-Authenticate`), `authentication_
failed`, `permission_denied`, `not_found`, `method_not_allowed`, `throttled` (with `Retry-After`),
`server_error` (generic message, `DEBUG=false`), `error` (415, catch-all, status authoritative).
`details` present on every response, confirmed.

---

## 4. `client_ip` behind the real proxy chain — `tests/live/test_client_ip.py`

**No appkit-side issues — this is the strongest positive result in this report.** Live evidence,
the actual spoofing attempt, `TRUSTED_PROXY_COUNT=1`:

```
$ curl -H 'X-Forwarded-For: 66.66.66.66' http://127.0.0.1:8080/api/v1/demo/echo/
{
  "client_ip":        "172.22.0.1",              # correct — the real caller
  "remote_addr":       "66.66.66.66",             # SPOOFED — uvicorn's own REMOTE_ADDR is not safe
  "x_forwarded_for":  "66.66.66.66, 172.22.0.1"   # nginx appended its own peer after the fake entry
}
```

This is exactly the risk `docs/CONTRACT.md` §2.10 documents: with `--forwarded-allow-ips "*"`
(`backend/Dockerfile`'s CMD, matching `docs/BASE-DESIGN.md:919-921`), uvicorn's own proxy-headers
middleware trusts the attacker-controlled leftmost `X-Forwarded-For` entry into `REMOTE_ADDR`
— confirmed, not assumed. `appkit.net.client_ip` never reads `REMOTE_ADDR` and correctly resolved
the real address by reading from the right. Design validated against a live spoofing attempt.

---

## 5. Media URLs behind the proxy — `tests/live/test_media_https.py`

**No appkit-side issues**, given the host-baseline fix in §1.2. `absolute_url` yields
`http://127.0.0.1:8080/...` through the plain listener and `https://127.0.0.1:8443/...` through
the self-signed-TLS listener — **with the correct non-standard port in both cases**. That port
preservation was not free — see finding 6.2 below.

---

## 6. nginx (base-scaffold gap, flagged and worked around here)

`docs/BASE-DESIGN.md` §9 documents nginx only in prose (host-level proxy, `/healthz/`
internal-only, `$proxy_add_x_forwarded_for` semantics) — **it ships zero nginx config to copy.**
Building `playground/nginx/nginx.conf` from that prose, two real mistakes were made and caught
only by the live stack — exactly what a config-only playground guide can't catch and a base-
scaffold user following the same prose would very plausibly also make:

**6.1 — nginx `proxy_set_header` does not inherit between sibling `location` blocks.**
With the common headers set only inside `location /`, `location /healthz/` fell back to nginx's
default `Host` header (`$proxy_host`, i.e. the literal upstream name `"backend_upstream"`), which
Django's `ALLOWED_HOSTS` correctly rejected with `400 Bad Request`. Fix: hoist shared
`proxy_set_header` lines to the `server` block, which nginx *does* propagate to every location
that sets none of its own — `playground/nginx/nginx.conf`'s comment records this exactly.

**6.2 — nginx's `$host` strips the port; use `$http_host`.** With `proxy_set_header Host $host;`,
`request.build_absolute_uri()` produced `http://127.0.0.1/media/...` — the `:8080` silently gone,
because nginx's `$host` is the bare hostname. On a non-standard port (any real deployment behind
a reverse proxy that isn't `:80`/`:443`) every media URL is simply wrong. Fixed with
`$http_host`, which preserves what the client actually sent (Django's own `ALLOWED_HOSTS`
matching already strips the port for comparison, so this doesn't reopen that surface).

**Recommendation, not applied here (separate repo):** `docs/BASE-DESIGN.md` §9 should ship an
actual copy-pasteable nginx config, not prose alone — these are exactly the two mistakes prose-
only guidance produces.

---

## 7. Request-ID correlation — `tests/live/test_request_id.py`

**7.1 — Application-level correlation is fully correct.** Echoed on the response header,
inbound `X-Request-ID` honoured, a malformed inbound ID (space + 100 chars) discarded and
replaced, appears in `appkit.exceptions`'s own `logger.exception(...)` log line, and — the one
thing no unit test can prove — **12 concurrent requests, each with its own ID, showed zero
bleed** (`test_no_id_bleed_under_concurrency`), confirming the async-only design and the
`finally: reset()` contract hold under real concurrency.

**7.2 — Real, structural gap: Django's own `django.request` auto-logger never carries the ID.**
**Fix belongs in: CONTRACT.md** (document as a stated caveat — this is not fixable in `appkit`
without reintroducing the leak §7.1 just proved doesn't happen). Root-caused via
`django/core/handlers/base.py:154-170`:

```python
async def get_response_async(self, request):
    ...
    response = await self._middleware_chain(request)          # <- RequestIDMiddleware's own
                                                                #    finally: reset() has ALREADY
                                                                #    run by the time this returns —
                                                                #    it's one link INSIDE this chain
    if response.status_code >= 400:
        await sync_to_async(log_response, thread_sensitive=False)(...)   # sees "-", always
```

Verified with `test_django_request_autologger_never_carries_the_id`: a 404's own `X-Request-ID`
never appears in the corresponding `django.request` log line; `[-]` is what's there instead. This
is **not** fixable by reordering `MIDDLEWARE`, and not a flake — `BaseHandler`'s own top-level
4xx/5xx logging happens structurally *after* the entire middleware chain (including
`RequestIDMiddleware`) has fully unwound. Only logging calls made *from inside* application code
(a view, `standard_exception_handler`'s own `logger.exception`) are inside the correlated scope.

**This is exactly the kind of hole a unit test could have caught, and none did** — the existing
`appkit_frozen_request_id` fixture and appkit's own `test_request_id.py` only ever assert the
*contextvar* is set/reset correctly, never that Django's *own* automatic request logging
correlates with it. Recommend: document the caveat in `docs/CONTRACT.md` §2.4 and `README.md`'s
"Known caveats" section, and/or add a unit test asserting on `caplog` for the `django.request`
logger specifically, so nobody re-discovers this expecting different behaviour.

---

## 8. Cache isolation, staleness, and invalidation — `tests/live/test_cache_isolation.py`

**No appkit-side issues.** Against real Redis, three properties proven in one sequence (not
independently, so the isolation claim is load-bearing, not incidental): user A's second fetch
returns a **stale** cached count (proves caching); user B's **first-ever** fetch returns the
**fresh** count, not user A's stale one (proves the cache key is genuinely per-user — a shared-
key bug would have made user B see user A's stale value); `invalidate_namespace` makes user A see
fresh data afterward (proves invalidation). See the test file's own docstring for why "user B's
first fetch is fresh" is the specific assertion that rules out a shared-key implementation, not
just "caching exists."

---

## 9. Throttling — `tests/live/test_throttle.py`, `test_envelope_http.py`

**No appkit-side issues.** `demo_list: "5/min"` against real Redis: exactly 5 requests succeed,
the 6th and 7th are `429`, carrying both `Retry-After` and the `throttled` envelope code.

---

## 10. Both extras, and what a bare install actually shows

**10.1 — appkit's own ImportError messages are correct and actionable**, confirmed by invoking
`appkit.crypto.Cipher` and `appkit.files.validate_image` directly inside a container built with
neither extra:

```
CRYPTO ERROR: ImportError - appkit.crypto requires the 'cryptography' package.
  Install with: uv add "appkit[crypto]" (or: pip install "appkit[crypto]")
IMAGES ERROR: ImportError - appkit.files.validate_image requires the 'Pillow' package
  for image dimension reading. Install with: uv add "appkit[images]" (or: pip install "appkit[images]")
```

**10.2 — Demo-design artifact, not an appkit bug, worth flagging so it isn't mistaken for one:**
`demo.SecretNote.image` is a plain Django `ImageField`, which Django's *own* system check
(`fields.E210`) requires Pillow for regardless of what `appkit.files` needs — so a bare
(`PLAYGROUND_EXTRAS=bare`) container never boots far enough (`manage.py migrate`'s own
`check` gate) to reach any of appkit's own code paths:

```
demo.SecretNote.image: (fields.E210) Cannot use ImageField because Pillow is not installed.
```

This is the *actual* error text a real bare-install project sees first — Django's own, not
appkit's — which is itself a useful, honest data point for the brief's "record the actual error
text a real project sees" ask, but it means §10.1's appkit-specific messages had to be exercised
directly (bypassing `manage.py check`) to prove appkit's own error path independently.

---

## 11. The frontend prerequisite — `frontend/dist/` and `npm install`

**Fix belongs in: appkit** (`frontend/package.json`). `frontend/dist/` is gitignored, and there
is **no `prepare`/`prepack` script** — confirmed by reproducing exactly what a real host would
hit: `npm install "github:HjtDev/appkit#v1.0.0:frontend"` (or, here, `file:../../frontend`)
does **not** build `dist/`. `npm run build` inside `frontend/` had to run manually before
anything downstream could resolve `"appkit"` at all. Recommend a `prepare` script
(`"prepare": "npm run build"`) so this becomes automatic on install, matching how most published
npm packages handle this exact situation.

---

## 12. Two real, undocumented Next.js/Turbopack interactions

Neither of these appears anywhere in `docs/APP-DESIGN.md`, `docs/CONTRACT.md`, or base-scaffold's
docs. Both are specific to the *pattern* §11.2 mandates (a local package consumed by `file:` path,
outside any npm workspace, for `appkit` itself) — anyone else building a Next.js-based playground
or SDK-consuming test host against a path-linked appkit will hit them too.

**12.1 — `next build`'s static-generation pass needs `export const dynamic = "force-dynamic"`,
from a *server* file, not inline in a `"use client"` page.** Fix belongs in: **APP-DESIGN.md**
(§11.2, as guidance for anyone building a similar playground). `app/page.tsx` (`"use client"`,
calling `useDemoItems()`) failed `next build` with `Error: No QueryClient set, use
QueryClientProvider to set one` — Next's static-generation worker prerenders the client
component with no `<Providers>` in scope. Adding `export const dynamic = "force-dynamic"`
directly to the client file did **not** fix it (the directive is silently ignored when combined
with `"use client"`); splitting into a server-component `page.tsx` (exporting `dynamic`) wrapping
a separate client component (`HomeClient.tsx`, `ErrorsClient.tsx`) was required. `next dev` (this
playground's actual runtime mode) never hit this — only `next build` did, which is exactly why
it's worth documenting: it will surface the moment anyone tries a production build of a similar
setup.

**12.2 — Turbopack's `root` is a hard compilation boundary, and its auto-inference gets it wrong
for this exact layout.** Fix belongs in: **APP-DESIGN.md** (§11.2). Files resolved through a
symlink pointing *outside* Turbopack's inferred project root are excluded from compilation —
`"Module not found: Can't resolve 'appkit'"` — even though plain Node (`node --input-type=module
-e "import('appkit')"`) resolves the exact same specifier from the exact same directory without
error. This repo has three separate `package-lock.json` files (`frontend/`,
`playground/demo-sdk/`, `playground/frontend/` before the fix in finding 13), so Turbopack's
nearest-lockfile root inference has no single correct answer. The fix — pin `turbopack.root`
explicitly in `next.config.ts` — required finding the true common ancestor of *both*
`playground/` (the npm workspace) and `frontend/` (appkit's own, one level above, consumed by
path per §11.2): the **repository root**, not `playground/` and not the Next app's own directory.
Both of the wrong answers were tried and both failed differently (documented in
`playground/frontend/next.config.ts`'s own comment) before landing on the right one — worth
saving the next implementer that detour.

---

## 13. A real bug this playground's own design introduced and then caught

**Fix belongs in: APP-DESIGN.md** (§ "Manager & hook conventions" / §11.2 — guidance for future
SDK authors, not an appkit bug). `demo-sdk/package.json` listed `@tanstack/react-query` as its own
**devDependency** (needed for local `tsc` type-checking of `useQuery`/`useMutation` signatures).
Without a shared npm workspace, this installs a **second, real, physically separate copy** in
`demo-sdk/node_modules/@tanstack/react-query` — distinct from the one `playground/frontend`'s
`QueryClientProvider` uses. `useQuery()` inside `demo-sdk`'s *compiled* code (Node resolution
walks up from the file's own directory) picked up its own local copy, whose `React.Context`
object is not the one the mounted `QueryClientProvider` created:

```
Error: No QueryClient set, use QueryClientProvider to set one
    at useDemoItems (../demo-sdk/dist/hooks/useDemoItems.js:15:20)
```

This is **exactly** the "duplicate copy" class of bug `docs/CONTRACT.md` §2010–2020 and
`runDuplicateCopyGuard` exist to catch — just for `@tanstack/react-query`, which appkit's own
guard neither detects nor can detect (it only guards `appkit`'s own module identity). Fixed by
converting `playground/` into a real npm workspace (`playground/package.json`,
`workspaces: ["frontend", "demo-sdk"]`) so both members share one hoisted, deduped
`node_modules`. `docs/APP-DESIGN.md`'s SDK-authoring guidance (§ "Manager & hook conventions")
never mentions this risk for `react`/`@tanstack/react-query` specifically — worth a line: any
package a consuming SDK declares as a `peerDependency` should never *also* be a real
`devDependency` install target without a workspace guaranteeing dedupe, or the exact bug above
reproduces in any host, not just this playground.

---

## 14. The consuming-SDK path itself — no friction found

**Positive finding, the thing this phase most needed to prove.** `demo-sdk/` — `api/config.ts`
(`useApiClient("demo", "/api/v1/demo")`) → `api/manager.ts` (`DemoManager`, the only place a raw
HTTP call happens) → `hooks/useDemoItems.ts` / `useCreateDemoItem.ts` / `useInvalidateDemoCache.ts`
— compiled cleanly with plain `tsc`, and `npm ls appkit` (once the workspace fix in finding 13
landed) shows **exactly one** physical copy of `appkit`, reachable identically from both
`demo-sdk` and `playground/frontend`:

```
playground@ /app/playground
├─┬ demo-sdk@0.1.0 -> ./demo-sdk
│ └─┬ appkit@0.1.0 -> ./../frontend
└─┬ playground-frontend@0.1.0 -> ./frontend
  └── appkit@0.1.0 deduped -> ./../frontend
```

`useApiClient(key, defaultBasePath)`'s two-required-arguments, throws-on-empty-default design
(`frontend/src/provider.tsx:190-195`) caused zero friction writing the SDK — the pattern in
`docs/APP-DESIGN.md`'s "Manager & hook conventions" section transcribed directly with no
adaptation needed. This is the pattern every future app package's frontend will follow, and
nothing about it needs to change.

---

## Summary — where every fix belongs

| # | Finding | Fix belongs in | Status |
|---|---|---|---|
| 1.1 | README's wiring block splits/reorders CONTRACT §8's own canonical form | `README.md` | ✅ Fixed — one contiguous block, CONTRACT §8 order |
| 1.2 | ASGI / `SECURE_PROXY_SSL_HEADER` / `CACHES` / `ScopedRateThrottle` / `LOGGING` shape all silently required, none stated | `README.md` | ✅ Fixed — new "Four things..." subsection |
| 1.3 | Stale 4-method `HttpClient` excerpt | `APP-DESIGN.md` | ✅ Fixed — `put` added, `headerSources` added, types corrected |
| 6 | No copy-pasteable nginx config; two real mistakes resulted | `base-scaffold` (flagged) | Flagged only — separate repo |
| 7.2 | `django.request` auto-logger structurally never carries the request ID | `CONTRACT.md` (document), + a unit test worth adding | ✅ Documented in CONTRACT.md §2.4 and README's "Known caveats"; unit test still open |
| 10.2 | Django's own `fields.E210` masks appkit's own error path in a bare install | note only, no fix needed | N/A |
| 11 | `frontend/dist/` never auto-builds on install | `appkit` (`prepare` script) | ✅ Fixed — `frontend/package.json` |
| 12 | `dynamic="force-dynamic"` placement + `turbopack.root` both undocumented, both non-obvious | `APP-DESIGN.md` §11.2 | ✅ Fixed — new guidance in §11.2 |
| 13 | Undeduped `@tanstack/react-query` copy without an npm workspace | `APP-DESIGN.md` (SDK-authoring guidance) | ✅ Fixed — extended the peer-dependency bullet |
| 2–5, 8, 9, 14 | Everything else checked | **no issues found** | N/A |
