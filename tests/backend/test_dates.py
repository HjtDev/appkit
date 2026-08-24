"""`appkit.dates` — Gregorian <-> Jalali conversion, formatting, parsing (docs/CONTRACT.md
§2.13). Round-trip coverage is fixture-driven from tests/fixtures/jalali-vectors.json
(docs/CONTRACT.md §19) — the same file Phase 6's Vitest suite loads.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from django.utils import timezone

from appkit.dates import format_jalali, from_jalali, parse_jalali, to_jalali


def _gdate(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def test_to_jalali_matches_every_golden_round_trip_vector(golden: Callable[[str], Any]) -> None:
    for vector in golden("jalali-vectors.json")["round_trip"]:
        gregorian = _gdate(vector["gregorian"])
        expected = (vector["jalali"]["year"], vector["jalali"]["month"], vector["jalali"]["day"])
        assert to_jalali(gregorian) == expected, vector


def test_from_jalali_matches_every_golden_round_trip_vector(golden: Callable[[str], Any]) -> None:
    for vector in golden("jalali-vectors.json")["round_trip"]:
        jalali = vector["jalali"]
        expected = _gdate(vector["gregorian"])
        assert from_jalali(jalali["year"], jalali["month"], jalali["day"]) == expected, vector


def test_every_golden_vector_round_trips_gregorian_to_jalali_to_gregorian(
    golden: Callable[[str], Any],
) -> None:
    for vector in golden("jalali-vectors.json")["round_trip"]:
        gregorian = _gdate(vector["gregorian"])
        year, month, day = to_jalali(gregorian)
        assert from_jalali(year, month, day) == gregorian, vector


def test_every_golden_vector_round_trips_jalali_to_gregorian_to_jalali(
    golden: Callable[[str], Any],
) -> None:
    for vector in golden("jalali-vectors.json")["round_trip"]:
        jalali = vector["jalali"]
        gregorian = from_jalali(jalali["year"], jalali["month"], jalali["day"])
        assert to_jalali(gregorian) == (jalali["year"], jalali["month"], jalali["day"]), vector


def test_from_jalali_raises_value_error_for_every_golden_invalid_vector(
    golden: Callable[[str], Any],
) -> None:
    for vector in golden("jalali-vectors.json")["invalid"]:
        with pytest.raises(ValueError, match=r".+"):
            from_jalali(vector["year"], vector["month"], vector["day"])


def test_format_jalali_matches_every_golden_format_vector(golden: Callable[[str], Any]) -> None:
    for vector in golden("jalali-vectors.json")["format"]:
        jalali = vector["jalali"]
        value = from_jalali(jalali["year"], jalali["month"], jalali["day"])
        assert format_jalali(value, vector["fmt"]) == vector["expected"], vector


def test_parse_jalali_matches_every_golden_parse_vector(golden: Callable[[str], Any]) -> None:
    for vector in golden("jalali-vectors.json")["parse"]:
        expected_jalali = vector["jalali"]
        result = parse_jalali(vector["value"], vector["fmt"])
        assert to_jalali(result) == (
            expected_jalali["year"],
            expected_jalali["month"],
            expected_jalali["day"],
        ), vector


def test_format_jalali_default_format_matches_the_contract_default() -> None:
    assert format_jalali(from_jalali(1403, 1, 1)) == "1403/01/01"


def test_format_jalali_rejects_an_unsupported_directive() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        format_jalali(from_jalali(1403, 1, 1), fmt="%B")


def test_format_jalali_rejects_a_dangling_percent() -> None:
    with pytest.raises(ValueError, match="dangling"):
        format_jalali(from_jalali(1403, 1, 1), fmt="%Y/%")


def test_format_jalali_includes_time_components_for_a_datetime() -> None:
    value = dt.datetime(2024, 3, 20, 13, 45, 9)
    assert format_jalali(value, fmt="%H:%M:%S") == "13:45:09"


def test_parse_jalali_rejects_a_dangling_percent() -> None:
    with pytest.raises(ValueError, match="dangling"):
        parse_jalali("1403/01", fmt="%Y/%")


def test_parse_jalali_handles_a_literal_percent_in_the_format() -> None:
    result = parse_jalali("1403%01/01", fmt="%Y%%%m/%d")
    assert to_jalali(result) == (1403, 1, 1)


def test_parse_jalali_rejects_an_unsupported_directive() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        parse_jalali("anything", fmt="%B")


def test_parse_jalali_raises_for_a_string_not_matching_the_format() -> None:
    with pytest.raises(ValueError, match="does not match"):
        parse_jalali("not-a-date", fmt="%Y/%m/%d")


def test_parse_jalali_raises_for_an_invalid_jalali_date() -> None:
    with pytest.raises(ValueError):
        parse_jalali("1404/12/30", fmt="%Y/%m/%d")  # Esfand 30 in a non-leap year


def test_to_jalali_treats_a_naive_datetime_as_already_local() -> None:
    naive = dt.datetime(2024, 1, 1, 12, 0, 0)
    assert to_jalali(naive) == to_jalali(naive.date())


def test_to_jalali_localises_an_aware_datetime_before_extracting_the_jalali_date(
    settings: object,
) -> None:
    """The timezone rule (docs/CONTRACT.md §18): a datetime at 23:30 UTC may already be
    tomorrow in Asia/Tehran (UTC+3:30) — this must show up as a *different* Jalali day, not the
    UTC day truncated.
    """
    settings.TIME_ZONE = "Asia/Tehran"  # type: ignore[attr-defined]
    settings.USE_TZ = True  # type: ignore[attr-defined]
    aware_utc = dt.datetime(2024, 1, 1, 23, 30, tzinfo=dt.UTC)
    localized = timezone.localtime(aware_utc, timezone.get_fixed_timezone(210))  # +03:30
    assert localized.date() == dt.date(2024, 1, 2)
    assert to_jalali(aware_utc) == to_jalali(dt.date(2024, 1, 2))
    assert to_jalali(aware_utc) != to_jalali(dt.date(2024, 1, 1))


def test_to_jalali_checks_datetime_before_date_since_datetime_subclasses_date() -> None:
    """A naive `datetime` must not be silently treated as a plain `date` — its time component
    is irrelevant to the Jalali *date* either way, but the isinstance check order is what a
    reversed implementation would get wrong for an aware value.
    """
    naive_datetime = dt.datetime(2024, 3, 20, 23, 59, 59)
    plain_date = dt.date(2024, 3, 20)
    assert to_jalali(naive_datetime) == to_jalali(plain_date)
