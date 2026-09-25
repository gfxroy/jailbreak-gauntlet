import { describe, expect, it } from "vitest";
import { heatColor, layerLabel, pct, techniqueLabel } from "./format";

describe("format helpers", () => {
  it("formats percentages", () => {
    expect(pct(0.1234)).toBe("12%");
    expect(pct(0.1234, 1)).toBe("12.3%");
    expect(pct(Number.NaN)).toBe("–");
  });

  it("labels known and unknown keys", () => {
    expect(techniqueLabel("payload_splitting")).toBe("Payload splitting");
    expect(layerLabel("llm_judge")).toBe("LLM judge");
    expect(techniqueLabel("brand_new_trick")).toBe("Brand new trick");
  });

  it("maps heat ramp endpoints and empty cells", () => {
    expect(heatColor(0, 5)).toBe("rgb(27 36 50)");
    expect(heatColor(1, 5)).toBe("rgb(61 255 162)");
    expect(heatColor(1, 0)).toContain("0.6");
  });
});
