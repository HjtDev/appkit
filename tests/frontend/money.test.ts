import { describe, expect, it } from "vitest";

import { formatAmount, parseAmount } from "../../frontend/src/money.js";

import moneyVectors from "@fixtures/money-vectors.json";

interface ParseVector {
  input: string | number;
  output: number;
}
interface ParseErrorVector {
  input: string;
}
interface FormatVector {
  input: number;
  currency: string;
  output: string;
}

describe("parseAmount — driven by the shared golden vectors", () => {
  for (const vector of moneyVectors.parse as ParseVector[]) {
    it(`parseAmount(${JSON.stringify(vector.input)}) === ${vector.output}`, () => {
      expect(parseAmount(vector.input)).toBe(vector.output);
    });
  }

  for (const vector of moneyVectors.parse_errors as ParseErrorVector[]) {
    it(`parseAmount(${JSON.stringify(vector.input)}) throws`, () => {
      expect(() => parseAmount(vector.input)).toThrow();
    });
  }

  it("throws TypeError for a non-integer number", () => {
    expect(() => parseAmount(12000.5)).toThrow(TypeError);
  });

  it("throws RangeError beyond Number.MAX_SAFE_INTEGER (number input)", () => {
    expect(() => parseAmount(Number.MAX_SAFE_INTEGER + 10)).toThrow(RangeError);
  });

  it("throws RangeError beyond Number.MAX_SAFE_INTEGER (string input)", () => {
    expect(() => parseAmount(String(Number.MAX_SAFE_INTEGER) + "0")).toThrow(RangeError);
  });

  it("accepts an integer number unchanged", () => {
    expect(parseAmount(500)).toBe(500);
  });
});

describe("formatAmount — driven by the shared golden vectors", () => {
  for (const vector of moneyVectors.format as FormatVector[]) {
    it(`formatAmount(${vector.input}, ${JSON.stringify(vector.currency)}) === ${JSON.stringify(vector.output)}`, () => {
      expect(formatAmount(vector.input, vector.currency)).toBe(vector.output);
    });
  }

  it("defaults currency to empty string", () => {
    expect(formatAmount(1000000)).toBe("1,000,000");
  });

  it("never raises for 0 or a negative value", () => {
    expect(() => formatAmount(0)).not.toThrow();
    expect(() => formatAmount(-500)).not.toThrow();
  });

  it("emits Latin digits only, regardless of runtime locale", () => {
    expect(formatAmount(1000000)).toMatch(/^[0-9,]+$/);
  });
});
