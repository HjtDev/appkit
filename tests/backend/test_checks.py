"""`appkit.checks` — every system check registered by `AppKitConfig.ready()` (docs/CONTRACT.md
§6). Assertions are on check IDs only, never message text — the ID is the stable contract.

The single most important test in this file is `test_no_messages_on_a_correctly_configured_host`:
a check that false-positives on a correctly configured host is the one that gets deleted by the
first person it blocks, so every check is proven silent against appkit's own (correct) test
settings before any positive case is tested.
"""

from __future__ import annotations

import logging

from django.test import override_settings

from appkit import checks
from appkit.request_id import RequestIDFilter


def _ids(messages: list) -> set[str]:
    return {str(m.id) for m in messages}


# --------------------------------------------------------------------------- baseline


def test_no_messages_on_a_correctly_configured_host() -> None:
    """appkit's own tests/backend/settings.py wires MIDDLEWARE, EXCEPTION_HANDLER, and mounts
    only an unscoped view — every check must be silent against it.
    """
    all_messages = [
        *checks.check_request_id_middleware(app_configs=None),
        *checks.check_exception_handler(app_configs=None),
        *checks.check_middleware_order(app_configs=None),
        *checks.check_unknown_settings_keys(app_configs=None),
        *checks.check_throttle_scopes(app_configs=None),
        *checks.check_logging_filter(app_configs=None),
    ]
    assert all_messages == []


# --------------------------------------------------------------------------- E001


def test_e001_when_middleware_is_absent() -> None:
    with override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"]):
        assert "appkit.E001" in _ids(checks.check_request_id_middleware(app_configs=None))


def test_no_e001_when_middleware_is_present() -> None:
    assert "appkit.E001" not in _ids(checks.check_request_id_middleware(app_configs=None))


# --------------------------------------------------------------------------- E002 / W001


def test_e002_when_handler_is_unset() -> None:
    with override_settings(REST_FRAMEWORK={}):
        assert "appkit.E002" in _ids(checks.check_exception_handler(app_configs=None))


def test_e002_when_handler_is_still_drfs_default() -> None:
    with override_settings(
        REST_FRAMEWORK={"EXCEPTION_HANDLER": "rest_framework.views.exception_handler"}
    ):
        assert "appkit.E002" in _ids(checks.check_exception_handler(app_configs=None))


def test_w001_when_handler_is_a_third_party_wrapper() -> None:
    with override_settings(
        REST_FRAMEWORK={"EXCEPTION_HANDLER": "somewhere.else.custom_handler"}
    ):
        ids = _ids(checks.check_exception_handler(app_configs=None))
        assert "appkit.W001" in ids
        assert "appkit.E002" not in ids


def test_no_e002_or_w001_when_handler_is_appkits() -> None:
    ids = _ids(checks.check_exception_handler(app_configs=None))
    assert "appkit.E002" not in ids
    assert "appkit.W001" not in ids


# --------------------------------------------------------------------------- W002


def test_w002_when_request_id_middleware_precedes_security_middleware() -> None:
    with override_settings(
        MIDDLEWARE=[
            "appkit.request_id.RequestIDMiddleware",
            "django.middleware.security.SecurityMiddleware",
        ]
    ):
        assert "appkit.W002" in _ids(checks.check_middleware_order(app_configs=None))


def test_no_w002_in_correct_order() -> None:
    assert "appkit.W002" not in _ids(checks.check_middleware_order(app_configs=None))


def test_no_w002_when_security_middleware_is_absent() -> None:
    with override_settings(MIDDLEWARE=["appkit.request_id.RequestIDMiddleware"]):
        assert "appkit.W002" not in _ids(checks.check_middleware_order(app_configs=None))


# --------------------------------------------------------------------------- W003


def test_w003_when_appkit_dict_has_an_unknown_key() -> None:
    with override_settings(APPKIT={"CACHE_TIMOUT": 30}):
        assert "appkit.W003" in _ids(checks.check_unknown_settings_keys(app_configs=None))


def test_no_w003_when_all_keys_are_known() -> None:
    assert "appkit.W003" not in _ids(checks.check_unknown_settings_keys(app_configs=None))


def test_no_w003_when_appkit_setting_is_absent(monkeypatch) -> None:
    from django.conf import settings as django_settings

    monkeypatch.delattr(django_settings, "APPKIT", raising=False)
    assert "appkit.W003" not in _ids(checks.check_unknown_settings_keys(app_configs=None))


# --------------------------------------------------------------------------- W004


def test_no_w004_with_no_throttled_views_at_all() -> None:
    """Default test-tree URLconf mounts only the unscoped `ping` view."""
    assert "appkit.W004" not in _ids(checks.check_throttle_scopes(app_configs=None))


def test_w004_when_a_scope_has_no_matching_rate() -> None:
    with override_settings(
        ROOT_URLCONF="tests.backend.urls_throttling",
        REST_FRAMEWORK={
            "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
            "DEFAULT_THROTTLE_RATES": {"known-scope": "10/min"},
        },
    ):
        messages = checks.check_throttle_scopes(app_configs=None)
        assert "appkit.W004" in _ids(messages)
        assert any("missing-scope" in str(m.msg) for m in messages)
        assert not any("known-scope" in str(m.msg) for m in messages)


