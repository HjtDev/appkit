"""appkit.net.client_ip behind the REAL nginx proxy chain — the condition
docs/CONTRACT.md §2.10 is written for and no unit test can reproduce: a real
$proxy_add_x_forwarded_for append, and a real spoofing attempt against it.
"""

from __future__ import annotations

import ipaddress

import httpx


def test_client_ip_resolves_to_a_real_address(http_client: httpx.Client) -> None:
    body = http_client.get("/api/v1/demo/echo/").json()
    # Must be a syntactically valid IP — not empty, not the literal upstream/container name.
    ipaddress.ip_address(body["client_ip"])


def test_spoofed_leftmost_entry_is_ignored(http_client: httpx.Client) -> None:
    """The whole point of appkit.net.client_ip: reading from the RIGHT of X-Forwarded-For means
    a client-supplied, pre-pended fake entry never becomes the answer — even though uvicorn's
    own --forwarded-allow-ips "*" makes REMOTE_ADDR itself fully spoofable (verified below).
    """
    honest = http_client.get("/api/v1/demo/echo/").json()

    spoofed = http_client.get(
        "/api/v1/demo/echo/", headers={"X-Forwarded-For": "66.66.66.66"}
    ).json()

    assert spoofed["client_ip"] == honest["client_ip"]
    assert spoofed["client_ip"] != "66.66.66.66"
    # The X-Forwarded-For header now has two entries: nginx's $proxy_add_x_forwarded_for
    # appended its own peer address after the client-supplied fake one.
    assert spoofed["x_forwarded_for"].endswith(honest["client_ip"])
    assert spoofed["x_forwarded_for"].startswith("66.66.66.66")

    # The exact spoofing risk docs/CONTRACT.md §2.10 documents: with --forwarded-allow-ips "*",
    # uvicorn's OWN proxy-headers middleware trusts the spoofed value into REMOTE_ADDR/scope
    # ["client"] — this is why appkit.net.client_ip never reads REMOTE_ADDR for its answer.
    assert spoofed["remote_addr"] == "66.66.66.66"
