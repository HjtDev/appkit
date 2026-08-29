// Host's own — appkit knows nothing about it. Stands in for README.md:238's
// `import { getAuthHeaders } from "@/lib/auth"`. This playground's backend doesn't need an
// extra auth header (session + basic auth cover it), so this exists purely to prove
// ApiClientProvider's headerSources mechanism (docs/CONTRACT.md §16) actually reaches the wire.
import type { HeaderSource } from "@hjtdev/appkit";

export const getAuthHeaders: HeaderSource = () => ({
  "X-Playground-Client": "demo-frontend",
});
