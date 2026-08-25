import { act } from "react";
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, useApiClient } from "../../frontend/src/provider.js";
import type { HeaderSource, HttpClient } from "../../frontend/src/client.js";

function makeRecordingClient(): HttpClient & { lastInit: RequestInit | undefined } {
  // `HttpClient`'s methods are generic in T; a `vi.fn` mock always infers a single concrete
  // return type from its implementation, so it can never satisfy `get<T>(...): Promise<T>`
  // exactly. The cast is safe here — every mocked method ignores T and resolves an opaque
  // stub value, which is all these tests inspect (the recorded `init`, not the resolved value).
  const client = {
    lastInit: undefined as RequestInit | undefined,
    get: vi.fn(async (_path: string, init?: RequestInit) => {
      client.lastInit = init;
      return "ok";
    }),
    post: vi.fn(async () => "ok"),
    put: vi.fn(async () => "ok"),
    patch: vi.fn(async () => "ok"),
    delete: vi.fn(async () => "ok"),
  };
  return client as unknown as HttpClient & { lastInit: RequestInit | undefined };
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  const headers = new Headers(init?.headers);
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

function renderWithSources(client: HttpClient, headerSources: ReadonlyArray<HeaderSource>) {
  return renderHook(() => useApiClient("app", "/api"), {
    wrapper: ({ children }) => (
      <ApiClientProvider client={client} headerSources={headerSources}>
        {children}
      </ApiClientProvider>
    ),
  });
}

describe("headerSources — merge semantics (§16)", () => {
  it("two sources with overlapping keys: later wins", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      () => ({ "X-Value": "first" }),
      () => ({ "X-Value": "second" }),
    ];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x");
    });

    expect(headersOf(client.lastInit)["x-value"]).toBe("second");
  });

  it("case-mismatched keys still collapse to one header — the later value wins", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      () => ({ Authorization: "first" }),
      () => ({ authorization: "second" }),
    ];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x");
    });

    const headers = headersOf(client.lastInit);
    expect(headers["authorization"]).toBe("second");
    expect(Object.keys(headers).filter((k) => k.toLowerCase() === "authorization")).toHaveLength(1);
  });

  it("supports an async source", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      async () => {
        await new Promise((resolve) => setTimeout(resolve, 1));
        return { "X-Async": "value" };
      },
    ];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x");
    });

    expect(headersOf(client.lastInit)["x-async"]).toBe("value");
  });

  it("awaits sources in order, not racing — a later source can observe an earlier one's side effect", async () => {
    const client = makeRecordingClient();
    const order: string[] = [];
    const sources: HeaderSource[] = [
      async () => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        order.push("first");
        return { "X-First": "1" };
      },
      async () => {
        order.push("second");
        return { "X-Second": "2" };
      },
    ];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x");
    });

    expect(order).toEqual(["first", "second"]);
  });

  it("a throwing source fails the whole request, naming which source failed by index", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      () => ({ "X-Ok": "1" }),
      () => {
        throw new Error("token store unavailable");
      },
    ];
    const { result } = renderWithSources(client, sources);

    await expect(result.current.client.get("/x")).rejects.toThrow(
      "Header source #1 threw while building request headers: token store unavailable",
    );
    expect(client.get).not.toHaveBeenCalled();
  });

  it("a source throwing a non-Error value still names the source, stringifying the thrown value", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      () => {
        // Deliberately not an Error instance — proves the non-Error fallback path
        // (`String(err)`) rather than the `Error.message` path.
        throw "token store offline";
      },
    ];
    const { result } = renderWithSources(client, sources);

    await expect(result.current.client.get("/x")).rejects.toThrow(
      "Header source #0 threw while building request headers: token store offline",
    );
  });

  it("a rejecting async source fails the whole request the same way", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [async () => Promise.reject(new Error("refresh failed"))];
    const { result } = renderWithSources(client, sources);

    await expect(result.current.client.get("/x")).rejects.toThrow(
      "Header source #0 threw while building request headers: refresh failed",
    );
    expect(client.get).not.toHaveBeenCalled();
  });

  it("the call's own init.headers overrides both header sources", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [() => ({ "X-Value": "from-source" })];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x", { headers: { "X-Value": "from-call" } });
    });

    expect(headersOf(client.lastInit)["x-value"]).toBe("from-call");
  });

  it("normalises all three HeadersInit forms (object, array pairs, Headers instance)", async () => {
    const client = makeRecordingClient();
    const sources: HeaderSource[] = [
      () => ({ "X-Object": "1" }),
      () => [["X-Array", "2"]],
      () => new Headers({ "X-Headers-Instance": "3" }),
    ];
    const { result } = renderWithSources(client, sources);

    await act(async () => {
      await result.current.client.get("/x");
    });

    const headers = headersOf(client.lastInit);
    expect(headers["x-object"]).toBe("1");
    expect(headers["x-array"]).toBe("2");
    expect(headers["x-headers-instance"]).toBe("3");
  });

  it("works with no headerSources at all", async () => {
    const client = makeRecordingClient();
    const { result } = renderWithSources(client, []);

    await act(async () => {
      await result.current.client.get("/x");
    });

    expect(client.get).toHaveBeenCalled();
  });
});
