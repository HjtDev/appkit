"""`appkit.text` — truncation and digit normalisation (docs/CONTRACT.md §2.12)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from appkit.text import to_english_digits, to_persian_digits, truncate


def test_truncate_matches_the_shared_golden_vectors(golden: Callable[[str], Any]) -> None:
    """Fixture-driven from tests/fixtures/truncate-vectors.json — the same file Phase 6's
    Vitest suite loads, per docs/CONTRACT.md §19.
    """
    for vector in golden("truncate-vectors.json"):
        result = truncate(vector["value"], vector["length"], suffix=vector["suffix"])
        assert result == vector["expected"], vector


def test_truncate_example_from_the_contract() -> None:
    assert truncate("hello world", 8) == "hello w…"


def test_to_english_digits_converts_persian_digits() -> None:
    assert to_english_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"


def test_to_english_digits_converts_arabic_indic_digits() -> None:
    assert to_english_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"


def test_to_english_digits_passes_through_unrecognised_characters() -> None:
    assert to_english_digits("abc-۱۲۳-xyz") == "abc-123-xyz"


def test_to_persian_digits_converts_ascii_digits() -> None:
    assert to_persian_digits("0123456789") == "۰۱۲۳۴۵۶۷۸۹"


def test_to_persian_digits_passes_through_non_digit_characters() -> None:
    assert to_persian_digits("abc123xyz") == "abc۱۲۳xyz"  # noqa: RUF001 — Persian digits, deliberate
