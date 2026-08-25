/**
 * Gregorian <-> Jalali conversion, formatting, and parsing — mirrors the backend
 * (`appkit.dates`, docs/CONTRACT.md §18 <-> §2.13).
 *
 * **The timezone rule, restated because correct arithmetic alone still produces a wrong answer
 * without it:** the backend decides the calendar date; the frontend only formats and parses it.
 * `toJalali`/`fromJalali` accept only a date-only value (a `"YYYY-MM-DD"` string or a
 * `JalaliDate`), never a raw `Date`/instant — this is what makes it impossible to silently
 * re-derive "today" using the browser's own local timezone and disagree with the calendar date
 * the backend already committed to. `calendarDateIn(instant, timeZone)` is the one explicit
 * escape hatch for a caller holding a real ISO instant who needs *a* calendar date from it.
 */

import { isValidJalaaliDate, toGregorian, toJalaali as toJalaaliVendor } from "./vendor/jalaali.js";
import { toEnglishDigits } from "./text.js";

export interface JalaliDate {
  year: number;
  month: number;
  day: number;
}

const ISO_DATE_RE = /^(-?\d{1,6})-(\d{2})-(\d{2})$/;

function pad(n: number, width: number): string {
  const sign = n < 0 ? "-" : "";
  return sign + Math.abs(n).toString().padStart(width, "0");
}

