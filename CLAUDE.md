# CLAUDE.md — appkit (app package #1)

A standalone, versioned, dual-package Django + React app package — but not an ordinary one.
`appkit` is what `backend/tools/` (cache, mixins, crypto) and `config/logging.py`'s request-ID
plumbing move into once this ships (`BASE-DESIGN.md` §3). Every subsequent app declares
`appkit` as a dependency and imports its cache mixin, error envelope, and `HttpClient`/provider
instead of reimplementing them (`APP-DESIGN.md` §1.1's exception to "an app never depends on
an app"). It isn't an installable feature — it's what every other app and every host builds on.

**Read `docs/APP-DESIGN.md` in full before making changes**, and `docs/CONTRACT.md` once
Phase 0 writes it. This file is the fast reference.

## The rules that define this package

1. **appkit imports no app package**, and has no `appkit` exception of its own to lean on — it
   depends on the platform (Django, DRF) and nothing else.
2. **Never import anything host-specific** — no `tools.*`, no `core.*`. Structural here:
   appkit *is* what `tools.*` moves into, so importing back would be circular too.
3. **Public surface is its importable modules**, not the three-file shape other apps use — no
   models, no `signals.py`/`services.py`. Backend: `appkit.cache`, `appkit.mixins`,
   `appkit.exceptions`, `appkit.request_id`, rest in `README.md`. Frontend: `src/index.ts`.
4. **Wide dependency ranges, never exact pins**, on `django`, `djangorestframework`, and
   anything else a host also depends on directly.
5. **Both halves release under one tag** — `pyproject.toml`, `package.json`, `CHANGELOG.md`
   agree; CI fails the build otherwise.
6. **Namespace everything landing in a shared namespace** — cache keys, settings keys, `.env`
   keys, throttle-scope helpers. `APP-DESIGN.md` §1.3.

## Blast radius — read before touching a public signature

appkit is the dependency of every other app **and** every host — a breaking change ripples
through the whole ecosystem, not one app. Keep the public surface minimal; prefer additive
changes (new function/optional kwarg: fine; renamed/removed export or changed error-envelope
shape: major bump, see Semver triggers). Ship complete at v1.0.0 rather than growing this
underneath four installed apps — later additions mean re-verifying every dependent app.
**Coverage gate is 95%, not the usual 85%.**

## The frontend boundary — do not "fix" this

appkit owns the `HttpClient` **interface** and the shared `ApiClientProvider`/`useApiClient`
pair — never a client implementation. The host constructs the real client (reads
`NEXT_PUBLIC_API_URL`, handles CSRF, decides credentials mode — all host config) and injects
it via the provider. `APP-DESIGN.md` §12. **Whenever you're about to add a concrete client, a
`fetch` call, or anything reading an env var inside appkit's frontend half — stop.** A future
session "helpfully" moving an implementation in is the most likely way this breaks its own
reason for existing.

## Scope boundary

| In | Out |
|---|---|
| DRF serializers + a query-param validation helper | A parallel validation framework |
| `nh3` sanitisation, an ORM lookup-key allowlist | Generic XSS/SQLi checking — the ORM stops SQLi; blocklisting gives false confidence |
| cache, mixins, exceptions, request-ID, permissions, pagination, files, net, text, dates, money, throttling helpers | Models, migrations, admin |
| `HttpClient` interface + shared provider/hook | A concrete client implementation, Celery/`django.tasks`, UI components (SDK contract, not a component library) |

## Dependency ranges & pinned versions

`APP-DESIGN.md` §1.1 applies harder here than anywhere: appkit is the most widely shared
dependency, so an exact pin is the worst place for one. Every dependency added becomes every
app's dependency — flag it before adding.

| Decision | Value |
|---|---|
| Python | `requires-python = ">=3.13"` (range); `.python-version` pins `3.14` locally |
| Django / DRF | `>=5.2,<7.0` / `>=3.15,<4.0` |
| React / `@tanstack/react-query` (peer deps) | `>=18` / `>=5` |
| Vitest | 4.x, matching the scaffold's own pin |
| Coverage gate | 95% |

## Commands

```bash
cd backend && uv sync
uv run pytest                     # authoritative gate for the Python half
uv run ruff check --fix . && uv run ruff format .
uv run mypy src
uv build

cd frontend && npm ci
npm run test                      # Vitest + MSW — authoritative gate for the TS half
npx tsc --noEmit && npm run lint

# Verify against a real host before tagging
cd playground/backend && uv sync
docker compose -f playground/docker-compose.yml up
```

## Semver triggers — MAJOR bumps even when the diff is small

- Removing/renaming an exported name from any `appkit.*` module, or changing a signature.
- Changing the error envelope's shape, or renaming/removing one of the nine `code` values.
- Changing the `HttpClient` interface, or `useApiClient`'s return shape.
- Renaming a settings key or `.env` key.

Every one needs a **Host action:** line in `CHANGELOG.md` — every host is affected, not apps.

## Working agreement (delete after v1.0.0 ships)

- One phase at a time. Don't create files outside the current phase's scope.
- Re-read the relevant `docs/APP-DESIGN.md` section before writing files it specifies.
- After each phase, run its verification command and paste the real output. Never report
  success you haven't observed.
- If the spec is ambiguous or looks wrong, ask. Don't guess and proceed.
- This package must work in ANY host project. **Whenever you're about to rely on something
  existing outside this package, stop** — that's the constraint this whole design exists for.

## Definition of done

- `README.md`'s config block matches reality: settings, `.env` keys, exported
  modules/functions, `HttpClient` shape (`APP-DESIGN.md` §8).
- Security checklist walked, not assumed (§9, §12).
- Every public function has a happy + failure path test; coverage over 95%.
- Version bumped in all three places; `CHANGELOG.md` entry with `Host action:` lines (§11).
- Playground verified; CI green.

## Git protocol

- Never stage or commit unless explicitly asked. Every diff gets reviewed before it lands.
- Never `git push`, `git reset --hard`, `git checkout <branch>`, force-push, or amend an
  existing commit. Ever. Ask instead.
- When a phase or task is done, don't commit — summarise what changed and the verification
  output that passed, propose a commit message in the format below (fenced, copy-pasteable),
  then stop and wait for review.
- If something needs reverting, say so and let the reviewer do it.

### Commit message format

```
semantic(<scope>): <short_commit_message>

- Add <what was added>
- Remove <what was removed>
- Update <what was changed>
```

Rules for it:
- `semantic` is one of: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `build`, `ci`,
  `perf`, `style`. Use `!` after the scope for a breaking change: `feat(core)!:`.
- `<scope>`: lowercase, one word — `backend`, `frontend`, `api`, `hooks`, `ci`, `deps`,
  `playground`, `docs`. Narrowest scope that covers the change.
- `<short_commit_message>`: imperative mood, lowercase, no trailing period, under 60 chars.
- Blank line after the title, then literal `- `-prefixed bullets, each starting with an
  imperative verb (`Add`, `Remove`, `Update`, `Move`, `Rename`, `Fix`, `Pin`, `Enable`,
  `Disable`), capitalised, no trailing period. Group trivia, don't list every file.
- Host action required (new `.env` key, a config block to copy)? Final line: `Host action: <what to do>`.
- No co-author trailers, no "generated with" footers, no emoji.
- A commit changing an exported name, a signature, the error envelope, `HttpClient`, or a
  settings/`.env` key uses `!` and always gets a `Host action:` line — appkit's blast radius
  means one is needed far more often than for a normal app package.

Example:

```
chore(backend): add uv project config and tooling baseline

- Add backend/pyproject.toml with dependencies, dev/test dependency groups and uv default-groups
- Add ruff, mypy, pytest and coverage configuration
- Add commented banned-api table enforcing the core/-only app import rule
- Add MANIFEST.in, .python-version and .dockerignore
- Update .gitignore to cover .venv, .ruff_cache and .mypy_cache
```
