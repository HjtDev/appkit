"""Integer money parsing/formatting with fixed ASCII grouping.

Flagged in docs/CONTRACT.md §11 as the contract's second-weakest module — deliberately thin
(a handful of pure functions, zero dependencies) rather than grown into a currency/locale
framework.

Public surface (docs/CONTRACT.md §2.14), implemented in a later phase:

    def parse_amount(value: str | int) -> int: ...
        # Rejects float outright, raising TypeError. Raises ValueError for non-integer
        # strings. Strips , and ٬ thousands separators.

    def format_amount(value: int, *, currency: str = "") -> str: ...
        # Fixed ASCII "," thousands separator regardless of locale — the frontend half
        # deliberately avoids Intl.NumberFormat for the same reason (its grouping character is
        # locale-dependent). See tests/fixtures/money-vectors.json.
"""

from __future__ import annotations
