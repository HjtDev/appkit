/**
 * `ApiError`, the envelope types, and the pure parsing helpers (docs/CONTRACT.md §17).
 *
 * Mirrors the backend envelope (`appkit.exceptions`, `docs/CONTRACT.md` §1) character-for-
 * character, including the ten-code union — pinned against `tests/fixtures/error-codes.json`,
 * the same file `appkit.exceptions.ERROR_CODES` is pinned against, rather than the two halves
 * being hand-verified against each other (docs/CONTRACT.md §19).
 *
 * Purity is a rule, not a property of today's implementation: nothing here imports `fetch`,
 * `Response`, `baseUrl`, or `process.env`. `isApiErrorEnvelope`/`apiErrorFromEnvelope` operate
 * on already-fetched data — a status code, a parsed-or-unparsed body, header values the caller
 * already read — never on a live request (docs/CONTRACT.md §13).
 */

/**
 * The ten codes from the backend contract's §1, verbatim and in the same order. Exhaustive — a
 * `switch (error.code)` over this union type-checks against the real, closed set. `"error"` is
 * the documented catch-all, not an omission (docs/CONTRACT.md §1's four rules).
 */
export type ApiErrorCode =
  | "validation_error"
  | "parse_error"
  | "not_authenticated"
  | "authentication_failed"
  | "permission_denied"
  | "not_found"
  | "method_not_allowed"
  | "throttled"
  | "server_error"
  | "error";

/**
 * This client's own code for a response that isn't the envelope at all (an nginx error page, a
 * truncated body, a non-JSON 500) — kept OUT of `ApiErrorCode` so that union stays a true,
 * unmodified mirror of the ten codes the backend actually emits.
 */
export type ClientErrorCode = "unknown_error";

/** The wire shape exactly — `request_id`, snake_case, matches the backend's JSON key. */
export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode;
    message: string;
    details: Record<string, unknown>;
    request_id: string | null;
  };
}

const API_ERROR_BRAND = Symbol.for("appkit.ApiError");

export interface ApiErrorOptions {
  status: number;
  code: ApiErrorCode | ClientErrorCode;
  details?: Record<string, unknown>;
  requestId?: string | null;
  retryAfter?: string | null;
  /** The raw, un-parsed response body — present only on the "unknown_error" path. */
  body?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | ClientErrorCode;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;
  readonly retryAfter: string | null;
  readonly body?: unknown;

  constructor(message: string, options: ApiErrorOptions) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? {};
    this.requestId = options.requestId ?? null;
    this.retryAfter = options.retryAfter ?? null;
    this.body = options.body;
    // Non-enumerable brand, keyed off `Symbol.for` (which returns the identical symbol across
    // separately-bundled copies of this module) so `isApiError` survives a duplicate-copy
    // install the way `instanceof` would not. Set via `defineProperty` rather than a computed
    // class field so it never appears in `Object.keys`/`JSON.stringify` output alongside the
    // real, public fields above.
    Object.defineProperty(this, API_ERROR_BRAND, { value: true, enumerable: false });
  }
}

/**
 * Brand check, not `instanceof` — still correct if two copies of appkit ever land in one tree
 * (a host whose lockfile resolved two `appkit` installs), since `instanceof` across two module
 * instances of the same class fails even for a "real" `ApiError`. Keyed off `Symbol.for`, which
 * returns the identical symbol for the identical key across separate module instances.
 */
export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as Record<PropertyKey, unknown>)[API_ERROR_BRAND] === true
  );
}

const VALID_CODES: ReadonlySet<string> = new Set<ApiErrorCode>([
  "validation_error",
  "parse_error",
  "not_authenticated",
  "authentication_failed",
  "permission_denied",
  "not_found",
  "method_not_allowed",
  "throttled",
  "server_error",
  "error",
]);

/**
 * Pure. Validates, does not assume: `data` must be an object with an `error` object whose
 * `code` is one of the ten `ApiErrorCode` values, `message` is a string, `details` is an
 * object, and `request_id` is a string or null. An unrecognised `code` FAILS the guard, rather
 * than passing the envelope through with a code outside the closed set — this is what keeps
 * every downstream `switch (error.code)` exhaustive and type-safe.
 */
export function isApiErrorEnvelope(data: unknown): data is ApiErrorEnvelope {
  if (typeof data !== "object" || data === null || !("error" in data)) return false;

  const error = (data as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return false;

  const candidate = error as Record<string, unknown>;
  if (typeof candidate.code !== "string" || !VALID_CODES.has(candidate.code)) return false;
  if (typeof candidate.message !== "string") return false;
  if (typeof candidate.details !== "object" || candidate.details === null) return false;
  if (candidate.request_id !== null && typeof candidate.request_id !== "string") return false;

  return true;
}

export interface ApiErrorFromEnvelopeInput {
  status: number;
  body: unknown;
  requestId: string | null;
  retryAfter: string | null;
}

/**
 * Pure. Never throws while constructing an error — this is the single most important
 * behaviour in this module. A non-envelope `body` (HTML, empty, null, valid-JSON-non-envelope,
 * an envelope with an unrecognised code) produces a well-formed `ApiError` with code
 * `"unknown_error"` and `body` set to the raw input, rather than the parser itself failing on
 * the failure path it exists to describe.
 *
 * Header-derived values (`requestId`, `retryAfter`) are read by the caller — the host's
 * concrete client, which has the live `Response` — and passed in; this function never touches
 * `Response` itself.
 */
export function apiErrorFromEnvelope(input: ApiErrorFromEnvelopeInput): ApiError {
  const { status, body, requestId, retryAfter } = input;

  if (isApiErrorEnvelope(body)) {
    const { error } = body;
    return new ApiError(error.message, {
      status,
      code: error.code,
      details: error.details,
      requestId: error.request_id ?? requestId,
      retryAfter,
    });
  }

  return new ApiError(`Request failed with status ${status}.`, {
    status,
    code: "unknown_error",
    requestId,
    retryAfter,
    body,
  });
}
