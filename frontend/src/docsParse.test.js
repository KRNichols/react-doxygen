import { describe, it, expect } from "vitest";
import {
  isDocRelative,
  resolveAgainst,
  rewriteAssetUrl,
  rewritePageHref,
  parseNavtree,
  flattenNavtree,
  filterSidebar,
  flattenSidebarHrefs,
  extractTitle,
  parseHtml,
  stripTitleAttributes,
  dropUnsafeAttrs,
  extractToc,
} from "./docsParse.js";
import { F18_STILLS, pickStill } from "./stills.js";

describe("isDocRelative", () => {
  it("rejects blanks, hashes, mailto, data, and absolute URLs", () => {
    expect(isDocRelative("")).toBe(false);
    expect(isDocRelative("#top")).toBe(false);
    expect(isDocRelative("mailto:a@b.c")).toBe(false);
    expect(isDocRelative("https://example.com/x")).toBe(false);
    expect(isDocRelative("//cdn.example/x")).toBe(false);
    expect(isDocRelative("class_radar.html")).toBe(true);
  });
});

describe("resolveAgainst", () => {
  it("resolves a sibling page against the current document", () => {
    expect(resolveAgainst("class_radar.html", "index.html")).toBe("class_radar.html");
  });
});

describe("rewriteAssetUrl", () => {
  it("points CSS at the auth-gated proxy", () => {
    expect(rewriteAssetUrl("doxygen.css", "index.html")).toBe("/api/docs/doxygen.css");
  });
  it("leaves absolute URLs alone", () => {
    expect(rewriteAssetUrl("https://example.com/a.css", "index.html")).toBe("https://example.com/a.css");
  });
});

describe("rewritePageHref", () => {
  it("keeps hash-only links", () => {
    expect(rewritePageHref("#sec", "index.html")).toBe("#sec");
  });
  it("maps HTML pages onto the SPA reader route", () => {
    expect(rewritePageHref("modules.html", "index.html")).toBe("/docs/modules.html");
  });
});

describe("parseNavtree and flattenNavtree", () => {
  it("parses a NAVTREE assignment", () => {
    const tree = parseNavtree("var NAVTREE = [[\"Home\", \"index.html\", []]];");
    expect(tree[0][0]).toBe("Home");
    const flat = flattenNavtree(tree);
    expect(flat[0].label).toBe("Home");
    expect(flat[0].href).toBe("index.html");
  });
  it("returns empty on garbage", () => {
    expect(parseNavtree("nope")).toEqual([]);
  });
});

describe("filterSidebar", () => {
  it("keeps a parent when a child matches", () => {
    const items = [{ label: "Modules", href: "modules.html", children: [{ label: "Radar", href: "group__radar.html", children: [] }] }];
    const out = filterSidebar(items, "radar");
    expect(out).toHaveLength(1);
    expect(out[0].children[0].label).toBe("Radar");
  });
  it("returns the tree when the query is empty", () => {
    const items = [{ label: "Home", href: "index.html", children: [] }];
    expect(filterSidebar(items, "")).toEqual(items);
  });
});

describe("flattenSidebarHrefs", () => {
  it("walks depth-first", () => {
    const items = [{ label: "A", href: "a.html", children: [{ label: "B", href: "b.html", children: [] }] }];
    expect(flattenSidebarHrefs(items).map((x) => x.href)).toEqual(["a.html", "b.html"]);
  });
});

describe("parseHtml extractTitle stripTitleAttributes extractToc", () => {
  it("reads a Doxygen title and strips title attributes", () => {
    const doc = parseHtml("<html><head><title>Radar</title></head><body><div class=\"title\">Radar Suite</div><h2 title=\"tip\">Overview</h2></body></html>");
    expect(extractTitle(doc)).toBe("Radar Suite");
    stripTitleAttributes(doc);
    expect(doc.querySelector("[title]")).toBeNull();
    const toc = extractToc(doc.body);
    expect(toc.some((item) => item.text === "Overview")).toBe(true);
  });
});

describe("dropUnsafeAttrs", () => {
  it("removes onclick and javascript: href", () => {
    const doc = parseHtml(
      '<html><body><a href="javascript:alert(1)" onclick="alert(1)">x</a></body></html>',
    );
    dropUnsafeAttrs(doc);
    const el = doc.querySelector("a");
    expect(el.hasAttribute("onclick")).toBe(false);
    expect(el.getAttribute("href")).toBeNull();
  });
});

describe("stills", () => {
  it("picks a still from the shared pack", () => {
    const still = pickStill();
    expect(F18_STILLS).toContain(still);
    expect(still.src).toMatch(/\/stills\/f18-/);
  });
});
