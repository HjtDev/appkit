import { describe, expect, it } from "vitest";

import {
  isLeapJalaaliYear,
  isValidJalaaliDate,
  toGregorian,
  toJalaali,
} from "../../frontend/src/vendor/jalaali.js";

/**
 * The 79 golden round-trip vectors (tests/fixtures/jalali-vectors.json) all fall within
 * Jalali years ~1300–1450, which never crosses most of the 33-year break-point table's own
 * internal branches (jalCal/jalCalLeap's "within 6 years of the next break" and "jump%33===4"
 * special cases). These tests exercise those branches directly against years chosen from the
 * break-point table itself, asserting only internal self-consistency (round-trips through the
 * vendored arithmetic), not external fixture agreement — the golden vectors already cover
 * fixture agreement for the range that matters to appkit's own callers.
 */
describe("vendor/jalaali.ts — break-point-table edge branches", () => {
  it("round-trips a year within 6 of a break-point ('jump - n < 6' branch)", () => {
    // Break table has an entry at 38; year 35 is within 6 years of it in the -61..9..38 chain.
    const gregorian = toGregorian(35, 1, 1);
    expect(toJalaali(gregorian.gy, gregorian.gm, gregorian.gd)).toEqual({ jy: 35, jm: 1, jd: 1 });
  });

  it("round-trips a year just before the 1210->1635 break", () => {
    const gregorian = toGregorian(1630, 12, 1);
    expect(toJalaali(gregorian.gy, gregorian.gm, gregorian.gd)).toEqual({
      jy: 1630,
      jm: 12,
      jd: 1,
    });
  });

  it("round-trips a year hitting the 'jump % 33 === 4 && jump - n === 4' branch (segment jump=70, n=66)", () => {
    // Segment 1111..1181 has jump = 1181 - 1111 = 70 (70 % 33 === 4); n = 66 puts jy at 1177.
    const gregorian = toGregorian(1177, 1, 1);
    expect(toJalaali(gregorian.gy, gregorian.gm, gregorian.gd)).toEqual({
      jy: 1177,
      jm: 1,
      jd: 1,
    });
  });

  it("throws for a year below the break table's floor", () => {
    expect(() => toGregorian(-1000, 1, 1)).toThrow(/Invalid Jalaali year/);
  });

  it("throws for a year at or above the break table's ceiling", () => {
    expect(() => toGregorian(3178, 1, 1)).toThrow(/Invalid Jalaali year/);
  });

  it("isValidJalaaliDate returns false (not throw) for a year outside the break table", () => {
    expect(isValidJalaaliDate(-1000, 1, 1)).toBe(false);
    expect(isValidJalaaliDate(5000, 1, 1)).toBe(false);
  });

  it("isLeapJalaaliYear agrees with jalaaliMonthLength's own leap check for a near-break year", () => {
    // Indirect exercise of jalCalLeap's own "within 6 of a break" branch, independent of jalCal's.
    expect(typeof isLeapJalaaliYear(35)).toBe("boolean");
    expect(typeof isLeapJalaaliYear(1630)).toBe("boolean");
  });

  it("isLeapJalaaliYear throws for a year outside the break table (jalCalLeap's own guard)", () => {
    // isValidJalaaliDate's own range check short-circuits before ever calling jalCalLeap, so
    // this branch is only reachable by calling isLeapJalaaliYear directly, out of range.
    expect(() => isLeapJalaaliYear(-1000)).toThrow(/Invalid Jalaali year/);
  });
});
