"""`appkit.validation` — query-param validation, HTML sanitisation, ORM lookup allowlist
(docs/CONTRACT.md §2.8).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.http import QueryDict
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from appkit.exceptions import standard_exception_handler
from appkit.validation import (
    ALLOWED_LOOKUPS,
    safe_filter_kwargs,
    sanitize_html,
    strip_html,
    validate_lookup,
    validate_query_params,
)


class _QuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, default="")
    page = serializers.IntegerField(required=False, min_value=1, default=1)


# ---------------------------------------------------------------- ALLOWED_LOOKUPS


def test_regex_and_iregex_are_not_in_allowed_lookups() -> None:
    """The ReDoS vector this allowlist exists to prevent."""
    assert "regex" not in ALLOWED_LOOKUPS
    assert "iregex" not in ALLOWED_LOOKUPS


def test_exact_is_in_allowed_lookups_but_eq_is_not() -> None:
    """Django has no `eq` lookup — only `exact` is real."""
    assert "exact" in ALLOWED_LOOKUPS
    assert "eq" not in ALLOWED_LOOKUPS


@pytest.mark.parametrize(
    "lookup",
    [
        "exact",
        "iexact",
        "contains",
        "icontains",
        "startswith",
        "endswith",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "isnull",
        "range",
    ],
)
def test_validate_lookup_accepts_every_documented_lookup(lookup: str) -> None:
    assert validate_lookup(lookup) is True


def test_validate_lookup_rejects_regex() -> None:
    assert validate_lookup("regex") is False


def test_validate_lookup_rejects_an_unknown_string() -> None:
    assert validate_lookup("not_a_lookup") is False


# ---------------------------------------------------------------- sanitize_html / strip_html


def test_sanitize_html_keeps_the_default_allowed_tags() -> None:
    result = sanitize_html("<p>hello <strong>world</strong></p>")
    assert result == "<p>hello <strong>world</strong></p>"


def test_sanitize_html_strips_script_nested_inside_an_allowed_tag() -> None:
    """Mandatory: <script> stripped even nested inside an otherwise-allowed tag, not just at
    top level — "we sanitise HTML" is a security claim, asserted directly.
    """
    result = sanitize_html("<p>ok<script>alert(1)</script></p>")
    assert "<script" not in result
    assert "alert(1)" not in result
    assert result == "<p>ok</p>"


def test_sanitize_html_strips_event_handler_attribute_nested_inside_an_allowed_tag() -> None:
    result = sanitize_html('<a href="/x" onmouseover="alert(1)">click</a>')
    assert "onmouseover" not in result
    assert "alert(1)" not in result


def test_sanitize_html_strips_a_disallowed_tag_but_keeps_its_text_content() -> None:
    result = sanitize_html("<b>bold</b> text")
    assert "<b>" not in result
    assert "bold" in result


def test_sanitize_html_accepts_a_custom_allowed_tag_set() -> None:
    result = sanitize_html("<p>x</p><b>y</b>", allowed_tags=["b"])
    assert "<b>y</b>" in result
    assert "<p>" not in result


def test_strip_html_removes_every_tag() -> None:
    result = strip_html("<p>hello <strong>world</strong></p>")
    assert "<" not in result
    assert "hello" in result
    assert "world" in result


def test_strip_html_removes_script_and_its_content() -> None:
    result = strip_html("safe<script>alert(1)</script>")
    assert "alert(1)" not in result
    assert "<script" not in result


# ---------------------------------------------------------------- safe_filter_kwargs


def test_safe_filter_kwargs_rejects_relation_traversal_by_default() -> None:
    """The load-bearing default: `allow_relations=False` must reject `?user__email__icontains=`
    outright.
    """
    params = QueryDict("user__email__icontains=x")
    assert safe_filter_kwargs(params, ["email"], allow_relations=False) == {}


def test_safe_filter_kwargs_counts_segments_not_prefixes() -> None:
    """Mandatory: `allowed_fields=["created_at"]` accepts `?created_at__gte=x` (2 segments) and
    rejects `?created_at__related__gte=x` (3 segments) even though the first segment matches.
    """
    params = QueryDict("created_at__gte=2024-01-01&created_at__related__gte=2024-01-01")
    result = safe_filter_kwargs(params, ["created_at"])
    assert result == {"created_at__gte": "2024-01-01"}


def test_safe_filter_kwargs_rejects_regex_lookup() -> None:
    params = QueryDict("status__regex=^admin")
    assert safe_filter_kwargs(params, ["status"]) == {}


def test_safe_filter_kwargs_drops_unknown_params_without_raising() -> None:
    params = QueryDict("typo_field=x&status=active")
    result = safe_filter_kwargs(params, ["status"])
    assert result == {"status": "active"}


def test_safe_filter_kwargs_bare_field_means_exact() -> None:
    params = QueryDict("status=active")
    assert safe_filter_kwargs(params, ["status"]) == {"status": "active"}


def test_safe_filter_kwargs_coerces_isnull_to_bool() -> None:
    params = QueryDict("deleted_at__isnull=false")
    result = safe_filter_kwargs(params, ["deleted_at"])
    assert result == {"deleted_at__isnull": False}


def test_safe_filter_kwargs_coerces_in_to_a_list() -> None:
    params = QueryDict("status__in=active,pending")
    result = safe_filter_kwargs(params, ["status"])
    assert result == {"status__in": ["active", "pending"]}


def test_safe_filter_kwargs_allow_relations_permits_an_explicitly_allowed_relation_path() -> None:
    params = QueryDict("user__email__icontains=example.com")
    result = safe_filter_kwargs(params, ["user__email"], allow_relations=True)
    assert result == {"user__email__icontains": "example.com"}


def test_safe_filter_kwargs_allow_relations_still_rejects_a_path_not_in_allowed_fields() -> None:
    params = QueryDict("user__ssn__icontains=123")
    result = safe_filter_kwargs(params, ["user__email"], allow_relations=True)
    assert result == {}


def test_safe_filter_kwargs_allow_relations_bare_path_without_a_lookup_suffix_means_exact() -> None:
    """`?user__email=x` with `allow_relations=True`: the trailing segment ("email") isn't a
    recognised lookup, so the whole dotted path is treated as the field, defaulting to exact.
    """
    params = QueryDict("user__email=x")
    result = safe_filter_kwargs(params, ["user__email"], allow_relations=True)
    assert result == {"user__email": "x"}


class _ParamsWithAMissingValue:
    """Duck-types just enough of `QueryDict` to exercise the `raw is None` guard — a real
    `QueryDict.get()` never returns `None` for a key it also yields via `__iter__`, so this
    defensive branch needs a mapping that can disagree with itself to be reached at all.
    """

    def __iter__(self) -> Any:
        yield "status"

    def get(self, key: str) -> str | None:
        return None


def test_safe_filter_kwargs_skips_a_key_whose_value_is_none() -> None:
    result = safe_filter_kwargs(_ParamsWithAMissingValue(), ["status"])  # type: ignore[arg-type]
    assert result == {}


# ---------------------------------------------------------------- validate_query_params


def test_validate_query_params_returns_the_validated_serializer() -> None:
    params = QueryDict("q=hello&page=2")
    serializer = validate_query_params(_QuerySerializer, params)
    assert serializer.validated_data["q"] == "hello"
    assert serializer.validated_data["page"] == 2


def test_validate_query_params_raises_drf_validation_error() -> None:
    params = QueryDict("page=not-a-number")
    with pytest.raises(DRFValidationError):
        validate_query_params(_QuerySerializer, params)


def test_validate_query_params_error_flows_into_the_standard_envelope() -> None:
    params = QueryDict("page=not-a-number")
    try:
        validate_query_params(_QuerySerializer, params)
    except DRFValidationError as exc:
        response = standard_exception_handler(exc, {})
    else:
        pytest.fail("expected a DRFValidationError")
    assert response is not None
    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
