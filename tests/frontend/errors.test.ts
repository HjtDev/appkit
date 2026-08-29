import { describe, expect, it } from "vitest";

import {
  ApiError,
  apiErrorFromEnvelope,
  isApiError,
  isApiErrorEnvelope,
  type ApiErrorCode,
} from "../../frontend/src/errors.js";

import errorCodes from "@fixtures/error-codes.json";

describe("ApiErrorCode", () => {
  it("matches error-codes.json exactly, in order — the shared-fixture rule (§19)", () => {
    const codes: ApiErrorCode[] = [
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
    ];
    expect(codes).toEqual(errorCodes);
  });

  it("accepts every code from the fixture as a valid envelope code", () => {
    for (const code of errorCodes as string[]) {
      const envelope = {
        error: { code, message: "x", details: {}, request_id: null },
      };
      expect(isApiErrorEnvelope(envelope)).toBe(true);
    }
  });
});

describe("isApiError", () => {
  it("is true for a real ApiError", () => {
    const err = new ApiError("boom", { status: 500, code: "server_error" });
    expect(isApiError(err)).toBe(true);
  });

  it("is false for a plain Error", () => {
    expect(isApiError(new Error("boom"))).toBe(false);
  });

  it("is false for a structurally-similar impostor (no brand)", () => {
    const impostor = Object.assign(new Error("boom"), {
      status: 500,
      code: "server_error",
      details: {},
      requestId: null,
      retryAfter: null,
    });
    expect(isApiError(impostor)).toBe(false);
  });

  it("is false for null/undefined/primitives", () => {
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError("ApiError")).toBe(false);
    expect(isApiError(42)).toBe(false);
  });

  it("survives a simulated second module copy — the brand is Symbol.for-keyed", () => {
    // A genuine "two copies of appkit" scenario would mean two separately-evaluated copies of
    // this module, each with its own `class ApiError`. We can't easily load a second copy in a
    // single test file, but we can prove the mechanism: the brand symbol is retrieved via
    // `Symbol.for`, which is guaranteed to return the identical symbol for the identical key
    // across separate module registries (unlike a module-local `Symbol()`, which would not).
    expect(Symbol.for("appkit.ApiError")).toBe(Symbol.for("appkit.ApiError"));
  });

  it("does not leak the brand into JSON.stringify/Object.keys output", () => {
    const err = new ApiError("boom", { status: 500, code: "server_error" });
    expect(Object.keys(err)).not.toContain(Symbol.for("appkit.ApiError").toString());
    const json = JSON.parse(JSON.stringify({ status: err.status, code: err.code }));
    expect(json).toEqual({ status: 500, code: "server_error" });
  });
});

describe("isApiErrorEnvelope", () => {
  it("validates a well-formed envelope", () => {
    expect(
      isApiErrorEnvelope({
        error: { code: "validation_error", message: "bad", details: {}, request_id: "abc" },
      }),
    ).toBe(true);
  });

  it("accepts a null request_id", () => {
    expect(
      isApiErrorEnvelope({
        error: { code: "not_found", message: "gone", details: {}, request_id: null },
      }),
    ).toBe(true);
  });

  it("accepts a well-shaped envelope with an unrecognised code — forward-compatibility (§1)", () => {
    // A future minor version may carve a new, more specific code out of "error" — an older
    // minor's isApiErrorEnvelope must still recognise the envelope SHAPE so message/details/
    // request_id survive; only apiErrorFromEnvelope decides what to do with the unknown code.
    expect(
      isApiErrorEnvelope({
        error: { code: "rate_limit_exceeded", message: "x", details: {}, request_id: null },
      }),
    ).toBe(true);
  });

  it("still rejects a non-string or empty-string code", () => {
    expect(
      isApiErrorEnvelope({ error: { code: 42, message: "x", details: {}, request_id: null } }),
    ).toBe(false);
    expect(
      isApiErrorEnvelope({ error: { code: "", message: "x", details: {}, request_id: null } }),
    ).toBe(false);
  });

  it("rejects a missing details object", () => {
    expect(
      isApiErrorEnvelope({
        error: { code: "server_error", message: "x", request_id: null },
      }),
    ).toBe(false);
  });

  it("rejects a non-string message", () => {
    expect(
      isApiErrorEnvelope({
        error: { code: "server_error", message: 42, details: {}, request_id: null },
      }),
    ).toBe(false);
  });

  it("rejects a non-string, non-null request_id", () => {
    expect(
      isApiErrorEnvelope({
        error: { code: "server_error", message: "x", details: {}, request_id: 42 },
      }),
    ).toBe(false);
  });

  it("rejects null, arrays, and non-object bodies", () => {
    expect(isApiErrorEnvelope(null)).toBe(false);
    expect(isApiErrorEnvelope(undefined)).toBe(false);
    expect(isApiErrorEnvelope("string")).toBe(false);
    expect(isApiErrorEnvelope(42)).toBe(false);
    expect(isApiErrorEnvelope([])).toBe(false);
  });

  it("rejects valid JSON that isn't envelope-shaped", () => {
    expect(isApiErrorEnvelope({ status: "error", data: {} })).toBe(false);
  });

  it("rejects an envelope whose error field isn't an object", () => {
    expect(isApiErrorEnvelope({ error: "server_error" })).toBe(false);
  });
});

