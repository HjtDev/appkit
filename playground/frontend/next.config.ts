import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Turbopack's `root` is a HARD compilation boundary: "files outside of the workspace root
  // are not compiled" (its own error message). appkit's own frontend/ lives at the REPO root,
  // one level above the playground/ npm workspace root — §11.2's file:../../frontend
  // path-linking is specifically OUTSIDE any workspace by design (dev AND release use the same
  // pyproject.toml/package.json line). So root has to be the repo root, the true common
  // ancestor of both playground/ (this npm workspace) and frontend/ (appkit's own, consumed by
  // path) — not playground/ itself, and not this app's own directory. Getting this wrong
  // produces two DIFFERENT failures depending on which directory is picked, both reproduced
  // and logged while debugging this: `root` too narrow (this dir, or playground/) ->
  // "Module not found: Can't resolve 'appkit'"; `root` missing entirely -> Turbopack
  // mis-infers it from the nearest lockfile and gets a DIFFERENT wrong answer. See
  // playground/FINDINGS.md — this took real trial and error to pin down, and the fix isn't
  // documented anywhere in docs/APP-DESIGN.md's §11.2 playground brief.
  turbopack: {
    root: path.join(__dirname, "..", ".."),
  },
};

export default nextConfig;
