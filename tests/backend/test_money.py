"""`appkit.money` — integer money parsing/formatting (docs/CONTRACT.md §2.14)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from appkit.money import format_amount, parse_amount


def test_parse_amount_matches_the_shared_golden_vectors(golden: Callable[[str], Any]) -> None:
    for vector in golden("money-vectors.json")["parse"]:
        assert parse_amount(vector["input"]) == vector["output"], vector


def test_parse_amount_rejects_invalid_strings(golden: Callable[[str], Any]) -> None:
    for vector in golden("money-vectors.json")["parse_errors"]:
        with pytest.raises(ValueError):
            parse_amount(vector["input"])


def test_parse_amount_rejects_float_with_type_error() -> None:
    with pytest.raises(TypeError):
        parse_amount(12000.0)  # type: ignore[arg-type]


def test_parse_amount_rejects_bool_with_type_error() -> None:
    """`bool` is an `int` subclass in Python but is never a legitimate money amount —
    docs/CONTRACT.md §2.14 doesn't name it explicitly; excluding it is the safer reading.
    """
    with pytest.raises(TypeError):
        parse_amount(True)  # type: ignore[arg-type]


def test_format_amount_matches_the_shared_golden_vectors(golden: Callable[[str], Any]) -> None:
    for vector in golden("money-vectors.json")["format"]:
        assert format_amount(vector["input"], currency=vector["currency"]) == vector["output"]


def test_format_amount_never_raises_for_zero_or_negative() -> None:
    assert format_amount(0) == "0"
    assert format_amount(-500) == "-500"


def test_format_amount_uses_ascii_comma_never_locale_dependent() -> None:
    assert format_amount(1000000) == "1,000,000"