describe("apiErrorFromEnvelope — never throws, the §17 adversarial-input list", () => {
  const base = { status: 500, requestId: null, retryAfter: null };

  it("parses a well-formed envelope", () => {
    const err = apiErrorFromEnvelope({
      ...base,
      status: 400,
      body: {
        error: {
          code: "validation_error",
          message: "Bad input.",
          details: { field: "x" },
          request_id: "r-1",
        },
      },
    });
    expect(err.code).toBe("validation_error");
    expect(err.message).toBe("Bad input.");
    expect(err.details).toEqual({ field: "x" });
    expect(err.requestId).toBe("r-1");
    expect(err.status).toBe(400);
  });

  it("prefers the envelope's request_id over the header-derived one", () => {
    const err = apiErrorFromEnvelope({
      status: 400,
      requestId: "header-id",
      retryAfter: null,
      body: {
        error: { code: "server_error", message: "x", details: {}, request_id: "envelope-id" },
      },
    });
    expect(err.requestId).toBe("envelope-id");
  });

  it("falls back to the header-derived request_id when the envelope's is null", () => {
    const err = apiErrorFromEnvelope({
      status: 500,
      requestId: "header-id",
      retryAfter: null,
      body: { error: { code: "server_error", message: "x", details: {}, request_id: null } },
    });
    expect(err.requestId).toBe("header-id");
  });

  it("handles an HTML body (an nginx error page)", () => {
    const err = apiErrorFromEnvelope({
      ...base,
      body: "<html><body>502 Bad Gateway</body></html>",
    });
    expect(err.code).toBe("unknown_error");
    expect(err.body).toBe("<html><body>502 Bad Gateway</body></html>");
  });

  it("handles an empty body", () => {
    const err = apiErrorFromEnvelope({ ...base, body: "" });
    expect(err.code).toBe("unknown_error");
  });

  it("handles null", () => {
    const err = apiErrorFromEnvelope({ ...base, body: null });
    expect(err.code).toBe("unknown_error");
    expect(err.body).toBe(null);
  });

  it("handles valid JSON that isn't an envelope shape", () => {
    const err = apiErrorFromEnvelope({ ...base, body: { hello: "world" } });
    expect(err.code).toBe("unknown_error");
    expect(err.body).toEqual({ hello: "world" });
  });

  it('degrades an unrecognised code to "error" while preserving message/details/request_id', () => {
    // The forward-compatibility case (§1): a host on an older minor sees a code the backend
    // added later. It must not lose the message/details/request_id the way falling through to
    // "unknown_error" would — only the code itself degrades, to the documented catch-all.
    const err = apiErrorFromEnvelope({
      status: 429,
      requestId: null,
      retryAfter: "30",
      body: {
        error: {
          code: "rate_limit_exceeded",
          message: "Slow down.",
          details: { retry_in: 30 },
          request_id: "r-1",
        },
      },
    });
    expect(err.code).toBe("error");
    expect(err.message).toBe("Slow down.");
    expect(err.details).toEqual({ retry_in: 30 });
    expect(err.requestId).toBe("r-1");
    expect(err.retryAfter).toBe("30");
    expect(err.unrecognizedCode).toBe("rate_limit_exceeded");
  });

  it("leaves unrecognizedCode null for every known code", () => {
    const err = apiErrorFromEnvelope({
      ...base,
      body: { error: { code: "server_error", message: "x", details: {}, request_id: null } },
    });
    expect(err.code).toBe("server_error");
    expect(err.unrecognizedCode).toBeNull();
  });

  it("handles an envelope missing details", () => {
    const err = apiErrorFromEnvelope({
      ...base,
      body: { error: { code: "server_error", message: "x", request_id: null } },
    });
    expect(err.code).toBe("unknown_error");
  });

  it("handles a 204 (empty body, success status) without crashing", () => {
    const err = apiErrorFromEnvelope({
      status: 204,
      requestId: null,
      retryAfter: null,
      body: undefined,
    });
    expect(err.code).toBe("unknown_error");
    expect(err.status).toBe(204);
  });

  it("never throws for any of the above", () => {
    const inputs: unknown[] = ["<html/>", "", null, undefined, { x: 1 }, [], 42, true];
    for (const body of inputs) {
      expect(() => apiErrorFromEnvelope({ ...base, body })).not.toThrow();
    }
  });
});
