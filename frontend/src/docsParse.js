/**
 * Client-side Doxygen HTML helpers for the fancy reader.
 * Assets are rewritten to /api/docs/...; page links stay on /docs/...
 */

const ASSET_EXT = /\.(css|js|png|svg|gif|jpg|jpeg|woff2?|ico|map|md)(\?|#|$)/i;
const PAGE_EXT = /\.(html|md)(\?|#|$)/i;
const STRIP_SELECTORS = [
  "#top",
  "#nav-tree",
  "#side-nav",
  "#nav-path",
  "#navrow1",
  "#navrow2",
  "#navrow3",
  "#navrow4",
  "#nav-sync",
  "#MSearchBox",
  "#MSearchSelectWindow",
  "#MSearchResultsWindow",
  "div.navpath",
  "hr.footer",
  "address.footer",
  ".footer",
  "p.prev-next",
  ".prev-next",
];

/**
 * What: Decide whether a URL is a same-tree documentation asset or page.
 * Why: External links must stay external; S3 credentials never appear here.
 * Who: rewriteAssetUrl, rewritePageHref.
 * Where: href/src values inside proxied Doxygen HTML.
 * How: Reject blanks, hashes, mailto, and absolute http(s) off-origin.
 */
export function isDocRelative(url) {
  if (!url || typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("mailto:") || trimmed.startsWith("data:")) {
    return false;
  }
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed)) return false;
  if (trimmed.startsWith("//")) return false;
  return true;
}

/**
 * What: Resolve a relative URL against the current document path.
 * Why: Doxygen pages link to siblings (class_x.html) and same-folder images.
 * Who: rewrite helpers.
 * Where: Reader article pane after a /api/docs fetch.
 * How: URL() with a fake base, then drop leading slash / query-only noise.
 */
