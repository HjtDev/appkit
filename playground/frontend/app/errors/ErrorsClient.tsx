"use client";

import { useState } from "react";
import { useApiClient, isApiError, type ApiError } from "@hjtdev/appkit";

type Result = { label: string; ok: boolean; detail: string };

const CASES: Array<{ label: string; path: string; method: "GET" | "POST"; init?: RequestInit }> = [
  { label: "validation_error", path: "/errors/validation/", method: "POST", init: { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "" }) } },
  { label: "parse_error (via items/)", path: "/items/", method: "POST", init: { headers: { "Content-Type": "application/json" }, body: "{not valid json" } },
  { label: "not_authenticated", path: "/errors/not-authenticated/", method: "GET" },
  { label: "authentication_failed", path: "/errors/authentication-failed/", method: "GET", init: { headers: { Authorization: "Basic " + btoa("nobody:wrongpass") } } },
  { label: "permission_denied", path: "/errors/permission-denied/", method: "GET" },
  { label: "not_found", path: "/errors/not-found/", method: "GET" },
  { label: "method_not_allowed", path: "/errors/method-not-allowed/", method: "POST" },
  { label: "throttled (hits demo_list scope)", path: "/items/", method: "GET" },
  { label: "server_error", path: "/errors/server/", method: "GET" },
  { label: "error (catch-all, 415)", path: "/errors/catchall/", method: "GET" },
];

export default function ErrorsClient() {
  const { client, basePath } = useApiClient("demo", "/api/v1/demo");
  const [results, setResults] = useState<Record<string, Result>>({});

  const run = async (c: (typeof CASES)[number]) => {
    try {
      if (c.method === "GET") {
        await client.get(`${basePath}${c.path}`, c.init);
      } else {
        await client.post(`${basePath}${c.path}`, undefined, c.init);
      }
      setResults((r) => ({ ...r, [c.label]: { label: c.label, ok: true, detail: "200 (no error thrown)" } }));
    } catch (e) {
      const detail = isApiError(e)
        ? `code=${(e as ApiError).code} status=${(e as ApiError).status} requestId=${(e as ApiError).requestId}`
        : `non-ApiError thrown: ${String(e)}`;
      setResults((r) => ({ ...r, [c.label]: { label: c.label, ok: isApiError(e), detail } }));
    }
  };

  return (
    <main>
      <h1>Ten error-envelope codes, over real HTTP</h1>
      <p>
        Each button hits a backend view built to raise exactly one code
        (docs/CONTRACT.md §1). The result shown is what this page&apos;s{" "}
        <code>lib/api-client.ts</code> + appkit&apos;s <code>apiErrorFromEnvelope</code> parsed
        it into — proving the two halves agree with EACH OTHER, not just with the fixture.
      </p>
      <p>
        Some cases depend on which user is logged in via <code>/admin/</code> (Django session
        cookie): logged out → not_authenticated fires for permission_denied too; logged in as a
        non-staff user → permission_denied; logged in as staff → 200.
      </p>
      <p>
        <strong>The nginx-502 case:</strong> run <code>docker compose stop backend</code>, then
        click any button — the HTML error page nginx returns should still degrade to a
        well-formed <code>ApiError</code> with <code>code: &quot;unknown_error&quot;</code>,
        never an unhandled throw.
      </p>
      <ul>
        {CASES.map((c) => {
          const result = results[c.label];
          return (
            <li key={c.label} style={{ marginBottom: "0.5rem" }}>
              <button onClick={() => run(c)}>{c.label}</button>{" "}
              {result && (
                <span style={{ color: result.ok ? "green" : "crimson" }}>{result.detail}</span>
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}
