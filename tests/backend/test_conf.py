"""`appkit.conf` — the `APPKIT` settings-dict accessor (docs/CONTRACT.md §2.16)."""

from __future__ import annotations

import pytest
from django.test import override_settings

from appkit import conf


def test_default_returned_for_an_unset_key() -> None:
    with override_settings(APPKIT={}):
        assert conf.get_setting("CACHE_TIMEOUT") == conf.DEFAULTS["CACHE_TIMEOUT"]


def test_host_override_is_honoured() -> None:
    with override_settings(APPKIT={"CACHE_TIMEOUT": 999}):
        assert conf.get_setting("CACHE_TIMEOUT") == 999


def test_default_returned_when_appkit_setting_is_absent_entirely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.conf import settings as django_settings

    monkeypatch.delattr(django_settings, "APPKIT", raising=False)
    for key, default in conf.DEFAULTS.items():
        assert conf.get_setting(key) == default


def test_raises_key_error_for_a_key_not_in_defaults() -> None:
    with override_settings(APPKIT={}), pytest.raises(KeyError):
        conf.get_setting("NOT_A_REAL_KEY")


def test_unset_is_a_distinct_singleton_not_none() -> None:
    assert conf.UNSET is not None
    assert conf.UNSET is conf.UNSET
