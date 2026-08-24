# tests/fixtures/

Cross-half golden vectors — the rule this directory exists to enforce (`docs/CONTRACT.md` §19),
stated once here rather than as a footnote on each utility:

> Any behaviour that must agree across the two halves is verified by **one fixture file both
> test suites load**, never by two independently hand-written test files that happen to agree
> today. A divergence between the halves must be impossible to introduce by editing only one
> side's tests.

Test-only: this directory ships in neither the Python wheel nor the npm distributable.

## Files (all created in later phases)

- **`error-codes.json`** — the ten `code` values, in the exact order given in `docs/CONTRACT.md`
  §1. Both `appkit.exceptions.ERROR_CODES` (backend) and `ApiErrorCode` (frontend) are asserted
  against this file rather than against each other's source directly.
- **`jalali-vectors.json`** — Gregorian↔Jalali round-trip vectors: every leap year in the
  33-year cycle plus adjacent non-leap years, Esfand 29 vs. 30 in both, Nowruz across several
  years, the 31-day/30-day month boundary, Gregorian leap years including century years, and
  dates well outside the near present. Every vector round-tripped in both directions.
- **`money-vectors.json`** — `{input, output}` pairs for `parse_amount`/`parseAmount` and
  `format_amount`/`formatAmount`, including `0` and a negative value.
- **`truncate-vectors.json`** — length/suffix/expected-output triples, including emoji and
  combining-character cases.

## How each suite loads this directory

Not settled by the contract — decided here so a later phase doesn't invent a second convention:

- **Python** (`tests/backend/`): `Path(__file__).parents[1] / "fixtures"`.
- **TypeScript** (`tests/frontend/`, created in Phase 5): a `vitest.config.ts` alias pointing at
  this same directory.
