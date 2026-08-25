import HomeClient from "./HomeClient";

// Server-component wrapper, deliberately NOT "use client": `export const dynamic` must be
// exported from a server file to take effect. Without it, `next build`'s static-generation
// pass prerenders the client page in a build worker with no <Providers> in scope, and
// useDemoItems() throws "No QueryClient set" at BUILD time rather than at request time.
// Neither appkit's nor base-scaffold's docs mention this Next.js interaction anywhere — see
// playground/FINDINGS.md.
export const dynamic = "force-dynamic";

export default function HomePage() {
  return <HomeClient />;
}
