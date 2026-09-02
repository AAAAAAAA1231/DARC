import { describe, expect, it } from "vitest";
import { fmtNum, fmtPct, fmtUsd } from "./format";

describe("formatters", () => {
  it("does not invent UNKNOWN as zero", () => {
    expect(fmtNum(null)).toBe("UNKNOWN");
    expect(fmtNum("")).toBe("UNKNOWN");
    expect(fmtUsd(undefined)).toBe("UNKNOWN");
  });
  it("shortens large TVL", () => {
    expect(fmtUsd(1_500_000_000)).toBe("$1.50B");
  });
  it("treats 0.1 as 10%", () => {
    expect(fmtPct(0.1)).toBe("10.00%");
  });
});
