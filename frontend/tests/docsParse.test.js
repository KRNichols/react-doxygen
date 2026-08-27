import { describe, expect, it } from "vitest";
import {
  extractTitle,
  parseHtml,
  rewritePageHref,
  stripTitleAttributes,
} from "../src/docsParse.js";

describe("docsParse", () => {
  it("rewrites relative HTML links onto /docs", () => {
    expect(rewritePageHref("class_radar_suite.html", "index.html")).toBe(
      "/docs/class_radar_suite.html",
    );
  });

  it("extracts the Doxygen title", () => {
    const doc = parseHtml(
      '<html><body><div class="headertitle"><div class="title">Main Page</div></div></body></html>',
    );
    expect(extractTitle(doc)).toBe("Main Page");
  });

  it("strips title attributes used as hover help", () => {
    const doc = parseHtml(
      '<html><body><div class="contents"><a href="x.html" title="open X">X</a></div></body></html>',
    );
    stripTitleAttributes(doc);
    expect(doc.querySelector("a").hasAttribute("title")).toBe(false);
  });
});
