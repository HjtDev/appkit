# Self-signed TLS cert generated AT BUILD TIME — never written to the repo, never committed.
# This is what makes the :8443 listener real TLS rather than a documentation-only claim, so
# appkit.media.absolute_url's https:// behaviour (via request.build_absolute_uri +
# SECURE_PROXY_SSL_HEADER) can be checked against an actual TLS-terminating proxy, per
# docs/BASE-DESIGN.md §9's "nginx is a host-level reverse proxy... TLS termination" model.
FROM nginx:1.27-alpine

RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/certs && \
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout /etc/nginx/certs/playground.key \
        -out /etc/nginx/certs/playground.crt \
        -subj "/CN=playground.local" \
        -addext "subjectAltName=DNS:localhost,DNS:playground.local,IP:127.0.0.1"

COPY nginx.conf /etc/nginx/conf.d/default.conf
