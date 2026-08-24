"""Gregorian <-> Jalali conversion, formatting, and parsing using stdlib types only.

No third-party type in any public signature — ``jdatetime``/``jalali-core`` stay internal
(docs/CONTRACT.md §9). A major-version bump in either can never force an appkit major bump on
its own.

Public surface (docs/CONTRACT.md §2.13), implemented in a later phase:

    def to_jalali(value: date | datetime) -> tuple[int, int, int]: ...
    def from_jalali(year: int, month: int, day: int) -> date: ...   # raises ValueError
    def format_jalali(value: date | datetime, fmt: str = "%Y/%m/%d") -> str: ...
    def parse_jalali(value: str, fmt: str = "%Y/%m/%d") -> date: ...   # raises ValueError

Golden vectors verified against tests/fixtures/jalali-vectors.json (docs/CONTRACT.md §19):
every leap year in the 33-year Jalali cycle plus adjacent non-leap years, Esfand 29 vs. 30 in
both leap and non-leap years, Nowruz across several years, the 31-day/30-day month-length
boundary, Gregorian leap years including century years, and dates well outside the near present
— every vector round-tripped in both directions.
"""

from __future__ import annotations
