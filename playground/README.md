# appkit playground

Phase 6, `docs/APP-DESIGN.md` §11.2 / `docs/CLAUDE-CODE-GUIDE-APP.md`'s Phase 6 brief: proves the
two halves of appkit agree with **each other** over a real HTTP connection, and that the wiring
block in the top-level `README.md` produces a working project when pasted literally. See
`FINDINGS.md` for what this actually found.

## What's here

| Path | What it is |
|---|---|
| `backend/` | A minimal Django host — `config/settings.py` is the README's wiring block pasted verbatim between two banner comments, plus a host baseline a real project would already have |
| `backend/demo/` | A throwaway app exercising every appkit integration point: cached/paginated list, client_ip/media echo, crypto+files/images uploads, all ten error codes, permissions, throttling |
| `backend/config/broken/` | One settings module per system-check ID — proves each fires, and only when it should |
| `backend/tests/live/` | `pytest -m live` — hits the real running stack over HTTP through nginx |
| `backend/tests/test_plugin_fixtures.py` | Exercises `-p appkit.testing` as a real consumer, wired in `pyproject.toml`'s own `addopts` |
| `demo-sdk/` | A throwaway consuming SDK — the `useApiClient` → manager → hooks binding pattern every future app package's frontend takes |
| `frontend/` | A minimal Next App Router app: `lib/api-client.ts` (adapted from base-scaffold, rewired to appkit's `apiErrorFromEnvelope`), `/` (demo items) and `/errors` (all ten codes, click-through) |
| `nginx/` | Fronts the backend on `:8080` (http) and `:8443` (self-signed TLS) — required to test `client_ip`/`absolute_url` for real, not just by reasoning about proxy headers |
| `package.json` | The npm **workspace** root for `frontend/` + `demo-sdk/` — required, not optional; see `FINDINGS.md` for the duplicate-`@tanstack/react-query`-copy bug this exists to prevent |

## Running it

```bash
# One-time: appkit's own frontend dist/ is gitignored. frontend/package.json's `prepare`
# script builds it on `npm install`, but this dependency is path-linked (`file:../../frontend`),
# so build it explicitly to avoid running against a stale dist/ from a previous checkout.
cd frontend && npm run build && cd ../..

cp playground/.env.example playground/.env
# fill in DEMO_FERNET_KEY per the comment in .env.example

cd backend && uv sync && cd ../..           # local venv, for tests/live and IDE support
cd playground && npm install && cd ..       # npm workspace root — frontend + demo-sdk together

docker compose -f playground/docker-compose.yml --env-file playground/.env up -d --wait
```

Then:

- Backend direct: http://localhost:8000
- Through nginx: http://localhost:8080 / https://localhost:8443 (self-signed — `curl -k` / accept the browser warning)
- Frontend: http://localhost:3000 (`/` — demo items; `/errors` — all ten codes)
- Django admin: http://localhost:8080/admin/ (create a superuser first: `docker compose -f playground/docker-compose.yml exec backend python manage.py createsuperuser`)

## Verification

```bash
# System checks — both directions
docker compose -f playground/docker-compose.yml exec backend python manage.py check   # silent
docker compose -f playground/docker-compose.yml exec backend python manage.py check \
  --settings=config.broken.no_middleware                                              # appkit.E001
# ...and the other six modules under backend/config/broken/

# The live suite — real HTTP through nginx
cd playground/backend
export $(grep -v '^#' ../.env | xargs)
uv run pytest -m live

# The -p appkit.testing opt-in path — needs the compose Postgres/Redis reachable locally
export POSTGRES_HOST=localhost POSTGRES_PORT=55434 REDIS_URL=redis://localhost:63792/0
uv run pytest -m "not live"
```

## The extras matrix

```bash
PLAYGROUND_EXTRAS=bare docker compose -f playground/docker-compose.yml --env-file playground/.env build backend
docker compose -f playground/docker-compose.yml --env-file playground/.env up -d backend
# manage.py check now fails on Django's OWN fields.E210 (Pillow) before appkit's own code
# ever runs — see FINDINGS.md for why, and how to reach appkit.crypto's/appkit.files' own
# actionable ImportError messages directly.

# Restore:
docker compose -f playground/docker-compose.yml --env-file playground/.env build backend
docker compose -f playground/docker-compose.yml --env-file playground/.env up -d backend
```

## Manual browser check

`/` — create an item, invalidate the server cache, watch pagination. `/errors` — click through
all ten codes (some depend on the `/admin/` session: logged out → `not_authenticated` fires for
`permission_denied` too; log in as a non-staff user → `permission_denied`; staff → 200). Then
`docker compose -f playground/docker-compose.yml stop backend` and click again — nginx's HTML
502 should degrade to a well-formed `ApiError` (`code: "unknown_error"`), never an unhandled
throw.

## Tearing down

```bash
docker compose -f playground/docker-compose.yml --env-file playground/.env down -v
```
