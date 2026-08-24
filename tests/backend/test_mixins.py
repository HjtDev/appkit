"""`appkit.mixins` — CachedListMixin (docs/CONTRACT.md §2.2)."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings
from rest_framework import generics, serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny

from appkit.mixins import CachedListMixin

factory = RequestFactory()


class _TrustPresetUserAuthentication(BaseAuthentication):
    """Test-only authenticator: trusts whatever `.user` was set on the raw Django request
    before it was handed to the view, so tests can drive `CachedListMixin` as two distinct
    users without wiring real sessions/tokens.
    """

    def authenticate(self, request: object) -> tuple[object, None] | None:
        user = getattr(request._request, "user", None)  # type: ignore[attr-defined]
        if user is None:
            return None
        return (user, None)


class _ItemSerializer(serializers.Serializer):
    value = serializers.IntegerField()


class _CallCounter:
    calls = 0


class _ListView(CachedListMixin, generics.ListAPIView):
    cache_namespace = "mixin_ns"
    serializer_class = _ItemSerializer
    permission_classes = [AllowAny]
    authentication_classes = [_TrustPresetUserAuthentication]

    def get_queryset(self) -> list[dict[str, int]]:
        _CallCounter.calls += 1
        return [{"value": _CallCounter.calls}]


class _NoNamespaceView(CachedListMixin, generics.ListAPIView):
    serializer_class = _ItemSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self) -> list[dict[str, int]]:
        return []


class _FakeRequest:
    """Enough to reach `_cache_key`'s namespace check without a full DRF dispatch."""

    def __init__(self, user: object) -> None:
        self.user = user

    def get_full_path(self) -> str:
        return "/items/"


def _request_as(user: object) -> object:
    request = factory.get("/items/")
    request.user = user
    return request


def test_cached_list_mixin_raises_when_cache_namespace_is_empty() -> None:
    view = _NoNamespaceView()
    with pytest.raises(ImproperlyConfigured):
        view.list(_FakeRequest(AnonymousUser()))


def test_second_call_returns_equal_but_not_identical_data() -> None:
    _CallCounter.calls = 0
    view = _ListView.as_view()
    user = User(pk=1)

    first = view(_request_as(user))
    second = view(_request_as(user))

    assert first.data == second.data
    assert first.data is not second.data
    assert _CallCounter.calls == 1  # queryset built once — the second call hit the cache


def test_two_users_never_share_a_cache_entry() -> None:
    _CallCounter.calls = 0
    view = _ListView.as_view()

    response_a = view(_request_as(User(pk=1)))
    response_b = view(_request_as(User(pk=2)))

    assert response_a.data != response_b.data
    assert _CallCounter.calls == 2


def test_cache_timeout_unset_resolves_from_appkit_cache_timeout_setting() -> None:
    _CallCounter.calls = 0
    view = _ListView.as_view()
    user = User(pk=3)

    with override_settings(APPKIT={"CACHE_TIMEOUT": 0}):
        view(_request_as(user))
        view(_request_as(user))

    assert _CallCounter.calls == 2  # CACHE_TIMEOUT=0 expired the entry immediately
