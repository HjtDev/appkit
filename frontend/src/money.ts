/**
 * Integer money parsing/formatting with fixed ASCII grouping — mirrors the backend
 * (`appkit.money`, docs/CONTRACT.md §18 <-> §2.14).
 */

import { toEnglishDigits } from "./text.js";

const THOUSANDS_SEPARATORS = [",", "٬"];

/**
 * Parses a digit string or `number` into an integer amount.
 *
 * Accepts Persian/Arabic-Indic digits (normalised via `toEnglishDigits` first) and strips
 * thousands separators (`,`/`٬`) before parsing.
 *
 * The one place JS's lack of a separate int type forces a documented divergence in *shape*,
 * not intent, from the backend's `parse_amount`: **rejects a non-integer `number` outright**,
 * throwing `TypeError` — mirroring the backend's float rejection, since a currency amount
 * arriving as `12000.5` is the identical defect-in-the-caller case. **Additionally throws
 * `RangeError`** for a value exceeding `Number.MAX_SAFE_INTEGER` — the backend's arbitrary-
 * precision `int` has no such ceiling; a caller handling an amount near or beyond 2^53 must
 * keep it as a string end-to-end and never round-trip it through `parseAmount`/`formatAmount`.
 * Throws a plain `Error` for a string that isn't a valid integer after normalisation.
 */
export function parseAmount(value: string | number): number {
  if (typeof value === "number") {
    if (!Number.isInteger(value)) {
      throw new TypeError(
        `parseAmount() does not accept a non-integer number (${value}); pass an integer or a digit string.`,
      );
    }
    if (Math.abs(value) > Number.MAX_SAFE_INTEGER) {
      throw new RangeError(
        `parseAmount() received ${value}, which exceeds Number.MAX_SAFE_INTEGER — keep this amount as a string.`,
      );
    }
    return value;
  }

  let normalized = toEnglishDigits(value);
  for (const sep of THOUSANDS_SEPARATORS) {
    normalized = normalized.split(sep).join("");
  }
  normalized = normalized.trim();

  if (!normalized || !/^[+-]?\d+$/.test(normalized)) {
    throw new Error(`parseAmount() received a non-integer string: ${JSON.stringify(value)}`);
  }

  const parsed = Number(normalized);
  if (Math.abs(parsed) > Number.MAX_SAFE_INTEGER) {
    throw new RangeError(
      `parseAmount() received ${JSON.stringify(value)}, which exceeds Number.MAX_SAFE_INTEGER — keep this amount as a string.`,
    );
  }
  return parsed;
}

/**
 * Thousands-grouped string using a fixed ASCII `,` separator, regardless of locale —
 * `Intl.NumberFormat` is deliberately not used, since its grouping character is locale-
 * dependent and would make the same call render differently across two browsers.
 *
 * `1000000` -> `"1,000,000"`, or `"1,000,000 IRT"` with `currency: "IRT"`. Never raises for any
 * finite integer input, including `0` and negative values (`-500` -> `"-500"`). Emits Latin
 * digits only — `toPersianDigits` is a caller's separate, explicit choice on the result.
 */
export function formatAmount(value: number, currency = ""): string {
  const negative = value < 0;
  const digits = Math.trunc(Math.abs(value)).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const formatted = negative ? `-${grouped}` : grouped;
  return currency ? `${formatted} ${currency}` : formatted;
}
