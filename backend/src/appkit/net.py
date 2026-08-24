"""Trust-boundary parsing of proxy headers to resolve the real client IP.

Public surface (docs/CONTRACT.md §2.10) — the module's only export:

    def client_ip(request: HttpRequest | Request) -> str: ...
        # Never raises. Uses APPKIT['TRUSTED_PROXY_COUNT'] to read X-Forwarded-For from the
        # right (parts[-N]) — trusts only the proxy-appended entry, never the
        # client-controlled leftmost value.

**Why from the right, not `REMOTE_ADDR`:** verified directly against the installed
`uvicorn` proxy-headers middleware, not assumed — with the base scaffold's documented prod
command (`--proxy-headers --forwarded-allow-ips "*"`), uvicorn writes the *leftmost*
(client-controlled) `X-Forwarded-For` entry into `scope["client"]`, i.e. into Django's own
`request.META["REMOTE_ADDR"]`. `REMOTE_ADDR` is therefore spoofable end-to-end in that exact
deployment, and this module never reads it for the answer — only as the degraded fallback when
the header itself can't be trusted. nginx's `$proxy_add_x_forwarded_for` *appends* its own peer
address to whatever it received, so with `N` trusted proxies in front, the real client is
`parts[-N]`.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import TYPE_CHECKING

from appkit.conf import get_setting

if TYPE_CHECKING:
    from django.http import HttpRequest
    from rest_framework.request import Request

__all__ = ["client_ip"]

logger = logging.getLogger(__name__)


def _normalize_candidate(raw: str) -> str | None:
    """Validates a single `X-Forwarded-For` entry, stripping brackets/port where present.

    Returns `None` for anything that isn't a valid IPv4/IPv6 address once normalised.
    """
    raw = raw.strip()
    if not raw:
        return None

    if raw.startswith("["):
        # IPv6 in bracket notation, optionally with a port: "[2001:db8::1]:443" or "[2001:db8::1]".
        end = raw.find("]")
        if end == -1:
            return None
        host = raw[1:end]
    elif raw.count(":") == 1:
        # Exactly one colon means "host:port" (IPv4) — a bare IPv6 address always has more than
        # one colon (or the "::" shorthand), so this never misfires on an unbracketed IPv6
        # literal.
        host = raw.split(":", 1)[0]
    else:
        host = raw

    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


def client_ip(request: HttpRequest | Request) -> str:
    """Resolves the real client IP, trusting only the proxy-appended `X-Forwarded-For` entry.

    Reads `APPKIT["TRUSTED_PROXY_COUNT"]` (default `1`) trusted hops and returns the entry
    `TRUSTED_PROXY_COUNT`-th from the **right** of the header — never the leftmost, which a
    client can set (and pre-pend fake hops to) themselves. Never raises: an absent/empty
    header, a header with fewer entries than `TRUSTED_PROXY_COUNT`, a malformed candidate, or a
    non-positive `TRUSTED_PROXY_COUNT` (which would otherwise resolve `parts[-0] == parts[0]`,
    the spoofable leftmost entry) all fall back to the connection's own remote address, with a
    logged warning — degrading to "best available answer" rather than crashing the request.
    """
    trusted_proxy_count = get_setting("TRUSTED_PROXY_COUNT")
    fallback = request.META.get("REMOTE_ADDR", "") or ""

    header = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not header or not header.strip():
        return fallback

    parts = [part.strip() for part in header.split(",")]

    if trusted_proxy_count <= 0:
        logger.warning(
            "client_ip(): TRUSTED_PROXY_COUNT is not positive (%r); falling back to the "
            "direct connection address.",
            trusted_proxy_count,
        )
        return fallback

    if len(parts) < trusted_proxy_count:
        logger.warning(
            "client_ip(): X-Forwarded-For has fewer entries (%d) than TRUSTED_PROXY_COUNT "
            "(%d); falling back to the direct connection address.",
            len(parts),
            trusted_proxy_count,
        )
        return fallback

    candidate = parts[-trusted_proxy_count]
    normalized = _normalize_candidate(candidate)
    if normalized is None:
        logger.warning(
            "client_ip(): X-Forwarded-For candidate %r is not a valid IP address; falling "
            "back to the direct connection address.",
            candidate,
        )
        return fallback

    return normalized
