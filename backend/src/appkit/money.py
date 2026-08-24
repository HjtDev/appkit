"""Integer money parsing/formatting with fixed ASCII grouping.

Flagged in docs/CONTRACT.md §11 as the contract's second-weakest module — deliberately thin
(a handful of pure functions, zero dependencies) rather than grown into a currency/locale
framework.

Public surface (docs/CONTRACT.md §2.14):

    def parse_amount(value: str | int) -> int: ...
        # Rejects float outright, raising TypeError. Raises ValueError for non-integer
        # strings. Strips , and ٬ thousands separators.

    def format_amount(value: int, *, currency: str = "") -> str: ...
        # Fixed ASCII "," thousands separator regardless of locale — the frontend half
        # deliberately avoids Intl.NumberFormat for the same reason (its grouping character is
        # locale-dependent). See tests/fixtures/money-vectors.json.
"""

from __future__ import annotations

from appkit.text import to_english_digits

__all__ = ["format_amount", "parse_amount"]

_THOUSANDS_SEPARATORS = (",", "٬")


def parse_amount(value: str | int) -> int:
    """Parses a digit string or `int` into an `int` amount.

    Accepts Persian/Arabic-Indic digits (normalised via `to_english_digits` first) and strips
    thousands separators (`,`/`٬`) before parsing.

    Raises:
        TypeError: for a `float` (binary floating point can't represent most decimal currency
            amounts exactly, so a float here is a defect in the caller, never a valid input
            format this function should paper over) — and for a `bool`, which is an `int`
            subclass in Python but is never a legitimate money amount (docs/CONTRACT.md §2.14
            doesn't name `bool` explicitly; excluding it is the safer reading, since silently
            accepting `True`/`False` as `1`/`0` would be a confusing surprise for any caller
            that passes a boolean by mistake).
        ValueError: for a string that isn't a valid integer after normalisation (letters,
            multiple separators/decimal points, an empty string).
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"parse_amount() does not accept {type(value).__name__}; pass an int or a digit string."
        )
    if isinstance(value, int):
        return value

    normalized = to_english_digits(value)
    for sep in _THOUSANDS_SEPARATORS:
        normalized = normalized.replace(sep, "")
    normalized = normalized.strip()
    if not normalized or not normalized.lstrip("+-").isdigit():
        raise ValueError(f"parse_amount() received a non-integer string: {value!r}")
    return int(normalized)


def format_amount(value: int, *, currency: str = "") -> str:
    """Thousands-grouped string using a fixed ASCII `,` separator, regardless of locale.

    `1000000` -> `"1,000,000"`, or `"1,000,000 IRT"` with `currency="IRT"`. Never raises for
    any `int` input, including `0` and negative values (`-500` -> `"-500"`). Emits Latin digits
    only — `to_persian_digits` is a caller's separate, explicit choice on the result.
    """
    formatted = f"{value:,}"
    return f"{formatted} {currency}" if currency else formatted
