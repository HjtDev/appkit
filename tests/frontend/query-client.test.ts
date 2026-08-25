import { describe, expect, it } from "vitest";

import { makeQueryClient } from "../../frontend/src/query-client.js";
import { ApiError } from "../../frontend/src/errors.js";

function getRetryFn() {
  const qc = makeQueryClient();
  const retry = qc.getDefaultOptions().queries?.retry;
  if (typeof retry !== "function") {
    throw new Error("expected retry to be a function");
  }
  return retry;
}

describe("makeQueryClient", () => {
  it("is a factory — returns a distinct instance per call", () => {
    const a = makeQueryClient();
    const b = makeQueryClient();
    expect(a).not.toBe(b);
  });

  it("sets staleTime to 60_000 and disables refetchOnWindowFocus", () => {
    const qc = makeQueryClient();
    const queries = qc.getDefaultOptions().queries;
    expect(queries?.staleTime).toBe(60_000);
    expect(queries?.refetchOnWindowFocus).toBe(false);
  });

  it("never retries a 4xx ApiError", () => {
    const retry = getRetryFn();
    const err = new ApiError("bad", { status: 400, code: "validation_error" });
    expect(retry(0, err)).toBe(false);
    expect(retry(1, err)).toBe(false);
  });

  it("retries a 5xx ApiError up to twice", () => {
    const retry = getRetryFn();
    const err = new ApiError("boom", { status: 500, code: "server_error" });
    expect(retry(0, err)).toBe(true);
    expect(retry(1, err)).toBe(true);
    expect(retry(2, err)).toBe(false);
  });

  it("retries a plain network error (not an ApiError) up to twice", () => {
    const retry = getRetryFn();
    const err = new TypeError("Failed to fetch");
    expect(retry(0, err)).toBe(true);
    expect(retry(1, err)).toBe(true);
    expect(retry(2, err)).toBe(false);
  });

  it("checks isApiError (brand), not instanceof — correct even for a simulated second copy", () => {
    // Simulates "two copies of appkit in one tree": an object that is NOT an instance of this
    // module's ApiError class, but carries the correct Symbol.for-keyed brand a second,
    // separately-bundled copy of appkit would also produce. `instanceof` would treat this as an
    // unrecognised error and retry a 400 needlessly — the brand check must not.
    const retry = getRetryFn();
    const secondCopyError = Object.defineProperty(
      Object.assign(new Error("bad"), { status: 400, code: "validation_error", details: {} }),
      Symbol.for("appkit.ApiError"),
      { value: true, enumerable: false },
    );
    expect(secondCopyError instanceof ApiError).toBe(false);
    expect(retry(0, secondCopyError)).toBe(false);
  });
});
