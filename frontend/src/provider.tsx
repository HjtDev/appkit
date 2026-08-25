"use client";

/**
 * `ApiClientProvider` / `useApiClient` (docs/CONTRACT.md §15–§16).
 *
 * The one shared provider a host mounts, and the hook every installed app's own `api/config.ts`
 * binds against. appkit never constructs a client — the host injects one satisfying
 * `HttpClient` (docs/CONTRACT.md §13).
 *
 * The only stateful/client-side module in this package — every other export is a pure function
 * safe to import from a server component. `"use client"` lives here, not on `index.ts`, so a
 * server component importing `truncate` (say) from `"appkit"` never crosses the client boundary
 * for a function that doesn't need it.
 */

import { createContext, useContext, useMemo, type ReactElement, type ReactNode } from "react";

import type { HeaderSource, HttpClient } from "./client.js";

interface ApiClientContextValue {
  client: HttpClient;
  basePaths: Readonly<Record<string, string>>;
}

// Not exported — ApiClientProvider and useApiClient are the only two ways to reach this context
// (docs/CONTRACT.md §15, §21), so a host or a confused app can't hand-construct a second,
// incompatible provider against the same context.
const ApiClientContext = createContext<ApiClientContextValue | null>(null);

// A stable module-level reference for the "no headerSources passed" case — `props.headerSources
// ?? []` would otherwise create a fresh, differently-identitied array on every render even when
// the host never passes the prop at all, defeating the memoisation contract below for exactly
// the hosts that need it least.
const EMPTY_HEADER_SOURCES: ReadonlyArray<HeaderSource> = [];
const EMPTY_BASE_PATHS: Readonly<Record<string, string>> = {};

export interface ApiClientProviderProps {
  /** Any client satisfying HttpClient — normally the host's frontend/lib/api-client.ts
   *  apiClient, passed in as-is. */
  client: HttpClient;
  /** basePath per installed app, keyed by the app's own namespace. */
  basePaths?: Readonly<Record<string, string>>;
  /** Composable per-request header sources — see docs/CONTRACT.md §16. Must be a stable
   *  reference (module scope or useMemo); an inline array literal defeats the memoisation
   *  contract below, rebuilding every installed app's own manager on every render. */
  headerSources?: ReadonlyArray<HeaderSource>;
  children: ReactNode;
}

/**
 * Builds the merged header set for one request: `headerSources` run left-to-right, awaited in
 * order (never raced — a later source may rely on an earlier one's side effect), then the
 * call's own `init.headers` last. Header names compare case-insensitively (via the `Headers`
 * constructor every value is normalised through), so `authorization`/`Authorization` from two
 * sources collapse into one — the later value.
 *
 * A source that throws or rejects fails the WHOLE request: the rejection is wrapped naming
 * which source failed by index, and the underlying `client.get/post/...` is never invoked.
 */
async function buildHeaders(
  sources: ReadonlyArray<HeaderSource>,
  initHeaders?: HeadersInit,
): Promise<Headers> {
  const merged = new Headers();
  for (let i = 0; i < sources.length; i += 1) {
    const source = sources[i]!;
    let produced: HeadersInit;
    try {
      produced = await source();
    } catch (err) {
      const reason = err instanceof Error ? err.message : String(err);
      throw new Error(`Header source #${i} threw while building request headers: ${reason}`);
    }
    new Headers(produced).forEach((value, key) => merged.set(key, value));
  }
  if (initHeaders) {
    new Headers(initHeaders).forEach((value, key) => merged.set(key, value));
  }
  return merged;
}

/** Wraps `client` so every call first resolves `headerSources` (+ that call's own
 * `init.headers`) into the final header set before delegating. */
function decorateClient(
  client: HttpClient,
  headerSources: ReadonlyArray<HeaderSource>,
): HttpClient {
  return {
    get: async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const headers = await buildHeaders(headerSources, init?.headers);
      return client.get<T>(path, { ...init, headers });
    },
    post: async <T,>(path: string, body?: unknown, init?: RequestInit): Promise<T> => {
      const headers = await buildHeaders(headerSources, init?.headers);
      return client.post<T>(path, body, { ...init, headers });
    },
    put: async <T,>(path: string, body?: unknown, init?: RequestInit): Promise<T> => {
      const headers = await buildHeaders(headerSources, init?.headers);
      return client.put<T>(path, body, { ...init, headers });
    },
    patch: async <T,>(path: string, body?: unknown, init?: RequestInit): Promise<T> => {
      const headers = await buildHeaders(headerSources, init?.headers);
      return client.patch<T>(path, body, { ...init, headers });
    },
    delete: async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const headers = await buildHeaders(headerSources, init?.headers);
      return client.delete<T>(path, { ...init, headers });
    },
  };
}

