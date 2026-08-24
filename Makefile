# Local dev/test targets. Every test target brings up docker-compose.test.yml's ephemeral
# Postgres first and tears it down after — a fresh clone needs nothing pre-installed beyond
# Docker and uv. See CLAUDE.md's Commands block for the equivalent raw commands.

.PHONY: test test-bare lint typecheck check

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
