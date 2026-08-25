/**
 * `HttpClient` — the injected interface (docs/CONTRACT.md §14).
 *
 * appkit never implements this. A host constructs a real client (reads
 * `NEXT_PUBLIC_API_URL`, handles CSRF, decides the credentials mode — all host configuration,
 * §13) and injects it via `ApiClientProvider`. TypeScript is structurally typed, so the host's
 * concrete client satisfies this interface by having the right methods — no `implements`
 * declaration, no import of this type in the host's own client module required.
 *
 * Five methods — a deliberate deviation from an earlier draft that listed only
 * `get`/`post`/`patch`/`delete`. `put` is included because the base-scaffold's own client
 * already implements it, and an SDK wrapping a DRF `ViewSet`'s full-update action needs to
 * express it without reaching for a `request()` method this interface deliberately excludes
 * (`request()` is the host implementation's own internal method — exposing it here would leak
 * implementation shape instead of describing behaviour).
 */
export interface HttpClient {
  get<T>(path: string, init?: RequestInit): Promise<T>;
  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  patch<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  delete<T>(path: string, init?: RequestInit): Promise<T>;
}

/**
 * A composable per-request header source (docs/CONTRACT.md §16) — the mechanism a host uses to
 * attach headers (an auth app's `Authorization`, a tenant-scoping app's `X-Tenant-ID`) without
 * appkit knowing anything about auth. appkit never reads, stores, refreshes, or inspects a
 * token; it only invokes these opaque callbacks and merges their output into request headers.
 *
 * `ApiClientProvider`'s `headerSources` are invoked left-to-right, then a call's own
 * `init.headers` last — later always wins. A source that throws synchronously or returns a
 * rejected promise fails the whole request, naming which source failed by index, rather than
 * silently shipping the request without that header.
 */
export type HeaderSource = () => HeadersInit | Promise<HeadersInit>;
