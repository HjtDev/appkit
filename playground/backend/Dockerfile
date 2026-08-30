# Playground backend image. Built with the REPO ROOT as context (see playground/docker-compose.yml:
# `context: ..`) so the container can preserve the same relative layout as the working tree —
# /app/backend (appkit's own source) and /app/playground/backend — which is what lets
# pyproject.toml's `path = "../../backend"` [tool.uv.sources] entry resolve identically in and
# out of Docker, exactly as docs/APP-DESIGN.md §11.2 specifies (path-linked, not tag-pinned).
#
# ARG PLAYGROUND_EXTRAS switches between "both extras" and "bare" — the extras matrix
# docs/APP-DESIGN.md §11.2 asks for: what does a real project see when a bare install hits a
# crypto/images code path, not a simulated ImportError in a unit test.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

WORKDIR /app

# appkit's own source tree first (rarely changes during playground iteration — good layer cache).
COPY backend/ /app/backend/
# The playground consumer, at the same relative depth it has on disk.
COPY playground/backend/ /app/playground/backend/

ARG PLAYGROUND_EXTRAS=both
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app/playground/backend

RUN if [ "$PLAYGROUND_EXTRAS" = "bare" ]; then \
        sed -i 's/hjtdev-appkit\[crypto,images\]/hjtdev-appkit/' pyproject.toml; \
    fi && \
    uv sync --no-dev

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput --clear && uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
