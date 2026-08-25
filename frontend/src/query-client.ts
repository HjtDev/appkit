/**
 * `makeQueryClient` — a factory, never a module-level singleton (docs/CONTRACT.md §20).
 *
 * Ported unchanged from `../base-scaffold/frontend/lib/query-client.ts:19-37`, including its
 * full reasoning: Next.js renders on the server, and a module-level `QueryClient` would be
 * shared across every concurrent request/user, leaking one visitor's cached data into
 * another's response. A host calls this exactly once per browser session, inside `useState`,
 * in `frontend/app/providers.tsx`.
 */

import { QueryClient } from "@tanstack/react-query";

import { isApiError } from "./errors.js";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Retrying a 4xx (bad request, not found, forbidden) is pure latency — the response
          // won't change on retry. Only retry what might be transient: network failures and
          // 5xx, and only a couple of times.
          //
          // Checks `isApiError(error)` (a brand check), NOT `error instanceof ApiError` — an
          // `instanceof` check fails silently across two module instances of the same class
          // (two copies of appkit in one tree), which would make this predicate treat every
          // `ApiError` as an unrecognised error and retry a 400 needlessly.
          if (isApiError(error) && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
      },
    },
  });
}
