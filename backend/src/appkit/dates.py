"""Gregorian <-> Jalali conversion, formatting, and parsing using stdlib types only.

No third-party type in any public signature — ``jdatetime``/``jalali-core`` stay internal
(docs/CONTRACT.md §9). A major-version bump in either can never force an appkit major bump on
its own.

Public surface (docs/CONTRACT.md §2.13):

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

import datetime as dt
import re
from typing import Final

import jdatetime
from django.utils import timezone

from appkit.text import to_english_digits

__all__ = ["format_jalali", "from_jalali", "parse_jalali", "to_jalali"]

# docs/CONTRACT.md §18: format_jalali/parseJalali support only the numeric directives below —
# no month names ship in v1.0.0 (removes an entire Persian-spelling-drift divergence class
# between the two halves). An unrecognised directive raises, mirroring strftime's own failure
# mode, which stdlib strftime itself does NOT do for %B/%A-style directives it doesn't
# recognise — this is why format_jalali/parse_jalali can't simply delegate to strftime/strptime.
_SUPPORTED_DIRECTIVES: Final[frozenset[str]] = frozenset("YmdHMS%")

_DIRECTIVE_REGEX: Final[dict[str, str]] = {
    "Y": r"\d{1,4}",
    "m": r"\d{1,2}",
    "d": r"\d{1,2}",
    "H": r"\d{1,2}",
    "M": r"\d{1,2}",
    "S": r"\d{1,2}",
}


def to_jalali(value: dt.date | dt.datetime) -> tuple[int, int, int]:
    """Returns `(year, month, day)` for the Jalali calendar date corresponding to `value`.

    **The timezone rule (docs/CONTRACT.md §18), implemented exactly as stated, not re-decided:**
    an *aware* `datetime` is localised via `django.utils.timezone.localtime()` (Django's own
    `TIME_ZONE` setting) before the Jalali date is extracted — a datetime at `23:30 UTC` may
    already be tomorrow in `Asia/Tehran`. A *naive* `datetime` is treated as already-local
    (`localtime()` itself raises on a naive value, so it's simply not called). A plain `date`
    has no timezone component and is converted directly.

    `datetime` is checked before `date` — `datetime` is a subclass of `date`, so the reverse
    order would silently treat every `datetime` as a plain, timezone-naive date. Never raises
    for any valid `date`/`datetime`.
    """
    if isinstance(value, dt.datetime):
        localized = timezone.localtime(value) if timezone.is_aware(value) else value
        gregorian_date = localized.date()
    else:
        gregorian_date = value
    jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
    return jalali_date.year, jalali_date.month, jalali_date.day


def from_jalali(year: int, month: int, day: int) -> dt.date:
    """The inverse of `to_jalali`.

    Raises `ValueError` for an invalid Jalali calendar date (day 31 in a 30-day Jalali month,
    an invalid Esfand 30) — the same exception shape `datetime.date(...)` itself raises for an
    invalid Gregorian date, so callers don't need a Jalali-specific except clause.
    """
    jalali_date = jdatetime.date(year, month, day)  # raises ValueError on an invalid date
    result: dt.date = jalali_date.togregorian()
    return result


def _time_components(value: dt.date | dt.datetime) -> tuple[int, int, int]:
    if not isinstance(value, dt.datetime):
        return 0, 0, 0
    localized = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized.hour, localized.minute, localized.second


def format_jalali(value: dt.date | dt.datetime, fmt: str = "%Y/%m/%d") -> str:
    """`strftime`-style formatting of `value`'s Jalali representation.

    Supports only `%Y %m %d %H %M %S %%` (docs/CONTRACT.md §18 — no month names in v1.0.0).
    Never raises for a valid `date`/`datetime` input; an unsupported directive raises
    `ValueError`, mirroring stdlib `strftime`'s own failure mode for a malformed format string.
    """
    year, month, day = to_jalali(value)
    hour, minute, second = _time_components(value)
    substitutions = {
        "Y": f"{year:04d}",
        "m": f"{month:02d}",
        "d": f"{day:02d}",
        "H": f"{hour:02d}",
        "M": f"{minute:02d}",
        "S": f"{second:02d}",
        "%": "%",
    }

    result: list[str] = []
    i = 0
    while i < len(fmt):
        char = fmt[i]
        if char != "%":
            result.append(char)
            i += 1
            continue
        if i + 1 >= len(fmt):
            raise ValueError(f"appkit.dates.format_jalali: dangling '%' at end of format {fmt!r}")
        directive = fmt[i + 1]
        if directive not in _SUPPORTED_DIRECTIVES:
            raise ValueError(
                f"appkit.dates.format_jalali: unsupported format directive '%{directive}' in "
                f"{fmt!r}"
            )
        result.append(substitutions[directive])
        i += 2
    return "".join(result)


def _compile_format(fmt: str) -> re.Pattern[str]:
    """Builds a matching regex for `fmt`, one named group per first occurrence of a directive.

    A directive repeated in `fmt` gets a non-capturing group on its second+ occurrence — Python
    regex forbids duplicate group names, and there's no meaningful way to prefer one occurrence
    over another for parsing anyway.
    """
    parts: list[str] = []
    seen: set[str] = set()
    i = 0
    while i < len(fmt):
        char = fmt[i]
        if char != "%":
            parts.append(re.escape(char))
            i += 1
            continue
        if i + 1 >= len(fmt):
            raise ValueError(f"appkit.dates.parse_jalali: dangling '%' at end of format {fmt!r}")
        directive = fmt[i + 1]
        if directive == "%":
            parts.append(re.escape("%"))
        elif directive in _DIRECTIVE_REGEX:
            body = _DIRECTIVE_REGEX[directive]
            parts.append(f"(?:{body})" if directive in seen else f"(?P<{directive}>{body})")
            seen.add(directive)
        else:
            raise ValueError(
                f"appkit.dates.parse_jalali: unsupported format directive '%{directive}' in {fmt!r}"
            )
        i += 2
    return re.compile("".join(parts))


def parse_jalali(value: str, fmt: str = "%Y/%m/%d") -> dt.date:
    """The inverse of `format_jalali`.

    Runs `to_english_digits` internally first — Persian-keyboard input is the common real-world
    case for a date typed by a user, not pasted. Raises `ValueError` for a string that doesn't
    match `fmt`, or that names an invalid Jalali date — never returns a best-guess/partial
    result. A directive omitted from `fmt` (e.g. `fmt="%Y"` alone) defaults to `1` for month/day.
    """
    pattern = _compile_format(fmt)
    match = pattern.fullmatch(to_english_digits(value))
    if match is None:
        raise ValueError(f"appkit.dates.parse_jalali: {value!r} does not match format {fmt!r}")

    groups = match.groupdict()
    year = int(groups["Y"]) if groups.get("Y") is not None else 1
    month = int(groups["m"]) if groups.get("m") is not None else 1
    day = int(groups["d"]) if groups.get("d") is not None else 1
    return from_jalali(year, month, day)  # raises ValueError for an invalid Jalali date
