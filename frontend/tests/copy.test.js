import { describe, expect, it } from "vitest";
import { FALLBACK, fill } from "../src/copy.jsx";

describe("copy", () => {
  it("fills named tokens and keeps unknown ones", () => {
    expect(fill("Hello {name}", { name: "Pilot" })).toBe("Hello Pilot");
    expect(fill("Hello {name}")).toBe("Hello {name}");
  });

  it("keeps fallback brand copy without hero stills", () => {
    expect(FALLBACK.brand.programName).toMatch(/F\/A-18/);
    expect(FALLBACK.docs.heroStills).toBeUndefined();
  });
});
