import { describe, expect, it } from "vitest";
import { holdingFor } from "./holdings";

describe("holdingFor", () => {
  it("matches BTCUSDT and BTC", () => {
    const overlay = { BTCUSDT: { held: true, avg_cost: "1" }, BTC: { held: true, avg_cost: "1" } };
    expect(holdingFor(overlay, "btc")?.held).toBe(true);
    expect(holdingFor(overlay, "BTCUSDT")?.avg_cost).toBe("1");
    expect(holdingFor(undefined, "BTC")).toBeUndefined();
  });
});