export function resolveAgainst(url, currentPath) {
  const basePath = currentPath && !currentPath.endsWith("/") ? currentPath : `${currentPath || "index.html"}`;
  const dir = basePath.includes("/") ? basePath.slice(0, basePath.lastIndexOf("/") + 1) : "";
  try {
    const resolved = new URL(url, `https://docs.local/${dir}`);
    return decodeURIComponent(resolved.pathname.replace(/^\//, ""));
  } catch {
    return url.replace(/^\.\//, "");
  }
}

/**
 * What: Point a relative asset at the auth-gated proxy.
 * Why: Images/CSS/fonts must not load from raw S3.
 * Who: rewriteDocument after parse.
 * Where: img/src, source, link[href], script[src] inside the article.
 * How: /api/docs/ + resolved relative path when the extension is an asset.
 */
export function rewriteAssetUrl(url, currentPath) {
  if (!isDocRelative(url)) return url;
  const resolved = resolveAgainst(url, currentPath);
  if (!ASSET_EXT.test(resolved) && !PAGE_EXT.test(resolved)) {
    return `/api/docs/${resolved}`;
  }
  if (ASSET_EXT.test(resolved)) return `/api/docs/${resolved}`;
  return url;
}

/**
 * What: Point a relative HTML page at the SPA reader route.
 * Why: Clicks should stay in the fancy chrome, not load stock Doxygen.
 * Who: rewriteDocument and extractPrevNext (via pick).
 * Where: <a href> inside the injected article.
 * How: /docs/ + resolved path; preserve hash fragments.
 */
export function rewritePageHref(url, currentPath) {
  if (!url) return url;
  if (url.startsWith("#")) return url;
  if (!isDocRelative(url)) return url;
  const hashIndex = url.indexOf("#");
  const hash = hashIndex >= 0 ? url.slice(hashIndex) : "";
  const withoutHash = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
  const resolved = resolveAgainst(withoutHash || currentPath || "index.html", currentPath);
  if (PAGE_EXT.test(resolved) || resolved.endsWith("/")) {
    return `/docs/${resolved}${hash}`;
  }
  if (ASSET_EXT.test(resolved)) return `/api/docs/${resolved}`;
  return `/docs/${resolved}${hash}`;
}

/**
 * What: Remove Doxygen's own header, tabs, search, and footer from a document.
 * Why: The portal supplies BDS chrome; stock Doxygen chrome must not appear.
 * Who: extractBodyHtml.
 * Where: Parsed HTMLDocument from /api/docs/*.html.
 * How: querySelectorAll(STRIP_SELECTORS) and remove each node.
 */
export function stripDoxygenChrome(doc) {
  STRIP_SELECTORS.forEach((sel) => {
    doc.querySelectorAll(sel).forEach((node) => node.remove());
  });
  return doc;
}

/**
 * What: Pull the inner HTML of the Doxygen article body.
 * Why: Only the contents pane is injected into the reader.
 * Who: Docs.loadPage after fetchDocHtml.
 * Where: #doc-content .contents, .contents, #doc-content, else body.
 * How: Clone the best node, strip chrome, rewrite urls, drop scripts.
 */
export function extractBodyHtml(doc, currentPath) {
  const root =
    doc.querySelector("#doc-content .contents") ||
    doc.querySelector(".contents") ||
    doc.querySelector("#doc-content") ||
    doc.querySelector("body");
  if (!root) return "";
  const clone = root.cloneNode(true);
  const scratch = document.implementation.createHTMLDocument("");
  scratch.body.appendChild(clone);
  stripDoxygenChrome(scratch);
  rewriteDocument(scratch, currentPath);
  stripTitleAttributes(scratch);
  scratch.querySelectorAll("script").forEach((n) => n.remove());
  return scratch.body.innerHTML;
}

/**
 * What: Rewrite every relative href/src in a parsed document.
 * Why: Injected markup must fetch via /api/docs and navigate via /docs.
 * Who: extractBodyHtml.
 * Where: a, img, source, video, link, script nodes.
 * How: rewritePageHref for anchors; rewriteAssetUrl for everything else.
 */
export function rewriteDocument(doc, currentPath) {
  doc.querySelectorAll("a[href]").forEach((el) => {
    el.setAttribute("href", rewritePageHref(el.getAttribute("href"), currentPath));
  });
  doc.querySelectorAll("[src]").forEach((el) => {
    el.setAttribute("src", rewriteAssetUrl(el.getAttribute("src"), currentPath));
  });
  doc.querySelectorAll("link[href]").forEach((el) => {
    el.setAttribute("href", rewriteAssetUrl(el.getAttribute("href"), currentPath));
  });
  return doc;
}


/**
 * What: Remove title attributes from injected Doxygen markup.
 * Why: Native browser tooltips read as flyouts and fail the no-hover-help brief.
 * Who: extractBodyHtml after rewriteDocument.
 * Where: Every element in the cloned article document.
 * How: Walk every [title] node on the clone and drop the attribute so hover cannot open a native tooltip.
 */
export function stripTitleAttributes(doc) {
  doc.querySelectorAll("[title]").forEach((el) => el.removeAttribute("title"));
  return doc;
}

/**
 * What: Read a human title from a Doxygen page.
 * Why: The article heading and document.title should match the page.
 * Who: Docs.loadPage.
 * Where: .title, h1, or <title>.
 * How: First non-empty text content among those selectors.
 */
export function extractTitle(doc) {
  const node = doc.querySelector(".headertitle .title") || doc.querySelector(".title") || doc.querySelector("h1");
  if (node && node.textContent.trim()) return node.textContent.trim();
  const t = (doc.querySelector("title") || {}).textContent || "";
  return t.replace(/\s*[—–-]\s*F\/A-18.*$/i, "").trim() || t.trim();
}

/**
 * What: Build a right-rail TOC from h1–h3 in the article.
 * Why: Long Doxygen pages need in-page jump links.
 * Who: Docs page after HTML injection.
 * Where: Headings inside the extracted body (or the original document).
 * How: Assign ids when missing; return {id, text, level}[].
 */
export function extractToc(container) {
  if (!container) return [];
  const nodes = container.querySelectorAll("h1, h2, h3");
  const items = [];
  nodes.forEach((el, i) => {
    const text = (el.textContent || "").trim();
    if (!text) return;
    if (!el.id) {
      el.id = `toc-${i}-${text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "s"}`;
    }
    items.push({ id: el.id, text, level: Number(el.tagName[1]) });
  });
  return items;
}

/**
 * What: Find prev/next links on a Doxygen page.
 * Why: The reader shows pager controls when the tree or page provides them.
 * Who: Docs.loadPage; fallback is sidebar order in Docs.jsx.
 * Where: rel=prev/next, .prev/.next, or .prev-next anchors.
 * How: Collect href+label pairs after rewritePageHref.
 */
export function extractPrevNext(doc, currentPath) {
  /**
   * What: Pull one prev/next anchor into {href, label} or null.
   * Why: Doxygen marks pager links with rel=prev/next or .prev/.next classes.
   * Who: extractPrevNext for the prev and next slots.
   * Where: Parsed Doxygen HTMLDocument after rewritePageHref.
   * How: querySelector the selector, rewrite the href, skip missing or hash-only anchors.
   */
  const pick = (sel) => {
    const el = doc.querySelector(sel);
    if (!el) return null;
    const href = rewritePageHref(el.getAttribute("href") || "", currentPath);
    const label = (el.textContent || "").trim();
    if (!href || href.startsWith("#")) return null;
    return { href, label };
  };
  return {
    prev: pick("a[rel='prev']") || pick("a.prev"),
    next: pick("a[rel='next']") || pick("a.next"),
  };
}

/**
 * What: Collect module/class/file links from a Doxygen index-like page.
 * Why: Fallback sidebar when navtree.js is missing.
 * Who: buildSidebar.
 * Where: #navrow1, .tablist, .directory a, .contents a[href$=.html].
 * How: Unique href/label pairs that look like documentation pages.
 */
export function extractIndexLinks(doc) {
  const seen = new Set();
  const items = [];
  const nodes = doc.querySelectorAll("#navrow1 a, .tablist a, .directory a, .memberdecls a, .contents a");
  nodes.forEach((el) => {
    const href = el.getAttribute("href") || "";
    const label = (el.textContent || "").replace(/\s+/g, " ").trim();
    if (!label || !PAGE_EXT.test(href.split("#")[0])) return;
    const path = href.split("#")[0];
    if (seen.has(path)) return;
    seen.add(path);
    items.push({ href: path, label, children: [] });
  });
  return items;
}

/**
 * What: Parse Doxygen navtree.js into a nested array.
 * Why: navtree is the richest module/class/file outline when present.
 * Who: buildSidebar after fetch /api/docs/navtree.js.
 * Where: `var NAVTREE = [ ... ];`
 * How: Slice the assignment and evaluate as a JS expression (our own proxy).
 */
export function parseNavtree(text) {
  if (!text) return [];
  const match = text.match(/var\s+NAVTREE\s*=\s*(\[[\s\S]*?\]);/);
  if (!match) return [];
  try {
    const fn = new Function(`"use strict"; return (${match[1]});`);
    const tree = fn();
    return Array.isArray(tree) ? tree : [];
  } catch {
    return [];
  }
}

/**
 * What: Convert a NAVTREE node list into sidebar items.
 * Why: The left rail needs label, href, and optional children.
 * Who: buildSidebar.
 * Where: Parsed navtree.js arrays of [label, url, children|id|null].
 * How: Recurse; skip empty urls; treat string third slots as no children.
 */
export function flattenNavtree(tree, depth = 0) {
  if (!Array.isArray(tree)) return [];
  return tree
    .map((node) => {
      if (!Array.isArray(node) || !node.length) return null;
      const label = String(node[0] || "").trim();
      const href = typeof node[1] === "string" ? node[1] : "";
      const third = node[2];
      const children = Array.isArray(third) ? flattenNavtree(third, depth + 1) : [];
      if (!label) return null;
      return { label, href, children, depth };
    })
    .filter(Boolean);
}

/**
 * What: Build the left-rail tree from navtree, else from index.html links.
 * Why: Real Doxygen exports vary; the reader should still have a sidebar.
 * Who: Docs.jsx on first load.
 * Where: navtree.js plus the proxied index document.
 * How: Prefer flattenNavtree; group leftover index links by filename.
 */
export function buildSidebar(navtree, indexDoc) {
  const fromTree = flattenNavtree(navtree);
  if (fromTree.length) {
    if (fromTree.length === 1 && fromTree[0].children && fromTree[0].children.length) {
      return fromTree[0].children;
    }
    return fromTree;
  }
  const links = indexDoc ? extractIndexLinks(indexDoc) : [];
  const groups = { Modules: [], Classes: [], Files: [], Pages: [] };
  links.forEach((item) => {
    const h = item.href;
    if (/^group_/.test(h) || h === "modules.html") groups.Modules.push(item);
    else if (/^class_/.test(h) || h === "annotated.html") groups.Classes.push(item);
    else if (/_8h\.html$/.test(h) || h === "files.html") groups.Files.push(item);
    else groups.Pages.push(item);
  });
  return Object.entries(groups)
    .filter(([, kids]) => kids.length)
    .map(([label, children]) => ({ label, href: children[0]?.href || "", children }));
}

/**
 * What: Filter sidebar items by a case-insensitive query.
 * Why: In-reader search should shrink the outline as the user types.
 * Who: Docs.jsx search box.
 * Where: Client-side only; no extra API.
 * How: Keep a node if its label or any descendant matches.
 */
export function filterSidebar(items, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return items || [];
  /**
   * What: Recurse the sidebar tree keeping nodes that match the query.
   * Why: A parent must stay visible when only a descendant matches.
   * Who: filterSidebar after the query is non-empty.
   * Where: Client-side outline; no extra API.
   * How: Depth-first: keep a node if its label matches or any child is kept.
   */
  const walk = (nodes) => {
    const out = [];
    (nodes || []).forEach((node) => {
      const kids = walk(node.children || []);
      if ((node.label || "").toLowerCase().includes(q) || kids.length) {
        out.push({ ...node, children: kids });
      }
    });
    return out;
  };
  return walk(items);
}

/**
 * What: Wrap query matches in <mark class="docs-hl"> inside an element.
 * Why: Search should highlight hits in the article as well as the sidebar.
 * Who: Docs.jsx when the search box is non-empty.
 * Where: Text nodes under the article root (skip script/style).
 * How: Split text nodes with a case-insensitive RegExp; honor empty query.
 */
export function highlightText(root, query) {
  if (!root) return;
  const marks = root.querySelectorAll("mark.docs-hl");
  marks.forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    parent.replaceChild(document.createTextNode(mark.textContent), mark);
    parent.normalize();
  });
  const q = (query || "").trim();
  if (!q) return;
  let escaped = "";
  for (const ch of q) {
    escaped += /[.*+?^${}()|[\]\\]/.test(ch) ? `\\${ch}` : ch;
  }
  const re = new RegExp(escaped, "gi");
  const skip = new Set(["SCRIPT", "STYLE", "MARK"]);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    /**
     * What: TreeWalker filter that accepts text nodes containing the query.
     * Why: highlightText must skip script/style/mark and empty text.
     * Who: document.createTreeWalker inside highlightText.
     * Where: Text nodes under the article root.
     * How: Reject skipped parents; accept when the case-insensitive regexp hits.
     */
    acceptNode(node) {
      const p = node.parentElement;
      if (!p || skip.has(p.tagName)) return NodeFilter.FILTER_REJECT;
      return node.textContent && re.test(node.textContent)
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT;
    },
  });
  const nodes = [];
  let n = walker.nextNode();
  while (n) {
    nodes.push(n);
    n = walker.nextNode();
  }
  nodes.forEach((node) => {
    const text = node.textContent;
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m = re.exec(text);
    while (m) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const mark = document.createElement("mark");
      mark.className = "docs-hl";
      mark.textContent = m[0];
      frag.appendChild(mark);
      last = m.index + m[0].length;
      m = re.exec(text);
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  });
}

