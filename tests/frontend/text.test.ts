import { describe, expect, it } from "vitest";

import { toEnglishDigits, toPersianDigits, truncate } from "../../frontend/src/text.js";

import truncateVectors from "@fixtures/truncate-vectors.json";

interface TruncateVector {
  value: string;
  length: number;
  suffix: string;
  expected: string;
  note?: string;
}

describe("truncate — driven by the shared golden vectors", () => {
  for (const vector of truncateVectors as TruncateVector[]) {
    const label = vector.note ?? `truncate(${JSON.stringify(vector.value)}, ${vector.length})`;
    it(label, () => {
      expect(truncate(vector.value, vector.length, vector.suffix)).toBe(vector.expected);
    });
  }

  it("defaults the suffix to “…”", () => {
    expect(truncate("hello world", 8)).toBe("hello w…");
  });
});

describe("toEnglishDigits / toPersianDigits", () => {
  it("normalises Persian digits to ASCII", () => {
    expect(toEnglishDigits("۰۱۲۳۴۵۶۷۸۹")).toBe("0123456789");
  });

  it("normalises Arabic-Indic digits to ASCII", () => {
    expect(toEnglishDigits("٠١٢٣٤٥٦٧٨٩")).toBe("0123456789");
  });

  it("passes through unrecognised characters unchanged", () => {
    expect(toEnglishDigits("abc-۱۲۳-def")).toBe("abc-123-def");
  });

  it("never raises on empty input", () => {
    expect(toEnglishDigits("")).toBe("");
    expect(toPersianDigits("")).toBe("");
  });

  it("converts ASCII digits to Persian digits", () => {
    expect(toPersianDigits("0123456789")).toBe("۰۱۲۳۴۵۶۷۸۹");
  });

  it("passes through non-ASCII-digit characters unchanged", () => {
    expect(toPersianDigits("abc-123-def")).toBe("abc-۱۲۳-def");
  });
});
