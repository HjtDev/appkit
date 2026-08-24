"""Trust-boundary parsing of proxy headers to resolve the real client IP.

Public surface (docs/CONTRACT.md §2.10) — the module's only export, implemented in a later
phase:

    def client_ip(request: HttpRequest | Request) -> str: ...
        # Never raises. Uses APPKIT['TRUSTED_PROXY_COUNT'] to read X-Forwarded-For from the
        # right (parts[-N]) — trusts only the proxy-appended entry, never the
        # client-controlled leftmost value.
"""

from __future__ import annotations