def test_no_w004_when_every_scope_has_a_rate() -> None:
    with override_settings(
        ROOT_URLCONF="tests.backend.urls_throttling",
        REST_FRAMEWORK={
            "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
            "DEFAULT_THROTTLE_RATES": {"known-scope": "10/min", "missing-scope": "5/min"},
        },
    ):
        assert "appkit.W004" not in _ids(checks.check_throttle_scopes(app_configs=None))


def test_no_w004_with_unset_root_urlconf() -> None:
    with override_settings(ROOT_URLCONF=None):
        assert checks.check_throttle_scopes(app_configs=None) == []


def test_no_w004_with_unimportable_root_urlconf() -> None:
    with override_settings(ROOT_URLCONF="this.module.does.not.exist"):
        assert checks.check_throttle_scopes(app_configs=None) == []


def test_w004_recurses_into_a_nested_include() -> None:
    """A scope declared behind one level of `include()` must be found too — the walk recurses
    into every nested `URLResolver`, not just the top-level pattern list.
    """
    with override_settings(
        ROOT_URLCONF="tests.backend.urls_throttling_nested",
        REST_FRAMEWORK={
            "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
            "DEFAULT_THROTTLE_RATES": {"known-scope": "10/min"},
        },
    ):
        messages = checks.check_throttle_scopes(app_configs=None)
        assert any("missing-scope" in str(m.msg) for m in messages)


# --------------------------------------------------------------------------- W005


class _SubclassedRequestIDFilter(RequestIDFilter):
    """A host subclassing to add a field — must still count as correctly configured."""


# A pre-built instance, resolved via import_string exactly like a class would be — covers the
# `isinstance(resolved, RequestIDFilter)` branch, distinct from the `is`/`issubclass` branches
# above it.
_shared_filter_instance = RequestIDFilter()


# check_logging_filter reads settings.LOGGING/LOGGING_CONFIG but never calls dictConfig itself
# (docs/CONTRACT.md §4 — it inspects host policy, never enacts it). Django's own test signal
# handler DOES call the real logging.config.dictConfig(...) whenever `LOGGING` changes via
# `override_settings`, though, which would crash on the deliberately-unimportable filter path
# these tests exercise before the check under test ever runs — and would leak a real
# reconfiguration of process-wide logging into the rest of the suite besides. `monkeypatch` sets
# the attribute directly, without firing that signal, so these tests observe only the check
# function's own behaviour.


def _set_logging(monkeypatch, *, logging_dict, logging_config="logging.config.dictConfig"):
    from django.conf import settings as django_settings

    monkeypatch.setattr(django_settings, "LOGGING", logging_dict, raising=False)
    monkeypatch.setattr(django_settings, "LOGGING_CONFIG", logging_config, raising=False)


def test_no_w005_when_logging_is_unset(monkeypatch) -> None:
    _set_logging(monkeypatch, logging_dict=None)
    assert checks.check_logging_filter(app_configs=None) == []


def test_no_w005_when_logging_config_is_none(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={"version": 1, "handlers": {"console": {"class": "logging.StreamHandler"}}},
        logging_config=None,
    )
    assert checks.check_logging_filter(app_configs=None) == []


def test_w005_when_no_filter_resolves_to_request_id_filter(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "handlers": {"console": {"class": "logging.StreamHandler", "filters": []}},
        },
    )
    assert "appkit.W005" in _ids(checks.check_logging_filter(app_configs=None))


def test_w005_when_filter_declared_but_no_handler_references_it(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {"request_id": {"()": "appkit.request_id.RequestIDFilter"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "filters": []}},
        },
    )
    assert "appkit.W005" in _ids(checks.check_logging_filter(app_configs=None))


def test_no_w005_when_filter_is_registered_under_a_non_obvious_key(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {"corr-id": {"()": "appkit.request_id.RequestIDFilter"}},
            "handlers": {
                "console": {"class": "logging.StreamHandler", "filters": ["corr-id"]}
            },
        },
    )
    assert checks.check_logging_filter(app_configs=None) == []


def test_no_w005_when_filter_is_a_subclass(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {
                "request_id": {"()": "tests.backend.test_checks._SubclassedRequestIDFilter"}
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "filters": ["request_id"]}
            },
        },
    )
    assert checks.check_logging_filter(app_configs=None) == []


def test_no_w005_when_resolved_filter_is_a_pre_built_instance(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {
                "request_id": {"()": "tests.backend.test_checks._shared_filter_instance"}
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "filters": ["request_id"]}
            },
        },
    )
    assert checks.check_logging_filter(app_configs=None) == []


def test_no_crash_on_a_filter_entry_missing_the_callable_key(monkeypatch) -> None:
    """A `filters` entry using dictConfig's `"class"` key instead of `"()"` (or any other shape
    without a callable target) must be skipped, not crash — only the shape appkit's own filter
    is registered under (`"()"`) is one this check knows how to resolve.
    """
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {"plain": {"name": "some.other.logger"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "filters": ["plain"]}},
        },
    )
    assert "appkit.W005" in _ids(checks.check_logging_filter(app_configs=None))


def test_no_crash_on_unimportable_filter_and_other_entries_still_evaluated(monkeypatch) -> None:
    _set_logging(
        monkeypatch,
        logging_dict={
            "version": 1,
            "filters": {
                "broken": {"()": "this.does.not.exist.AtAll"},
                "request_id": {"()": "appkit.request_id.RequestIDFilter"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "filters": ["broken", "request_id"],
                }
            },
        },
    )
    assert checks.check_logging_filter(app_configs=None) == []
