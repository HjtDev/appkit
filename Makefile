# Local dev/test targets. Every test target brings up docker-compose.test.yml's ephemeral
# Postgres first and tears it down after — a fresh clone needs nothing pre-installed beyond
# Docker and uv. See CLAUDE.md's Commands block for the equivalent raw commands.

.PHONY: test test-bare lint typecheck check sync-readmes

# The authoritative gate — both extras installed, >=95% coverage (docs/CONTRACT.md §9's
# two-leg test strategy).
test:
	docker compose -f docker-compose.test.yml up -d --wait
	trap 'docker compose -f docker-compose.test.yml down' EXIT; \
	(cd backend && \
	POSTGRES_HOST=localhost POSTGRES_PORT=55432 \
	POSTGRES_DB=test_appkit POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres \
	uv run --extra crypto --extra images pytest)

# The bare-install leg — neither extra, proves the core stands alone. `--exact` matters: it
# removes cryptography/pillow if a prior `make test` run left them in the venv. Restores both
# extras once the bare run finishes, either way — the venv is a shared dev environment, not
# something later targets (or a developer's next command) should find in a bare state.
test-bare:
	docker compose -f docker-compose.test.yml up -d --wait
	trap 'docker compose -f docker-compose.test.yml down' EXIT; \
	(cd backend && \
	POSTGRES_HOST=localhost POSTGRES_PORT=55432 \
	POSTGRES_DB=test_appkit POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres \
	uv run --exact pytest -m "not requires_extra" --no-cov; \
	status=$$?; \
	uv sync --extra crypto --extra images >/dev/null; \
	exit $$status)

# `.` alone silently skips ../tests (a different root) — both are always checked together.
lint:
	cd backend && uv run ruff check . ../tests && uv run ruff format --check . ../tests

typecheck:
	cd backend && uv run mypy src

check: test lint typecheck test-bare

# The root README.md is the single hand-maintained source; backend/README.md and
# frontend/README.md are committed, generated copies — PyPI and npm each read a package's
# `readme` file relative to ITS OWN project root (backend/, frontend/), never the repo root two
# levels up, so a monorepo publishing from both halves needs a real file in each directory or
# the registry page shows no description at all (found live: v1.0.0 through v2.0.0 all did
# this). CI's `readme-contract` job fails the build if either copy drifts from the original —
# run this and commit both files whenever README.md itself changes.
sync-readmes:
	cp README.md backend/README.md
	cp README.md frontend/README.md

# Phase 6 playground — docs/APP-DESIGN.md §11.2. Brings up Postgres, Redis, both appkit halves
# (linked by path, not tag), and nginx. Requires playground/.env (cp playground/.env.example
# playground/.env first) and appkit's own frontend dist/ built once (`cd frontend && npm run
# build`) — see playground/README.md.
PLAYGROUND_COMPOSE = docker compose -f playground/docker-compose.yml --env-file playground/.env

.PHONY: playground-up playground-down playground-verify playground-bare

playground-up:
	$(PLAYGROUND_COMPOSE) up -d --wait

playground-down:
	$(PLAYGROUND_COMPOSE) down -v

# The live suite (real HTTP through nginx) + both directions of the system checks. Does NOT
# include tests/test_plugin_fixtures.py — that one runs against the LOCAL venv, not `docker
# exec`, and needs POSTGRES_HOST=localhost POSTGRES_PORT=55434 REDIS_URL=redis://localhost:63792/0
# exported first; see playground/README.md.
playground-verify:
	$(PLAYGROUND_COMPOSE) exec backend python manage.py check
	cd playground/backend && \
	set -a && . ../.env && set +a && \
	uv run pytest -m live

# The extras matrix's bare leg — brings the backend up with neither crypto nor images, so
# manage.py check surfaces Django's own fields.E210 (Pillow) rather than a simulated import
# failure. See playground/FINDINGS.md and playground/README.md's "extras matrix" section.
playground-bare:
	PLAYGROUND_EXTRAS=bare $(PLAYGROUND_COMPOSE) build backend
	$(PLAYGROUND_COMPOSE) up -d backend
