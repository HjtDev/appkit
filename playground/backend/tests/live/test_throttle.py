"""appkit.throttling.throttle_scope + REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] against real
Redis — DEFAULT_THROTTLE_RATES["demo_list"] = "5/min" (playground/backend/config/settings.py).
"""

from __future__ import annotations

import httpx


def test_scope_allows_exactly_the_configured_rate(
    http_client: httpx.Client, new_user_credentials: tuple[str, str]
) -> None:
    statuses = [
        http_client.get("/api/v1/demo/items/", auth=new_user_credentials).status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [200] * 5, statuses
    assert statuses[5:] == [429, 429], statuses


def test_throttled_response_is_the_standard_envelope(
    http_client: httpx.Client, new_user_credentials: tuple[str, str]
) -> None:
    for _ in range(5):
        http_client.get("/api/v1/demo/items/", auth=new_user_credentials)
    r = http_client.get("/api/v1/demo/items/", auth=new_user_credentials)
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "throttled"
    assert body["error"]["request_id"]
    retry_after = r.headers["Retry-After"]
    assert retry_after.isdigit()
