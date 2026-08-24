"""Shared string helpers whose semantics must match the frontend half.

Flagged in docs/CONTRACT.md §11 as one of the contract's two weakest modules — it survives past
``truncate`` alone (which ``django.utils.text.Truncator`` already provides) only because the
frontend half ships a matching ``truncate``, and matching client/server truncation is worth one
small shared function.

Public surface (docs/CONTRACT.md §2.12), implemented in a later phase:

    def truncate(value: str, length: int, *, suffix: str = "…") -> str: ...
        # Counts len() (codepoints) — the frontend's Array.from-based count must agree; see
        # tests/fixtures/truncate-vectors.json.

    def to_english_digits(value: str) -> str: ...
        # Persian ۰۱۲۳۴۵۶۷۸۹ and Arabic-Indic ٠١٢٣٤٥٦٧٨٩ digit sets, normalised to ASCII.

    def to_persian_digits(value: str) -> str: ...
"""

from __future__ import annotations
