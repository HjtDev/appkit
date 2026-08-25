"""appkit.mixins.CachedListMixin against REAL Redis — user-aware isolation, staleness, and
appkit.cache.invalidate_namespace, over real HTTP through nginx.

DemoItemListView's queryset is Django-truth-shared across every user (it's not per-owner
filtered) — deliberately, so the ONLY thing that can differ between two users' responses is the
cache key appkit.mixins.CachedListMixin builds from (namespace, per-user token, full_path). That
is what makes "user B's first-ever fetch returns current truth, not user A's stale cached blob"
a real proof of per-user isolation, not just of caching working at all.
"""

from __future__ import annotations

import httpx


def _create_item(http_client: httpx.Client, creds: tuple[str, str], name: str) -> None:
    r = http_client.post(
        "/api/v1/demo/items/", json={"name": name}, auth=creds
    )
    assert r.status_code == 201, r.text


def test_isolation_staleness_and_invalidation(
    http_client: httpx.Client,
    new_user_credentials: tuple[str, str],
) -> None:
    user_a = new_user_credentials
    from tests.live.conftest import run_manage
    import uuid

    # A second, independent fresh user — new_user_credentials only gives one per test.
    user_b_name = f"live-{uuid.uuid4().hex[:12]}"
    user_b_password = "live-test-password-123"  # noqa: S105
    script = (
        "from django.contrib.auth import get_user_model; "
        "U = get_user_model(); "
        f"U.objects.create_user({user_b_name!r}, password={user_b_password!r})"
    )
    result = run_manage(["shell", "-c", script])
    assert result.returncode == 0, result.stderr
    user_b = (user_b_name, user_b_password)

    # 1. User A's first-ever fetch — populates A's own cache entry with count N.
    count_n = http_client.get("/api/v1/demo/items/", auth=user_a).json()["count"]

    # 2. DB truth changes (a new item lands) without either user's cache being touched.
    _create_item(http_client, user_a, f"isolation-probe-{uuid.uuid4().hex[:8]}")

    # 3. User A re-fetches: STALE, still count_n — proves the cache actually caches.
    stale = http_client.get("/api/v1/demo/items/", auth=user_a).json()["count"]
    assert stale == count_n, "user A's second fetch should have hit the stale cached entry"

    # 4. User B's FIRST-EVER fetch: must be FRESH (count_n + 1) — if the cache key weren't
    # per-user, this would incorrectly return user A's stale cached count_n instead.
    fresh_for_b = http_client.get("/api/v1/demo/items/", auth=user_b).json()["count"]
    assert fresh_for_b == count_n + 1, (
        f"cache isolation failure: user B's first fetch got {fresh_for_b}, "
        f"expected the FRESH count {count_n + 1} — got user A's stale value instead"
    )

    # 5. Invalidate the shared namespace; user A now sees the fresh count too.
    inv = http_client.post("/api/v1/demo/items/invalidate/", auth=user_a)
    assert inv.status_code == 200
    after_invalidate = http_client.get("/api/v1/demo/items/", auth=user_a).json()["count"]
    assert after_invalidate == count_n + 1
