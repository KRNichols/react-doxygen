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
 * What: True when a href/src is a same-tree documentation relative path.
 * Why: Absolute, hash, mailto, and data URLs must not be rewritten onto /docs.
 * Who: rewriteAssetUrl and rewritePageHref before they map a URL.
 * Where: Client parse of proxied Doxygen HTML in the /docs reader.
 * How: Reject empty, hash, mailto, data, scheme, and protocol-relative strings.
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
 * What: Resolve a relative documentation URL against the current object path.
 * Why: Sibling and ../ links in Doxygen HTML must stay inside the tree.
 * Who: rewriteAssetUrl, rewritePageHref, and extractPrevNext.
 * Where: frontend/src/docsParse.js used by the /docs article pane.
 * How: Join against a fake https://docs.local/ base and return the pathname.
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
 * What: Point stylesheets, images, and fonts at the auth-gated docs proxy.
 * Why: The browser must never fetch Doxygen assets from a raw S3 URL.
 * Who: rewriteDocument when it walks [src] and link[href].
 * Where: Injected article HTML inside Docs.jsx.
 * How: Relative asset paths become /api/docs/<resolved>; pages stay untouched.
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
 * What: Map a Doxygen page link onto the SPA reader route, keeping hashes.
 * Why: In-article navigation must stay inside /docs, not bounce to Flask HTML.
 * Who: rewriteDocument for every a[href], plus extractPrevNext.
 * Where: Client rewrite of proxied Doxygen markup.
 * How: Relative .html paths become /docs/<file>#hash; assets go to /api/docs.
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
 * What: Remove Doxygen header, navtree, search, and footer chrome from a document.
 * Why: The portal reader supplies its own rails; leftover chrome duplicates them.
 * Who: extractBodyHtml after it clones the contents root.
 * Where: Scratch HTMLDocument built from the proxied page.
 * How: querySelectorAll each STRIP_SELECTORS entry and remove the matched nodes.
 */
export function stripDoxygenChrome(doc) {
  STRIP_SELECTORS.forEach((sel) => {
    doc.querySelectorAll(sel).forEach((node) => node.remove());
  });
  return doc;
}

/**
 * What: Inner HTML of the Doxygen article body with chrome and scripts removed.
 * Why: Docs.jsx injects that markup into the reader pane, not the full page.
 * Who: Docs loadPage after fetchDocHtml.
 * Where: frontend/src/docsParse.js, consumed only by the granted /docs route.
 * How: Clone .contents, strip chrome, rewrite URLs, drop title attrs and scripts.
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
 * What: Rewrite every href/src in a parsed document onto /docs or /api/docs.
 * Why: Injected markup must keep page clicks in the SPA and assets on the proxy.
 * Who: extractBodyHtml after chrome is stripped.
 * Where: Scratch document that becomes the article innerHTML.
 * How: a[href] uses rewritePageHref; [src] and link[href] use rewriteAssetUrl.
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
 * What: Drop title= attributes so Doxygen hover help cannot become a flyout.
 * Why: Product lock forbids title= tooltips on the reader surface.
 * Who: extractBodyHtml and the docsParse unit tests.
 * Where: Cloned article document before innerHTML is returned.
 * How: querySelectorAll [title] and removeAttribute on each match.
 */
export function stripTitleAttributes(doc) {
  doc.querySelectorAll("[title]").forEach((el) => el.removeAttribute("title"));
  return doc;
}

/**
 * What: Human title of a Doxygen page for the reader heading and tab.
 * Why: The article h1 should name the object, not the raw filename.
 * Who: Docs.jsx when a page finishes loading.
 * Where: Parsed HTML from GET /api/docs/<path>.
 * How: Prefer .headertitle .title, then .title, then h1, then <title>.
 */
export function extractTitle(doc) {
  const node = doc.querySelector(".headertitle .title") || doc.querySelector(".title") || doc.querySelector("h1");
  if (node && node.textContent.trim()) return node.textContent.trim();
  const t = (doc.querySelector("title") || {}).textContent || "";
  return t.replace(/\s*[—–-]\s*F\/A-18.*$/i, "").trim() || t.trim();
}

/**
 * What: Build an on-this-page list from heading elements in the article.
 * Why: The right rail needs stable ids to scroll to Overview/Safety sections.
 * Who: Docs.jsx after the body HTML is mounted.
 * Where: The injected article container, not the Doxygen navtree.
 * How: Walk h1–h3, mint a slug id when missing, return {id, text, level}.
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
 * What: Previous/next pager links from Doxygen rel=prev/next anchors.
 * Why: The reader footer should offer linear movement without the old navpath.
 * Who: Docs.jsx pager row under the article.
 * Where: The same parsed document as extractBodyHtml.
 * How: Prefer rel=prev/next, then .prev/.next, and rewrite each href.
 */