/**
 * What: Flatten sidebar items into a prev/next sequence.
 * Why: Pager fallback when the HTML has no rel=prev/next.
 * Who: Docs.jsx pager.
 * Where: Visible sidebar tree (unfiltered).
 * How: Depth-first push of nodes that have an href.
 */
export function flattenSidebarHrefs(items) {
  const out = [];
  /**
   * What: Depth-first collect of sidebar nodes that have an href.
   * Why: The pager needs a linear order matching the visible tree.
   * Who: flattenSidebarHrefs.
   * Where: Unfiltered sidebar items.
   * How: Pre-order visit: emit the node when it has a page href, then walk its children.
   */
  const walk = (nodes) => {
    (nodes || []).forEach((node) => {
      if (node.href) out.push({ href: node.href, label: node.label });
      walk(node.children);
    });
  };
  walk(items);
  return out;
}

/**
 * What: Parse a fetched HTML string into a document.
 * Why: DOMParser is the only safe way to query Doxygen structure.
 * Who: Docs.loadPage and Docs.loadTree.
 * Where: Browser; string from /api/docs/*.html.
 * How: Feed the fetched markup into the browser HTML parser so extractors can querySelector.
 */
export function parseHtml(html) {
  return new DOMParser().parseFromString(html || "", "text/html");
}