function parseIsoDate(value: string): { year: number; month: number; day: number } {
  const match = ISO_DATE_RE.exec(value);
  if (!match) {
    throw new Error(`appkit.dates: ${JSON.stringify(value)} is not a "YYYY-MM-DD" date string.`);
  }
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

/**
 * `value` is a **Gregorian** date — either a `"YYYY-MM-DD"` string or a `{year, month, day}`
 * triple (the `JalaliDate` shape reused as a plain calendar-date shape for the *input*; the
 * return value is the Jalali one). Never accepts a `Date`/instant — see `calendarDateIn`.
 */
export function toJalali(value: string | JalaliDate): JalaliDate {
  const gregorian = typeof value === "string" ? parseIsoDate(value) : value;
  const jalaali = toJalaaliVendor(gregorian.year, gregorian.month, gregorian.day);
  return { year: jalaali.jy, month: jalaali.jm, day: jalaali.jd };
}

/**
 * The inverse of `toJalali`. Returns a `"YYYY-MM-DD"` Gregorian date string.
 *
 * Raises `Error` for an invalid Jalali calendar date (day 31 in a 30-day Jalali month, an
 * invalid Esfand 30) — mirroring the backend's `ValueError` from `jdatetime.date(...)`.
 */
export function fromJalali(value: JalaliDate): string {
  if (!isValidJalaaliDate(value.year, value.month, value.day)) {
    throw new Error(
      `appkit.dates.fromJalali: ${JSON.stringify(value)} is not a valid Jalali calendar date.`,
    );
  }
  const gregorian = toGregorian(value.year, value.month, value.day);
  return `${pad(gregorian.gy, 4)}-${pad(gregorian.gm, 2)}-${pad(gregorian.gd, 2)}`;
}

// docs/CONTRACT.md §18: formatJalali/parseJalali support only the numeric directives below —
// no month names ship in v1.0.0 (removes a Persian-spelling-drift divergence class between the
// two halves). An unrecognised directive raises, mirroring `backend/src/appkit/dates.py`'s
// `format_jalali`/`parse_jalali` exactly (which itself deviates from `strftime`'s own lenient
// handling of directives it doesn't recognise, for the same reason).
const SUPPORTED_DIRECTIVES = new Set(["Y", "m", "d", "H", "M", "S", "%"]);

const DIRECTIVE_REGEX: Record<string, string> = {
  Y: "\\d{1,4}",
  m: "\\d{1,2}",
  d: "\\d{1,2}",
  H: "\\d{1,2}",
  M: "\\d{1,2}",
  S: "\\d{1,2}",
};

/**
 * `strftime`-style formatting of `value`'s Jalali representation. Supports only
 * `%Y %m %d %H %M %S %%` — `JalaliDate` carries no time component, so `%H`/`%M`/`%S` always
 * render as `"00"` (never derived from an ambient clock). Never raises for a valid
 * `JalaliDate`; an unsupported directive raises `Error`, mirroring the backend's `ValueError`.
 */
export function formatJalali(value: JalaliDate, fmt = "%Y/%m/%d"): string {
  const substitutions: Record<string, string> = {
    Y: pad(value.year, 4),
    m: pad(value.month, 2),
    d: pad(value.day, 2),
    H: "00",
    M: "00",
    S: "00",
    "%": "%",
  };

  const result: string[] = [];
  let i = 0;
  while (i < fmt.length) {
    const char = fmt[i]!;
    if (char !== "%") {
      result.push(char);
      i += 1;
      continue;
    }
    if (i + 1 >= fmt.length) {
      throw new Error(
        `appkit.dates.formatJalali: dangling '%' at end of format ${JSON.stringify(fmt)}`,
      );
    }
    const directive = fmt[i + 1]!;
    if (!SUPPORTED_DIRECTIVES.has(directive)) {
      throw new Error(
        `appkit.dates.formatJalali: unsupported format directive '%${directive}' in ${JSON.stringify(fmt)}`,
      );
    }
    result.push(substitutions[directive]!);
    i += 2;
  }
  return result.join("");
}

/** Builds a matching regex for `fmt`, one named group per first occurrence of a directive — a
 * directive repeated in `fmt` gets a non-capturing group on its second+ occurrence, mirroring
 * `backend/src/appkit/dates.py`'s `_compile_format`. */
function compileFormat(fmt: string): RegExp {
  const parts: string[] = [];
  const seen = new Set<string>();
  let i = 0;
  while (i < fmt.length) {
    const char = fmt[i]!;
    if (char !== "%") {
      parts.push(char.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      i += 1;
      continue;
    }
    if (i + 1 >= fmt.length) {
      throw new Error(
        `appkit.dates.parseJalali: dangling '%' at end of format ${JSON.stringify(fmt)}`,
      );
    }
    const directive = fmt[i + 1]!;
    if (directive === "%") {
      parts.push("%");
    } else if (directive in DIRECTIVE_REGEX) {
      const body = DIRECTIVE_REGEX[directive]!;
      parts.push(seen.has(directive) ? `(?:${body})` : `(?<${directive}>${body})`);
      seen.add(directive);
    } else {
      throw new Error(
        `appkit.dates.parseJalali: unsupported format directive '%${directive}' in ${JSON.stringify(fmt)}`,
      );
    }
    i += 2;
  }
  return new RegExp(`^${parts.join("")}$`);
}

/**
 * The inverse of `formatJalali`. Runs `toEnglishDigits` internally first — Persian-keyboard
 * input is the common real-world case for a date typed by a user, not pasted. Raises `Error`
 * for a string that doesn't match `fmt`, or that names an invalid Jalali date — never returns a
 * best-guess/partial result. A directive omitted from `fmt` defaults to `1` for year/month/day.
 */
export function parseJalali(value: string, fmt = "%Y/%m/%d"): JalaliDate {
  const pattern = compileFormat(fmt);
  const match = pattern.exec(toEnglishDigits(value));
  if (!match) {
    throw new Error(
      `appkit.dates.parseJalali: ${JSON.stringify(value)} does not match format ${JSON.stringify(fmt)}`,
    );
  }

  const groups = match.groups ?? {};
  const year = groups.Y !== undefined ? Number(groups.Y) : 1;
  const month = groups.m !== undefined ? Number(groups.m) : 1;
  const day = groups.d !== undefined ? Number(groups.d) : 1;

  return fromJalaliChecked(year, month, day);
}

function fromJalaliChecked(year: number, month: number, day: number): JalaliDate {
  if (!isValidJalaaliDate(year, month, day)) {
    throw new Error(
      `appkit.dates.parseJalali: (${year}, ${month}, ${day}) is not a valid Jalali calendar date.`,
    );
  }
  return { year, month, day };
}

/**
 * The explicit bridge from an instant to a calendar date in a given zone. `timeZone` is a
 * required IANA name with no default, so the one place a timezone decision is made is explicit
 * and visible at the call site, never implicit in `new Date().getTimezoneOffset()`.
 */
export function calendarDateIn(instant: Date | string, timeZone: string): JalaliDate {
  const date = typeof instant === "string" ? new Date(instant) : instant;
  // Locale and calendar must both be explicit — an unspecified locale can resolve to the
  // runtime's default (e.g. "fa-IR"), which would silently return Persian-calendar parts
  // instead of the Gregorian ones this function localises before handing off to toJalali.
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    calendar: "gregory",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(date);
  const get = (type: string): number => {
    const part = parts.find((p) => p.type === type);
    if (!part) {
      throw new Error(
        `appkit.dates.calendarDateIn: could not resolve "${type}" for timeZone ${timeZone}`,
      );
    }
    return Number(part.value);
  };
  return toJalali({ year: get("year"), month: get("month"), day: get("day") });
}
