import { describe, expect, it } from "vitest";

import * as appkit from "../../frontend/src/index.js";

// docs/CONTRACT.md §21's complete export list — the value exports only (type-only exports
// leave no runtime binding to enumerate). Kept as a literal list, not derived from the module
// itself, so a future session can't silently widen or narrow the public surface without this
// test failing.
const EXPECTED_VALUE_EXPORTS = [
  "ApiClientProvider",
  "useApiClient",
  "ApiError",
  "isApiError",
  "isApiErrorEnvelope",
  "apiErrorFromEnvelope",
  "makeQueryClient",
  "truncate",
  "toEnglishDigits",
  "toPersianDigits",
  "parseAmount",
  "formatAmount",
  "toJalali",
  "fromJalali",
  "formatJalali",
  "parseJalali",
  "calendarDateIn",
  "mediaUrl",
].sort();

describe("src/index.ts — the complete export list (§21)", () => {
  it("exports exactly the names §21 specifies — no more, no less", () => {
    expect(Object.keys(appkit).sort()).toEqual(EXPECTED_VALUE_EXPORTS);
  });

  it("does not export a context object, a concrete client, or a QueryClient singleton", () => {
    expect(Object.keys(appkit)).not.toContain("ApiClientContext");
    expect(Object.keys(appkit)).not.toContain("apiClient");
    expect(Object.keys(appkit)).not.toContain("getApiBaseUrl");
    expect(Object.keys(appkit)).not.toContain("queryClient");
  });
});
