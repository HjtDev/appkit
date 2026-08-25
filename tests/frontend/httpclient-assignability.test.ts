import { describe, expect, it } from "vitest";

import type { HttpClient } from "../../frontend/src/client.js";

/**
 * Type-level test: proves the base-scaffold's `ApiClient`
 * (`../base-scaffold/frontend/lib/api-client.ts:185-215`) is structurally assignable to
 * `HttpClient` with zero scaffold changes — the whole design rests on structural typing
 * (docs/CONTRACT.md §14). A faithful COPY of the scaffold's method signatures, not an import —
 * appkit must never reference a sibling repo at runtime or build time.
 *
 * If a future scaffold change (or a future appkit `HttpClient` change) breaks this
 * assignability, `tsc --noEmit` fails right here, not three repos away when the first app tries
 * to use it.
 */
class ScaffoldApiClientShape {
  async request<T>(_path: string, _init: RequestInit = {}): Promise<T> {
    throw new Error("not implemented — type-level fixture only");
  }

  get<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...init, method: "GET" });
  }

  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...init,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...init,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...init,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  delete<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...init, method: "DELETE" });
  }
}

// The assignability check itself — no `implements HttpClient` on the class above (deliberately,
// since the scaffold's real file has none either): this line is what fails `tsc --noEmit` if
// the shapes ever drift apart.
const scaffoldClientSatisfiesHttpClient: HttpClient = new ScaffoldApiClientShape();

describe("HttpClient <- base-scaffold's ApiClient (structural, type-level)", () => {
  it("compiles, proving structural assignability — see the type annotation above", () => {
    expect(typeof scaffoldClientSatisfiesHttpClient.get).toBe("function");
    expect(typeof scaffoldClientSatisfiesHttpClient.post).toBe("function");
    expect(typeof scaffoldClientSatisfiesHttpClient.put).toBe("function");
    expect(typeof scaffoldClientSatisfiesHttpClient.patch).toBe("function");
    expect(typeof scaffoldClientSatisfiesHttpClient.delete).toBe("function");
  });
});