export function extractPrevNext(doc, currentPath) {
  /**
   * What: Read one prev/next candidate and rewrite its href for the SPA.
   * Why: extractPrevNext tries several selectors and needs one shared mapper.
   * Who: The prev and next fields returned to Docs.jsx.
   * Where: Inside extractPrevNext only.
   * How: Query the selector, rewrite the href, skip empty or hash-only links.
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
 * What: Deduplicated page links from Doxygen index/directory tables.
 * Why: Fallback sidebar when navtree.js is missing or unparseable.
 * Who: buildSidebar when flattenNavtree returns nothing.
 * Where: Parsed index.html / modules.html / annotated.html documents.
 * How: Collect .html anchors from known index selectors, skip repeats.
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
 * What: Parse the NAVTREE array assignment out of Doxygen navtree.js text.
 * Why: The left rail should reuse the generated tree instead of scraping HTML.
 * Who: Docs.jsx loadTree after fetchDocText("navtree.js").
 * Where: Client-side parse of the proxied JS file.
 * How: Regex the assignment, evaluate the array literal, return [] on failure.
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
 * What: Turn a nested NAVTREE array into {label, href, children, depth} nodes.
 * Why: React sidebar rendering needs objects, not Doxygen's [label, href, kids] tuples.
 * Who: buildSidebar, and tests that assert flattenNavtree labels.
 * Where: frontend/src/docsParse.js after parseNavtree succeeds.
 * How: Recurse the third slot; drop empty labels; preserve depth for indent.
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
 * What: Sidebar tree from NAVTREE, or grouped index links as a fallback.
 * Why: The left rail must list Modules/Classes/Files even without navtree.js.
 * Who: Docs.jsx after loadTree finishes.
 * Where: Client state that SidebarTree renders.
 * How: Prefer flattenNavtree; else bucket extractIndexLinks into four groups.
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
 * What: Filter a sidebar tree to nodes whose label (or a child) matches query.
 * Why: The reader search box should hide unrelated modules without a refetch.
 * Who: Docs.jsx when the toolbar query changes.
 * Where: visibleSidebar derived from the full tree.
 * How: Recurse children; keep a parent when it or any descendant matches.
 */
export function filterSidebar(items, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return items || [];
  /**
   * What: Recurse one sidebar level and keep matching nodes plus ancestors.
   * Why: A child hit must still show its Modules/Classes parent in the rail.
   * Who: filterSidebar after the query is normalized.
   * Where: Local walk closed over q.
   * How: Walk kids first; keep the node when its label or any child matches.
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
 * What: Wrap query matches in the article with mark.docs-hl, or clear old marks.
 * Why: In-page search needs visible hits without a Doxygen MSearch box.
 * Who: Docs.jsx after the article HTML mounts or the query changes.
 * Where: The injected article root only.
 * How: Unwrap existing marks, then TreeWalker text nodes and split on a regex.
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
     * What: Accept text nodes that contain the current highlight query.
     * Why: TreeWalker must skip script/style/mark so we do not nest marks.
     * Who: highlightText after it compiled the escaped regex.
     * Where: The article TreeWalker filter object.
     * How: Reject skipped parents; accept when the node text matches the regex.
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
 * What: Depth-first list of {href, label} from a sidebar tree.
 * Why: The article pager needs a linear order to compute prev/next.
 * Who: Docs.jsx resolvedPager.
 * Where: Flattened copy of the filtered or full sidebar.
 * How: Recurse children after pushing each node that has an href.
 */
export function flattenSidebarHrefs(items) {
  const out = [];
  /**
   * What: Push href-bearing nodes then recurse their children.
   * Why: flattenSidebarHrefs shares one walker instead of an inline loop.
   * Who: The exported flattenSidebarHrefs entry.
   * Where: Closed over the out array.
   * How: For each node, record href/label, then walk children depth-first.
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
 * What: Parse an HTML string into a document the other helpers can query.
 * Why: fetchDocHtml returns text; title/body/sidebar extractors need a DOM.
 * Who: Docs.jsx loaders and the docsParse tests.
 * Where: Browser or jsdom via DOMParser.
 * How: DOMParser parseFromString as text/html, empty string when missing.
 */
export function parseHtml(html) {
  return new DOMParser().parseFromString(html || "", "text/html");
}
