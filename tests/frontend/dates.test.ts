import { afterEach, describe, expect, it, vi } from "vitest";

import {
  calendarDateIn,
  formatJalali,
  fromJalali,
  parseJalali,
  toJalali,
  type JalaliDate,
} from "../../frontend/src/dates.js";

import jalaliVectors from "@fixtures/jalali-vectors.json";

interface RoundTripVector {
  gregorian: string;
  jalali: JalaliDate;
  note: string;
}
interface FormatVector {
  jalali: JalaliDate;
  fmt: string;
  expected: string;
}
interface ParseVector {
  value: string;
  fmt: string;
  jalali: JalaliDate;
}
interface InvalidVector {
  year: number;
  month: number;
  day: number;
  note: string;
}

describe("toJalali — driven by every golden round-trip vector", () => {
  for (const vector of jalaliVectors.round_trip as RoundTripVector[]) {
    it(`${vector.gregorian} -> ${JSON.stringify(vector.jalali)} (${vector.note})`, () => {
      expect(toJalali(vector.gregorian)).toEqual(vector.jalali);
    });
  }

  it("accepts a Gregorian {year, month, day} triple, not only a string", () => {
    expect(toJalali({ year: 2024, month: 3, day: 20 })).toEqual({ year: 1403, month: 1, day: 1 });
  });

  it('rejects a string that isn\'t a "YYYY-MM-DD" date', () => {
    expect(() => toJalali("not-a-date")).toThrow(/is not a "YYYY-MM-DD" date string/);
  });
});

describe("fromJalali — driven by every golden round-trip vector", () => {
  for (const vector of jalaliVectors.round_trip as RoundTripVector[]) {
    it(`${JSON.stringify(vector.jalali)} -> ${vector.gregorian} (${vector.note})`, () => {
      expect(fromJalali(vector.jalali)).toBe(vector.gregorian);
    });
  }
});

describe("every golden vector round-trips in both directions", () => {
  for (const vector of jalaliVectors.round_trip as RoundTripVector[]) {
    it(`Gregorian -> Jalali -> Gregorian: ${vector.gregorian}`, () => {
      expect(fromJalali(toJalali(vector.gregorian))).toBe(vector.gregorian);
    });
    it(`Jalali -> Gregorian -> Jalali: ${JSON.stringify(vector.jalali)}`, () => {
      expect(toJalali(fromJalali(vector.jalali))).toEqual(vector.jalali);
    });
  }
});

describe("fromJalali rejects every golden invalid vector", () => {
  for (const vector of jalaliVectors.invalid as InvalidVector[]) {
    it(vector.note, () => {
      expect(() =>
        fromJalali({ year: vector.year, month: vector.month, day: vector.day }),
      ).toThrow();
    });
  }
});

describe("formatJalali — driven by the golden format vectors", () => {
  for (const vector of jalaliVectors.format as FormatVector[]) {
    it(`formatJalali(${JSON.stringify(vector.jalali)}, ${JSON.stringify(vector.fmt)}) === ${JSON.stringify(vector.expected)}`, () => {
      expect(formatJalali(vector.jalali, vector.fmt)).toBe(vector.expected);
    });
  }

  it("defaults fmt to %Y/%m/%d", () => {
    expect(formatJalali({ year: 1403, month: 1, day: 1 })).toBe("1403/01/01");
  });

  it("rejects an unsupported directive", () => {
    expect(() => formatJalali({ year: 1403, month: 1, day: 1 }, "%B")).toThrow(/unsupported/);
  });

  it("rejects a dangling percent", () => {
    expect(() => formatJalali({ year: 1403, month: 1, day: 1 }, "%Y/%")).toThrow(/dangling/);
  });

  it("renders %H %M %S as zero-padded zeros — JalaliDate carries no time component", () => {
    expect(formatJalali({ year: 1403, month: 1, day: 1 }, "%H:%M:%S")).toBe("00:00:00");
  });

  it("handles a literal %% in the format", () => {
    expect(formatJalali({ year: 1403, month: 1, day: 1 }, "%Y%%%m/%d")).toBe("1403%01/01");
  });

  it("pads a negative year with a leading '-', not a padded absolute value", () => {
    // Jalali year -61 is the break table's own floor (vendor/jalaali.ts) — a legitimate input,
    // even though every value on the wire in practice is comfortably positive.
    expect(formatJalali({ year: -61, month: 1, day: 1 })).toBe("-0061/01/01");
  });
});

