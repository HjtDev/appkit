/**
 * The host's own concrete HttpClient implementation — adapted from
 * base-scaffold/frontend/lib/api-client.ts (the reference appkit's own
 * httpclient-assignability.test.ts type-checks against), with the two changes
 * docs/CONTRACT.md:2069-2079 calls for:
 *
 *   1. Errors are constructed via appkit's apiErrorFromEnvelope, not a locally-declared
 *      ApiError class — so makeQueryClient's brand-based isApiError() retry predicate actually
 *      recognises what this client throws. This is the Phase 5 assignability check
 *      (httpclient-assignability.test.ts) promoted from compile time to a real runtime proof.
 *   2. appkit never sees a NEXT_PUBLIC_* env var or a fetch call — this file is the ONLY place
 *      either happens, per CLAUDE.md's "The frontend boundary".
 */
import { ApiError, apiErrorFromEnvelope, type HttpClient } from "@hjtdev/appkit";

const REQUEST_ID_HEADER = "X-Request-ID";
const CSRF_COOKIE_NAME = "csrftoken";
const CSRF_HEADER_NAME = "X-CSRFToken";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function resolveBaseUrl(override?: string): string {
  const baseUrl = override ?? process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) {
    throw new ApiError(
      "NEXT_PUBLIC_API_URL is not set. Copy .env.local.example to .env.local and fill it in.",
      { status: 0, code: "unknown_error" },
    );
  }
  return baseUrl;
}

export interface ApiClientOptions {
  /** Overrides NEXT_PUBLIC_API_URL. Mainly for tests. */
  baseUrl?: string;
  /** Default RequestCredentials for every call; defaults to "same-origin". */
  credentials?: RequestCredentials;
}

export class ApiClient implements HttpClient {
  private readonly baseUrl: string | undefined;
  private readonly defaultCredentials: RequestCredentials;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl;
    this.defaultCredentials = options.credentials ?? "same-origin";
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const baseUrl = resolveBaseUrl(this.baseUrl);
    const method = (init.method ?? "GET").toUpperCase();
    const credentials = init.credentials ?? this.defaultCredentials;

    const headers = new Headers(init.headers);
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (UNSAFE_METHODS.has(method) && credentials !== "omit") {
      const csrfToken = readCookie(CSRF_COOKIE_NAME);
      if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
    }

    const response = await fetch(`${baseUrl}${path}`, { ...init, method, credentials, headers });

    if (response.status === 204) {
      return undefined as T;
    }

    const requestId = response.headers.get(REQUEST_ID_HEADER);
    const retryAfter = response.headers.get("Retry-After");
    const contentType = response.headers.get("Content-Type") ?? "";

    if (!contentType.includes("application/json")) {
      // Exactly the nginx-502-HTML case docs/CLAUDE-CODE-GUIDE-APP.md's Phase 6 brief calls
      // out: apiErrorFromEnvelope degrades this to a well-formed ApiError (code:
      // "unknown_error") rather than this client ever throwing something un-typed.
      const text = await response.text();
      if (!response.ok) {
        throw apiErrorFromEnvelope({ status: response.status, body: text, requestId, retryAfter });
      }
      return text as unknown as T;
    }

    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw apiErrorFromEnvelope({ status: response.status, body: undefined, requestId, retryAfter });
    }

    if (!response.ok) {
      throw apiErrorFromEnvelope({ status: response.status, body: data, requestId, retryAfter });
    }

    return data as T;
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

export function getApiBaseUrl(): string {
  return resolveBaseUrl();
}

export const apiClient = new ApiClient();
