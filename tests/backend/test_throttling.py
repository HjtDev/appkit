"""`appkit.throttling` — mechanical construction of DRF throttle-scope strings
(docs/CONTRACT.md §2.15), and its documented complementary (not equivalent) relationship to
`appkit.W004` (`appkit.checks.check_throttle_scopes`, docs/CONTRACT.md §6)."""

from __future__ import annotations

import pytest
from django.test import override_settings

from appkit import checks
from appkit.throttling import throttle_scope


def _ids(messages: list) -> set[str]:
    return {str(m.id) for m in messages}


@pytest.mark.parametrize(
    ("app_namespace", "action", "expected"),
    [
        ("notifications", "list", "notifications_list"),
        ("payments", "retrieve", "payments_retrieve"),
    ],
)
def test_throttle_scope_joins_namespace_and_action(
    app_namespace: str, action: str, expected: str
) -> None:
    assert throttle_scope(app_namespace, action) == expected


@pytest.mark.parametrize(
    ("app_namespace", "action"),
    [
        ("", "list"),
        ("notifications", ""),
        ("", ""),
    ],
)
def test_throttle_scope_rejects_empty_arguments(app_namespace: str, action: str) -> None:
    with pytest.raises(ValueError):
        throttle_scope(app_namespace, action)


@pytest.mark.parametrize(
    ("app_namespace", "action"),
    [
        ("notifications_app", "list"),  # the namespace itself contains an underscore
        ("notifications", "list_all"),  # the action itself contains an underscore
    ],
)
def test_throttle_scope_rejects_an_underscore_in_either_argument(
    app_namespace: str, action: str
) -> None:
    with pytest.raises(ValueError):
        throttle_scope(app_namespace, action)


def test_a_throttle_scope_produced_scope_satisfies_w004_once_registered() -> None:
    """The naming helper and appkit.W004 are complementary, not one defining the other — a
    well-formed scope with a registered rate must not warn. `urls_throttling.py` also mounts
    a deliberately-unregistered `missing-scope` view (`test_checks.py`'s own W004 fixture);
    this test isn't about that view, so its rate is registered too, keeping the assertion
    scoped to the one scope this test actually cares about.
    """
    scope = throttle_scope("notifications", "list")
    with override_settings(
        ROOT_URLCONF="tests.backend.urls_throttling",
        REST_FRAMEWORK={
            "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
            "DEFAULT_THROTTLE_RATES": {
                scope: "10/min",
                "known-scope": "10/min",
                "missing-scope": "10/min",
            },
        },
    ):
        assert "appkit.W004" not in _ids(checks.check_throttle_scopes(app_configs=None))


def test_w004_is_indifferent_to_scope_format() -> None:
    """`tests/backend/urls_throttling.py`'s `known-scope` is hyphenated and unprefixed — not a
    string `throttle_scope()` would ever produce — yet W004 stays silent for it once its rate
    is registered: W004 checks registration only, never naming format. (`missing-scope`'s own
    rate is registered too, so its dedicated, deliberate warning doesn't obscure the point.)
    """
    with override_settings(
        ROOT_URLCONF="tests.backend.urls_throttling",
        REST_FRAMEWORK={
            "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
            "DEFAULT_THROTTLE_RATES": {"known-scope": "10/min", "missing-scope": "10/min"},
        },
    ):
        messages = checks.check_throttle_scopes(app_configs=None)
        assert not any("known-scope" in str(m.msg) for m in messages)
