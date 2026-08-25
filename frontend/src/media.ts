/**
 * `mediaUrl` — the frontend counterpart to the backend's `file_url`/`absolute_url`
 * (`appkit.media`, docs/CONTRACT.md §18 <-> §2.11).
 *
 * Takes its base **as an argument**, never reading `NEXT_PUBLIC_API_URL` itself — this is the
 * literal mechanism that keeps §13's boundary intact for the one function in this contract that
 * would otherwise have the strongest pull toward reading an env var directly. The host's own
 * code (or an app's manager, which already has the injected `basePath`/client) supplies
 * `baseUrl`; this function stays pure.
 */

function isAbsolute(url: string): boolean {
  // Mirrors backend/src/appkit/media.py's `_is_absolute`: a scheme AND an authority (netloc)
  // must both be present. `new URL(url)` with no base throws for anything relative — including
  // a protocol-relative URL ("//cdn.example.com/x"), which has an authority but no scheme, the
  // same "not absolute" verdict Python's `urlparse` reaches for it (`bool("" and "cdn")` is
  // `False`) — it still gets prefixed with `baseUrl` below, never double-prefixed.
  try {
    const parsed = new URL(url);
    return parsed.protocol !== "" && parsed.host !== "";
  } catch {
    return false;
  }
}

/**
 * `null`/`undefined`/`""` in -> `null` out. An already-absolute URL passes through unchanged,
 * never double-prefixed. A relative URL is prefixed with `baseUrl` (trailing/leading slashes
 * normalised so the join never double- or zero-slashes).
 */
export function mediaUrl(value: string | null | undefined, baseUrl: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (isAbsolute(value)) return value;

  const base = baseUrl.replace(/\/+$/, "");
  const path = value.startsWith("/") ? value : `/${value}`;
  return `${base}${path}`;
}