describe("parseJalali — driven by the golden parse vectors", () => {
  for (const vector of jalaliVectors.parse as ParseVector[]) {
    it(`parseJalali(${JSON.stringify(vector.value)}, ${JSON.stringify(vector.fmt)})`, () => {
      expect(toJalali(fromJalali(parseJalali(vector.value, vector.fmt)))).toEqual(vector.jalali);
      expect(parseJalali(vector.value, vector.fmt)).toEqual(vector.jalali);
    });
  }

  it("rejects a dangling percent", () => {
    expect(() => parseJalali("1403/01", "%Y/%")).toThrow(/dangling/);
  });

  it("rejects an unsupported directive", () => {
    expect(() => parseJalali("anything", "%B")).toThrow(/unsupported/);
  });

  it("raises for a string not matching the format", () => {
    expect(() => parseJalali("not-a-date", "%Y/%m/%d")).toThrow(/does not match/);
  });

  it("raises for a string naming an invalid Jalali date", () => {
    expect(() => parseJalali("1404/12/30", "%Y/%m/%d")).toThrow();
  });

  it("defaults an omitted directive to 1 for month/day", () => {
    expect(parseJalali("1403", "%Y")).toEqual({ year: 1403, month: 1, day: 1 });
  });

  it("handles a literal %% in the format", () => {
    expect(parseJalali("1403%01/01", "%Y%%%m/%d")).toEqual({ year: 1403, month: 1, day: 1 });
  });

  it("uses a non-capturing group for a directive repeated in fmt", () => {
    expect(parseJalali("1403-1403", "%Y-%Y")).toEqual({ year: 1403, month: 1, day: 1 });
  });

  it("defaults year/month/day all to 1 when fmt has no directives at all", () => {
    expect(parseJalali("literal", "literal")).toEqual({ year: 1, month: 1, day: 1 });
  });
});

describe("calendarDateIn", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("raises a named error if the runtime's Intl implementation omits an expected part", () => {
    // Defensive branch: every real ICU implementation returns year/month/day for this
    // formatter config, so this is only reachable by simulating a broken/incomplete Intl.
    vi.spyOn(Intl.DateTimeFormat.prototype, "formatToParts").mockReturnValue([
      { type: "month", value: "01" },
      { type: "day", value: "01" },
    ]);
    expect(() => calendarDateIn("2024-01-01T00:00:00.000Z", "UTC")).toThrow(
      /could not resolve "year" for timeZone UTC/,
    );
  });

  it("resolves the next calendar day at a day boundary in Asia/Tehran (+03:30)", () => {
    // 23:30 UTC on 2024-01-01 is 03:00 on 2024-01-02 in Asia/Tehran — proving this function
    // actually localises rather than truncating the instant's UTC date.
    const result = calendarDateIn("2024-01-01T23:30:00.000Z", "Asia/Tehran");
    expect(result).toEqual(toJalali("2024-01-02"));
  });

  it("stays on the same UTC day for a UTC timeZone", () => {
    const result = calendarDateIn("2024-01-01T23:30:00.000Z", "UTC");
    expect(result).toEqual(toJalali("2024-01-01"));
  });

  it("accepts a Date instance, not only an ISO string", () => {
    const instant = new Date("2024-01-01T23:30:00.000Z");
    expect(calendarDateIn(instant, "Asia/Tehran")).toEqual(toJalali("2024-01-02"));
  });
});