/**
 * Dev-only duplicate-copy safeguard (docs/CONTRACT.md §21): if a second copy of appkit's
 * module registers the same `globalThis` symbol, this converts a silent, hard-to-diagnose
 * `null` (two React contexts resolving independently) into a named, actionable console warning
 * at the moment it happens. Stripped in production builds via the `process.env.NODE_ENV` guard
 * — a bundler that inlines `NODE_ENV` and dead-code-eliminates the `false` branch removes this
 * entirely, keeping `sideEffects: false` true in the terms that matter (nothing observable
 * survives into a production bundle).
 */
// Factored out of the module-level call below so a test can invoke it twice against an
// injected, throwaway registry — the real call always targets `globalThis`, and ES module
// caching means the module-top-level statement itself only ever runs once per process, so the
// "second copy" branch can't be exercised by re-importing this module in a test.
export function runDuplicateCopyGuard(
  registry: Record<symbol, boolean> = globalThis as unknown as Record<symbol, boolean>,
): void {
  if (typeof process === "undefined" || process.env?.NODE_ENV === "production") return;
  const marker = Symbol.for("appkit.duplicate-copy-guard");
  if (registry[marker]) {
    console.warn(
      "appkit: a second copy of appkit's module was just loaded into this tree. Two copies " +
        "means two separate React module instances, which means two separate React contexts — " +
        "useApiClient will silently behave as if no <ApiClientProvider> were mounted in half " +
        "the tree. Run `npm ls appkit` and dedupe to exactly one resolved copy (docs/CONTRACT.md §22).",
    );
  } else {
    registry[marker] = true;
  }
}

runDuplicateCopyGuard();

export function ApiClientProvider(props: ApiClientProviderProps): ReactElement {
  const {
    client,
    basePaths = EMPTY_BASE_PATHS,
    headerSources = EMPTY_HEADER_SOURCES,
    children,
  } = props;

  // Memoised on [client, headerSources] exactly — the decorated client this hands out is a new
  // object only when one of those two identities changes. A host passing an inline array
  // literal as `headerSources` defeats this (a new array identity every render), which is the
  // documented footgun (docs/CONTRACT.md §15), not a bug in this memoisation.
  const decoratedClient = useMemo(
    () => decorateClient(client, headerSources),
    [client, headerSources],
  );

  const value = useMemo<ApiClientContextValue>(
    () => ({ client: decoratedClient, basePaths }),
    [decoratedClient, basePaths],
  );

  return <ApiClientContext.Provider value={value}>{children}</ApiClientContext.Provider>;
}

function normalizeBasePath(basePath: string): string {
  return basePath.replace(/\/+$/, "");
}

/**
 * Called from an app's own api/config.ts, never directly by a host. `key` is this app's
 * namespace; `defaultBasePath` is what the app's own README suggests if the host's `basePaths`
 * map has no entry for `key`. Both arguments are REQUIRED — a missing/typo'd `basePaths` entry
 * falls back to the calling app's own default, never to `""`/`"/"`.
 */
export function useApiClient(
  key: string,
  defaultBasePath: string,
): { client: HttpClient; basePath: string } {
  const context = useContext(ApiClientContext);
  if (context === null) {
    throw new Error(
      `useApiClient(${JSON.stringify(key)}) was called outside an <ApiClientProvider>. Mount it once in ` +
        `frontend/app/providers.tsx — see appkit's README, "Usage — mounting the shared provider".`,
    );
  }
  if (!defaultBasePath) {
    throw new Error(
      `useApiClient(${JSON.stringify(key)}, ${JSON.stringify(defaultBasePath)}) was called with an empty ` +
        "defaultBasePath — pass this app's own README-suggested base path; there is no host-wide-safe default.",
    );
  }

  const resolvedBasePath = normalizeBasePath(context.basePaths[key] ?? defaultBasePath);

  return useMemo(
    () => ({ client: context.client, basePath: resolvedBasePath }),
    [context.client, resolvedBasePath],
  );
}
