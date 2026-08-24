"""`appkit.cache` — namespace versioning, key building, get-or-set, and endpoint-level
response caching (docs/CONTRACT.md §2.1)."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.response import Response

from appkit.cache import (
    build_cache_key,
    cache_endpoint,
    cached_call,
    invalidate_namespace,
    namespace_version,
)
from appkit.conf import UNSET


class _FakeRequest:
    """Duck-types just what `cache_endpoint` touches: `.user`, `.get_full_path()`, `.headers`."""

    def __init__(self, user: Any, path: str = "/x/", headers: dict[str, str] | None = None):
        self.user = user
        self._path = path
        self.headers = headers or {}

    def get_full_path(self) -> str:
        return self._path


# ---------------------------------------------------------------- namespace_version / invalidate


def test_namespace_version_is_stable_across_repeated_calls() -> None:
    first = namespace_version("stable_ns")
    second = namespace_version("stable_ns")
    assert first == second


def test_namespace_version_is_opaque_never_assume_it_starts_at_one() -> None:
    # Seeded from int(time.time()) (docs/CONTRACT.md §2.1) — a version of literal 1 would mean
    # this test runs at the Unix epoch.
    assert namespace_version("fresh_ns") > 1


def test_invalidate_namespace_returns_strictly_greater_than_before() -> None:
    before = namespace_version("inv_ns")
    after = invalidate_namespace("inv_ns")
    assert after > before


def test_invalidate_namespace_makes_a_previously_cached_value_unreachable() -> None:
    calls: list[int] = []

    def producer() -> str:
        calls.append(1)
        return "value"

    key_before = build_cache_key("gone_ns", "x")
    cached_call(key_before, 60, producer)

    invalidate_namespace("gone_ns")

    key_after = build_cache_key("gone_ns", "x")
    cached_call(key_after, 60, producer)

    assert key_before != key_after
    assert len(calls) == 2  # the second call missed — the old key is unreachable


# ---------------------------------------------------------------------------- build_cache_key


def test_build_cache_key_embeds_namespace_and_version() -> None:
    version = namespace_version("basic_ns")
    key = build_cache_key("basic_ns", "part")
    assert key == f"basic_ns:{version}:part"


def test_build_cache_key_hashes_an_overlong_part() -> None:
    long_part = "x" * 100
    key = build_cache_key("long_ns", long_part)
    segment = key.split(":")[-1]
    assert segment != long_part
    assert len(segment) == 16


def test_build_cache_key_hashes_a_part_containing_the_delimiter() -> None:
    unsafe = "a:b:c"
    key = build_cache_key("unsafe_ns", unsafe)
    segments = key.split(":")
    # namespace, version, hashed-part — the embedded ":" must never smuggle extra segments in.
    assert len(segments) == 3
    assert segments[-1] != unsafe


def test_build_cache_key_hashes_a_user_controlled_search_query() -> None:
    query = "arbitrary user search query; with punctuation & spaces" * 3
    key = build_cache_key("query_ns", query)
    assert query not in key
    assert len(key) < 100


# --------------------------------------------------------------------------------- cached_call


def test_cached_call_hit_and_miss() -> None:
    calls: list[int] = []

    def producer() -> str:
        calls.append(1)
        return "value"

    first = cached_call("cc_key_1", 60, producer)
    second = cached_call("cc_key_1", 60, producer)

    assert first == second == "value"
    assert len(calls) == 1  # producer ran at most once


def test_cached_call_never_caches_a_none_result() -> None:
    calls: list[int] = []

    def producer() -> None:
        calls.append(1)
        return None

    cached_call("cc_key_2", 60, producer)
    cached_call("cc_key_2", 60, producer)

    assert len(calls) == 2  # every call missed — None is never actually served from cache


def test_cached_call_timeout_zero_expires_immediately() -> None:
    calls: list[int] = []

    def producer() -> str:
        calls.append(1)
        return "value"

    cached_call("cc_key_3", 0, producer)
    cached_call("cc_key_3", 0, producer)

    assert len(calls) == 2


def test_cached_call_unset_resolves_from_appkit_cache_timeout_setting() -> None:
    calls: list[int] = []

    def producer() -> str:
        calls.append(1)
        return "value"

    with override_settings(APPKIT={"CACHE_TIMEOUT": 0}):
        cached_call("cc_key_4", UNSET, producer)
        cached_call("cc_key_4", UNSET, producer)

    assert len(calls) == 2  # CACHE_TIMEOUT=0 was honoured, not a hardcoded literal


# ------------------------------------------------------------------------------- cache_endpoint


def test_cache_endpoint_raises_at_decoration_time_for_an_empty_namespace() -> None:
    with pytest.raises(ImproperlyConfigured):
        cache_endpoint(namespace="")(lambda self, request: None)  # type: ignore[misc]


def test_cache_endpoint_never_serves_user_as_cached_response_to_user_b() -> None:
    class _View:
        def __init__(self) -> None:
            self.calls = 0

        @cache_endpoint(namespace="isolation_ns")
        def get(self, request: _FakeRequest) -> Response:
            self.calls += 1
            return Response({"calls": self.calls}, status=200)

    view = _View()
    user_a = User(pk=1, username="a")
    user_b = User(pk=2, username="b")

    resp_a = view.get(_FakeRequest(user_a))
    resp_b = view.get(_FakeRequest(user_b))

    # If B were served A's cached response, both would read {"calls": 1} and `calls` would
    # never reach 2 — the authorization-bypass shape docs/CONTRACT.md §2.1 names explicitly.
    assert resp_a.data != resp_b.data
    assert view.calls == 2


def test_cache_endpoint_per_user_hits_on_repeat_from_the_same_user() -> None:
    class _View:
        def __init__(self) -> None:
            self.calls = 0

        @cache_endpoint(namespace="repeat_ns")
        def get(self, request: _FakeRequest) -> Response:
            self.calls += 1
            return Response({"calls": self.calls}, status=200)

    view = _View()
    user = User(pk=1, username="a")

    first = view.get(_FakeRequest(user))
    second = view.get(_FakeRequest(user))

    assert first.data == second.data == {"calls": 1}
    assert view.calls == 1


def test_cache_endpoint_per_user_false_shares_the_response_across_callers() -> None:
    class _View:
        def __init__(self) -> None:
            self.calls = 0

        @cache_endpoint(namespace="shared_ns", per_user=False)
        def get(self, request: _FakeRequest) -> Response:
            self.calls += 1
            return Response({"calls": self.calls}, status=200)

    view = _View()
    resp_a = view.get(_FakeRequest(User(pk=1)))
    resp_b = view.get(_FakeRequest(User(pk=2)))

    assert resp_a.data == resp_b.data == {"calls": 1}
    assert view.calls == 1


def test_cache_endpoint_vary_headers_creates_distinct_cache_entries() -> None:
    class _View:
        def __init__(self) -> None:
            self.calls = 0

        @cache_endpoint(namespace="header_ns", vary_headers=["Accept-Language"])
        def get(self, request: _FakeRequest) -> Response:
            self.calls += 1
            return Response({"calls": self.calls}, status=200)

    view = _View()
    user = User(pk=1)
    resp_en = view.get(_FakeRequest(user, headers={"Accept-Language": "en"}))
    resp_fa = view.get(_FakeRequest(user, headers={"Accept-Language": "fa"}))

    assert resp_en.data != resp_fa.data
    assert view.calls == 2


def test_cache_endpoint_does_not_cache_a_non_default_status() -> None:
    class _View:
        def __init__(self) -> None:
            self.calls = 0

        @cache_endpoint(namespace="status_ns")  # default cache_statuses=(200,)
        def get(self, request: _FakeRequest) -> Response:
            self.calls += 1
            return Response({"calls": self.calls}, status=403)

    view = _View()
    request = _FakeRequest(User(pk=1))

    view.get(request)
    view.get(request)

    assert view.calls == 2  # a 403 must never be cached — see docs/CONTRACT.md §2.1
