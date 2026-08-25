import { act } from "react";
import { renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, useApiClient } from "../../frontend/src/provider.js";
import type { HttpClient } from "../../frontend/src/client.js";
import { server } from "./setup.js";

/**
 * §16's mandated wire-level test: a merged header must actually arrive on the wire request,
 * not just be present in the object the merge function returns. This is a minimal, test-only
 * `fetch`-based `HttpClient` — appkit itself ships no fetcher (docs/CONTRACT.md §13); this
 * exists purely to give MSW something real to intercept.
 */
function makeFetchClient(baseUrl: string): HttpClient {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, init);
    return (await response.json()) as T;
  }
  return {
    get: (path, init) => request(path, init),
    post: (path, _body, init) => request(path, init),
    put: (path, _body, init) => request(path, init),
    patch: (path, _body, init) => request(path, init),
    delete: (path, init) => request(path, init),
  };
}

describe("headerSources — the merged header actually arrives on the wire (§16)", () => {
  it("MSW observes the merged, case-collapsed header on a real request", async () => {
    let observedAuth: string | null = null;
    let observedTenant: string | null = null;

    server.use(
      http.get("https://api.test/x", ({ request }) => {
        observedAuth = request.headers.get("authorization");
        observedTenant = request.headers.get("x-tenant-id");
        return HttpResponse.json({ ok: true });
      }),
    );

    const client = makeFetchClient("https://api.test");
    const headerSources = [
      () => ({ Authorization: "Bearer token-1" }),
      () => ({ "X-Tenant-ID": "tenant-42" }),
    ];

    const { result } = renderHook(() => useApiClient("app", "/api"), {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client} headerSources={headerSources}>
          {children}
        </ApiClientProvider>
      ),
    });

    await act(async () => {
      await result.current.client.get("/x");
    });

    expect(observedAuth).toBe("Bearer token-1");
    expect(observedTenant).toBe("tenant-42");
  });

  it("a later source's value wins on the wire when two sources set the same header", async () => {
    let observed: string | null = null;
    server.use(
      http.get("https://api.test/y", ({ request }) => {
        observed = request.headers.get("authorization");
        return HttpResponse.json({ ok: true });
      }),
    );

    const client = makeFetchClient("https://api.test");
    const headerSources = [
      () => ({ Authorization: "Bearer stale" }),
      () => ({ authorization: "Bearer fresh" }),
    ];

    const { result } = renderHook(() => useApiClient("app", "/api"), {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client} headerSources={headerSources}>
          {children}
        </ApiClientProvider>
      ),
    });

    await act(async () => {
      await result.current.client.get("/y");
    });

    expect(observed).toBe("Bearer fresh");
  });
});
