/**
 * Jalaali <-> Gregorian calendar arithmetic — vendored, not depended on.
 *
 * docs/CONTRACT.md §19 evaluates `jalaali-js` as a runtime dependency and rejects it in favour
 * of vendoring: the conversion is fixed, well-defined arithmetic (the standard 33-year-cycle
 * algorithm) that needs no upstream updates once correct, and §22 makes zero runtime
 * `dependencies` a structural property of this package (every dependency added here becomes
 * every host's and every installed app SDK's dependency transitively). This file is that
 * vendored implementation.
 *
 * Provenance: ported from `jalaali-js` v1.2.8 (https://github.com/jalaali/jalaali-js),
 * commit-equivalent to the npm-published 1.2.8 tarball, by Behrang Norouzinia. The algorithm
 * itself traces to Borkowski's 33-year-cycle break-point table (cited in the upstream source).
 * Verified against `tests/fixtures/jalali-vectors.json` (all 79 round-trip vectors, both
 * directions, plus all 4 invalid-date vectors) before vendoring — see docs/CONTRACT.md §19's
 * provenance note. Intentionally frozen: the arithmetic does not need updating, so this file is
 * not expected to track upstream `jalaali-js` releases.
 *
 * Internal to appkit — never exported from src/index.ts, not covered by appkit's own semver.
 * `toJalaali`/`toGregorian`/`isValidJalaaliDate` are consumed by ../dates.ts.
 *
 * ---
 *
 * MIT License
 *
 * Copyright (c) 2020 Behrang Norouzinia
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

export interface JalaaliDate {
  jy: number;
  jm: number;
  jd: number;
}

export interface GregorianDate {
  gy: number;
  gm: number;
  gd: number;
}

interface JalCalWithLeap {
  leap: number;
  gy: number;
  march: number;
}

interface JalCalWithoutLeap {
  gy: number;
  march: number;
}

// Jalaali years starting the 33-year rule.
const breaks = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394,
  2456, 3178,
];

function div(a: number, b: number): number {
  return Math.trunc(a / b);
}

function mod(a: number, b: number): number {
  return a - Math.trunc(a / b) * b;
}

/** Determines how many years have passed since the last leap year (0 to 4). */
function jalCalLeap(jy: number): number {
  const bl = breaks.length;
  // `breaks` is a fixed 20-element literal (never empty) — `!` here documents that invariant
  // rather than a runtime check `noUncheckedIndexedAccess` can't otherwise see; there is no
  // input to this module that makes `breaks[0]` genuinely undefined.
  const jp = breaks[0]!;
  if (jy < jp || jy >= breaks[bl - 1]!) {
    throw new Error(`Invalid Jalaali year ${jy}`);
  }

  let jpCursor = jp;
  let jump = 0;
  for (let i = 1; i < bl; i += 1) {
    const jm = breaks[i]!;
    jump = jm - jpCursor;
    if (jy < jm) break;
    jpCursor = jm;
  }
  let n = jy - jpCursor;

  if (jump - n < 6) {
    n = n - jump + div(jump + 4, 33) * 33;
  }
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;
  return leap;
}

/**
 * Determines whether the Jalaali year `jy` is leap, and the Gregorian March day of Farvardin
 * the 1st for that year. `withoutLeap: true` skips the leap computation (j2d's own call site
 * doesn't need it).
 */
function jalCal(jy: number, withoutLeap: true): JalCalWithoutLeap;
function jalCal(jy: number, withoutLeap: false): JalCalWithLeap;
function jalCal(jy: number, withoutLeap: boolean): JalCalWithLeap | JalCalWithoutLeap {
  const bl = breaks.length;
  const gy = jy + 621;
  let leapJ = -14;
  // See jalCalLeap's identical comment above — `breaks` is a fixed non-empty literal.
  const jp = breaks[0]!;
  if (jy < jp || jy >= breaks[bl - 1]!) {
    throw new Error(`Invalid Jalaali year ${jy}`);
  }

  let jpCursor = jp;
  let jump = 0;
  for (let i = 1; i < bl; i += 1) {
    const jm = breaks[i]!;
    jump = jm - jpCursor;
    if (jy < jm) break;
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jpCursor = jm;
  }
  let n = jy - jpCursor;

  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) {
    leapJ += 1;
  }

  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;

  if (withoutLeap) return { gy, march };

  if (jump - n < 6) {
    n = n - jump + div(jump + 4, 33) * 33;
  }
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;

  return { leap, gy, march };
}

/**
 * Calculates the Julian Day number from a Gregorian calendar date. Corresponds to the noon of
 * the date (12:00 UT). Valid since 1 March, -100100, up to a few million years into the future.
 */
export function g2d(gy: number, gm: number, gd: number): number {
  let d =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
    div(153 * mod(gm + 9, 12) + 2, 5) +
    gd -
    34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

/** Calculates a Gregorian calendar date from a Julian Day number. */
export function d2g(jdn: number): GregorianDate {
  let j = 4 * jdn + 139361631;
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

/** Converts a Jalaali calendar date to the Julian Day number. */
export function j2d(jy: number, jm: number, jd: number): number {
  const r = jalCal(jy, true);
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

/** Converts a Julian Day number to a Jalaali calendar date. */
export function d2j(jdn: number): JalaaliDate {
  const gy = d2g(jdn).gy;
  let jy = gy - 621;
  const r = jalCal(jy, false);
  const jdn1f = g2d(r.gy, 3, r.march);
  let jd: number;
  let jm: number;
  let k: number;

  k = jdn - jdn1f;
  if (k >= 0) {
    if (k <= 185) {
      jm = 1 + div(k, 31);
      jd = mod(k, 31) + 1;
      return { jy, jm, jd };
    }
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  jm = 7 + div(k, 30);
  jd = mod(k, 30) + 1;
  return { jy, jm, jd };
}

/** Converts a Gregorian date to Jalaali. */
export function toJalaali(gy: number, gm: number, gd: number): JalaaliDate {
  return d2j(g2d(gy, gm, gd));
}

/** Converts a Jalaali date to Gregorian. */
export function toGregorian(jy: number, jm: number, jd: number): GregorianDate {
  return d2g(j2d(jy, jm, jd));
}

/** Number of days in a given month of a Jalaali year. */
export function jalaaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isLeapJalaaliYear(jy) ? 30 : 29;
}

/** Whether `jy` is a leap Jalaali year (366 days). */
export function isLeapJalaaliYear(jy: number): boolean {
  return jalCalLeap(jy) === 0;
}

/** Whether `(jy, jm, jd)` names a real Jalaali calendar date. */
export function isValidJalaaliDate(jy: number, jm: number, jd: number): boolean {
  return (
    jy >= -61 && jy <= 3177 && jm >= 1 && jm <= 12 && jd >= 1 && jd <= jalaaliMonthLength(jy, jm)
  );
}
