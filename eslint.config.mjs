import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import prettierConfig from "eslint-config-prettier";

// Lives at the repo root, not frontend/, because ESLint 9's flat config treats any file outside
// the directory containing the config as ignored by default — and tests/frontend/ (the shared
// test tree docs/CONTRACT.md §19/tests/fixtures/README.md puts alongside tests/backend/, outside
// frontend/ itself) needs linting too. frontend/package.json's `lint` script points here via
// `--config ../eslint.config.mjs`.
//
// No eslint-config-next here — appkit ships no Next.js code of its own, only the interface and
// provider a Next.js host consumes. react-hooks catches the memoisation footguns §15's own
// contract calls out (a stale dependency array in useApiClient/ApiClientProvider). prettierConfig
// goes last so formatting rules never fight Prettier — Prettier owns formatting, ESLint owns
// everything else, matching BASE-DESIGN.md §5.1's split.
export default tseslint.config(
  {
    ignores: [
      "frontend/dist/**",
      "**/node_modules/**",
      "**/coverage/**",
      "backend/**",
      "docs/**",
    ],
  },
  ...tseslint.configs.recommended,
  {
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // An underscore-prefixed parameter names an intentionally-unused argument (an interface
      // slot a stub/mock must declare to match a signature but doesn't need) — used throughout
      // both src/ and tests/frontend/.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  prettierConfig,
);
