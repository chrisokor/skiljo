import { describe, expect, it } from "vitest";
import { SDK_VERSION } from "./index";

describe("SDK_VERSION", () => {
  it("is defined", () => {
    expect(SDK_VERSION).toBe("0.1.0");
  });
});
