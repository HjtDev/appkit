/**
 * Shared string helpers whose semantics must match the backend (`appkit.text`,
 * docs/CONTRACT.md §18 <-> §2.12).
 */

// Persian and Arabic-Indic digit blocks, both normalised to ASCII by `toEnglishDigits` — a
// Persian-locale keyboard can emit either set depending on the input method, so both are
// accepted, mirroring `backend/src/appkit/text.py`.
const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const ASCII_DIGITS = "0123456789";

const TO_ENGLISH_MAP: ReadonlyMap<string, string> = new Map(
  [...(PERSIAN_DIGITS + ARABIC_INDIC_DIGITS)].map((ch, i) => [ch, ASCII_DIGITS[i % 10]!]),
);
const TO_PERSIAN_MAP: ReadonlyMap<string, string> = new Map(
  [...ASCII_DIGITS].map((ch, i) => [ch, PERSIAN_DIGITS[i]!]),
);

/**
 * Truncates `value` to `length` characters (Unicode codepoints), suffix included in the count.
 *
 * `truncate("hello world", 8)` -> `"hello w…"` (8 characters total). Never raises: a
 * `length <= suffix.length` returns the suffix itself, clamped to `length` characters (a
 * negative `length` clamps to an empty string). Counts codepoints via `Array.from` — never bare
 * `.length`/`.slice()` indexing, which counts UTF-16 code units and can split a surrogate pair
 * mid-codepoint — matching the backend's `len()`-based count exactly
 * (`backend/src/appkit/text.py`).
 */
export function truncate(value: string, length: number, suffix = "…"): string {
  const suffixChars = Array.from(suffix);
  if (length <= suffixChars.length) {
    return suffixChars.slice(0, Math.max(length, 0)).join("");
  }
  const valueChars = Array.from(value);
  if (valueChars.length <= length) {
    return value;
  }
  return valueChars.slice(0, length - suffixChars.length).join("") + suffix;
}

/**
 * Normalises Persian and Arabic-Indic digits to ASCII. Never raises; characters outside both
 * digit sets pass through unchanged.
 */
export function toEnglishDigits(value: string): string {
  return Array.from(value)
    .map((ch) => TO_ENGLISH_MAP.get(ch) ?? ch)
    .join("");
}

/**
 * Converts ASCII digits to Persian digits. Never raises; non-ASCII-digit characters pass
 * through unchanged.
 */
export function toPersianDigits(value: string): string {
  return Array.from(value)
    .map((ch) => TO_PERSIAN_MAP.get(ch) ?? ch)
    .join("");
}
