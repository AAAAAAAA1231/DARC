import { describe, expect, it } from "vitest";
import { api } from "./api";

describe("api helper", () => {
  it("is a function", () => {
    expect(typeof api).toBe("function");
  });
});
