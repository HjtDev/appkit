import { act } from "react";
import { renderHook, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, useApiClient } from "../../frontend/src/provider.js";
import type { HttpClient } from "../../frontend/src/client.js";

function makeStubClient(): HttpClient {
  return {
    get: vi.fn().mockResolvedValue("get-result"),
    post: vi.fn().mockResolvedValue("post-result"),
    put: vi.fn().mockResolvedValue("put-result"),
    patch: vi.fn().mockResolvedValue("patch-result"),
    delete: vi.fn().mockResolvedValue("delete-result"),
  };
}

describe("useApiClient — not mounted", () => {
  it("throws a clear error naming the file to edit", () => {
    const { result } = renderHook(() => {
      try {
        return useApiClient("notifications", "/api/v1/notifications");
      } catch (err) {
        return err;
      }
    });
    expect(result.current).toBeInstanceOf(Error);
    const message = (result.current as Error).message;
    expect(message).toContain('useApiClient("notifications")');
    expect(message).toContain("outside an <ApiClientProvider>");
    expect(message).toContain("frontend/app/providers.tsx");
  });
});

describe("useApiClient — mounted", () => {
  it("returns the injected client and the caller's default basePath when unmapped", () => {
    const client = makeStubClient();
    const { result } = renderHook(() => useApiClient("notifications", "/api/v1/notifications"), {
      wrapper: ({ children }) => <ApiClientProvider client={client}>{children}</ApiClientProvider>,
    });
    expect(result.current.basePath).toBe("/api/v1/notifications");
    expect(result.current.client).toBeDefined();
  });

  it("honours a basePaths override for the matching key", () => {
    const client = makeStubClient();
    const { result } = renderHook(() => useApiClient("notifications", "/default"), {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client} basePaths={{ notifications: "/custom/path" }}>
          {children}
        </ApiClientProvider>
      ),
    });
    expect(result.current.basePath).toBe("/custom/path");
  });

  it("falls back to the caller's default for a different app's key, never '' or '/'", () => {
    const client = makeStubClient();
    const { result } = renderHook(() => useApiClient("notifications", "/default"), {
      wrapper: ({ children }) => (
        <ApiClientProvider client={client} basePaths={{ other_app: "/other" }}>
          {children}
        </ApiClientProvider>
      ),
    });
    expect(result.current.basePath).toBe("/default");
    expect(result.current.basePath).not.toBe("");
    expect(result.current.basePath).not.toBe("/");
  });

  it("strips a trailing slash from the resolved basePath", () => {
    const client = makeStubClient();
    const { result } = renderHook(() => useApiClient("notifications", "/default/"), {
      wrapper: ({ children }) => <ApiClientProvider client={client}>{children}</ApiClientProvider>,
    });
    expect(result.current.basePath).toBe("/default");
  });

  it("throws for an empty defaultBasePath — no host-wide-safe default", () => {
    const client = makeStubClient();
    const { result } = renderHook(
      () => {
        try {
          return useApiClient("notifications", "");
        } catch (err) {
          return err;
        }
      },
      {
        wrapper: ({ children }) => (
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        ),
      },
    );
    expect(result.current).toBeInstanceOf(Error);
  });
});

describe("useApiClient — memoisation contract (§15)", () => {
  it("returns a referentially-unchanged manager-facing value across re-renders with a stable headerSources ref", () => {
    const client = makeStubClient();
    const headerSources = [() => ({ "X-Test": "1" })];

    function Wrapper({ children }: { children: React.ReactNode }) {
      return (
        <ApiClientProvider client={client} headerSources={headerSources}>
          {children}
        </ApiClientProvider>
      );
    }

    const { result, rerender } = renderHook(() => useApiClient("notifications", "/default"), {
      wrapper: Wrapper,
    });
    const first = result.current;
    rerender();
    const second = result.current;
    expect(second.client).toBe(first.client);
  });

  it("changes the client's identity across re-renders when headerSources is an inline array literal — the documented footgun", () => {
    const client = makeStubClient();

    function Wrapper({ children }: { children: React.ReactNode }) {
      // Deliberately inline — this is the footgun under test (§15): a new array identity on
      // every render.
      return (
        <ApiClientProvider client={client} headerSources={[() => ({ "X-Test": "1" })]}>
          {children}
        </ApiClientProvider>
      );
    }

    const { result, rerender } = renderHook(() => useApiClient("notifications", "/default"), {
      wrapper: Wrapper,
    });
    const first = result.current;
    rerender();
    const second = result.current;
    expect(second.client).not.toBe(first.client);
  });
});

describe("ApiClientProvider — decorated client delegates to the injected client", () => {
  it("calls through get/post/put/patch/delete", async () => {
    const client = makeStubClient();
    const { result } = renderHook(() => useApiClient("notifications", "/api"), {
      wrapper: ({ children }) => <ApiClientProvider client={client}>{children}</ApiClientProvider>,
    });

    await act(async () => {
      await result.current.client.get("/x");
      await result.current.client.post("/x", { a: 1 });
      await result.current.client.put("/x", { a: 1 });
      await result.current.client.patch("/x", { a: 1 });
      await result.current.client.delete("/x");
    });

    expect(client.get).toHaveBeenCalledWith("/x", expect.any(Object));
    expect(client.post).toHaveBeenCalledWith("/x", { a: 1 }, expect.any(Object));
    expect(client.put).toHaveBeenCalledWith("/x", { a: 1 }, expect.any(Object));
    expect(client.patch).toHaveBeenCalledWith("/x", { a: 1 }, expect.any(Object));
    expect(client.delete).toHaveBeenCalledWith("/x", expect.any(Object));
  });
});

describe("ApiClientProvider renders children", () => {
  it("mounts without crashing", () => {
    const client = makeStubClient();
    const { getByText } = render(
      <ApiClientProvider client={client}>
        <div>hello</div>
      </ApiClientProvider>,
    );
    expect(getByText("hello")).toBeInTheDocument();
  });
});
