"""Shared string helpers whose semantics must match the frontend half.

Flagged in docs/CONTRACT.md §11 as one of the contract's two weakest modules — it survives past
``truncate`` alone (which ``django.utils.text.Truncator`` already provides) only because the
frontend half ships a matching ``truncate``, and matching client/server truncation is worth one
small shared function.

Public surface (docs/CONTRACT.md §2.12):

    def truncate(value: str, length: int, *, suffix: str = "…") -> str: ...
        # Counts len() (codepoints) — the frontend's Array.from-based count must agree; see
        # tests/fixtures/truncate-vectors.json.

    def to_english_digits(value: str) -> str: ...
        # Persian ۰۱۲۳۴۵۶۷۸۹ and Arabic-Indic ٠١٢٣٤٥٦٧٨٩ digit sets, normalised to ASCII.

    def to_persian_digits(value: str) -> str: ...
"""

from __future__ import annotations

__all__ = ["to_english_digits", "to_persian_digits", "truncate"]

# Persian and Arabic-Indic digit blocks, both normalised to ASCII by `to_english_digits` — a
# Persian-locale keyboard can emit either set depending on the input method, so both are
# accepted (docs/CONTRACT.md §2.12).
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"

_TO_ENGLISH_TABLE = str.maketrans(_PERSIAN_DIGITS + _ARABIC_INDIC_DIGITS, _ASCII_DIGITS * 2)
_TO_PERSIAN_TABLE = str.maketrans(_ASCII_DIGITS, _PERSIAN_DIGITS)


def truncate(value: str, length: int, *, suffix: str = "…") -> str:
    """Truncates `value` to `length` characters (codepoints), suffix included in the count.

    `truncate("hello world", 8)` -> `"hello w…"` (8 characters total). Never raises: a
    `length <= len(suffix)` returns the suffix itself, clamped to `length` characters (a
    negative `length` clamps to an empty string). Counts `len()` — plain codepoints, not
    grapheme clusters — matching the frontend's `Array.from`-based count (docs/CONTRACT.md §18),
    which is also codepoint-based, not grapheme-based.
    """
    if length <= len(suffix):
        return suffix[: max(length, 0)]
    if len(value) <= length:
        return value
    return value[: length - len(suffix)] + suffix


def to_english_digits(value: str) -> str:
    """Normalises Persian and Arabic-Indic digits to ASCII. Never raises; characters outside
    both digit sets pass through unchanged.
    """
    return value.translate(_TO_ENGLISH_TABLE)


def to_persian_digits(value: str) -> str:
    """Converts ASCII digits to Persian digits. Never raises; non-ASCII-digit characters pass
    through unchanged.
    """
    return value.translate(_TO_PERSIAN_TABLE)
