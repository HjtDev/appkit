/**
 * appkit's frontend entrypoint (docs/CONTRACT.md §21).
 *
 * The single entrypoint — per the "one entrypoint" rule, everything a host or an installed app
 * can use is exported from here; nothing under an internal path is ever imported directly. The
 * `exports` map in package.json makes this enforced by Node's resolver, not merely convention.
 */

export type { HttpClient, HeaderSource } from "./client.js";

export { ApiClientProvider, useApiClient } from "./provider.js";
export type { ApiClientProviderProps } from "./provider.js";

export { ApiError, isApiError, isApiErrorEnvelope, apiErrorFromEnvelope } from "./errors.js";
export type { ApiErrorCode, ClientErrorCode, ApiErrorEnvelope } from "./errors.js";

export { makeQueryClient } from "./query-client.js";

export { truncate, toEnglishDigits, toPersianDigits } from "./text.js";
export { parseAmount, formatAmount } from "./money.js";
export { toJalali, fromJalali, formatJalali, parseJalali, calendarDateIn } from "./dates.js";
export type { JalaliDate } from "./dates.js";
export { mediaUrl } from "./media.js";
