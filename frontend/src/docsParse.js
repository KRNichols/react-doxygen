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

export function rewriteAssetUrl(url, currentPath) {
  if (!isDocRelative(url)) return url;
  const resolved = resolveAgainst(url, currentPath);
  if (!ASSET_EXT.test(resolved) && !PAGE_EXT.test(resolved)) {
    return `/api/docs/${resolved}`;
  }
  if (ASSET_EXT.test(resolved)) return `/api/docs/${resolved}`;
  return url;
}

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

export function stripDoxygenChrome(doc) {
  STRIP_SELECTORS.forEach((sel) => {
    doc.querySelectorAll(sel).forEach((node) => node.remove());
  });
  return doc;
}

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

export function stripTitleAttributes(doc) {
  doc.querySelectorAll("[title]").forEach((el) => el.removeAttribute("title"));
  return doc;
}

export function extractTitle(doc) {
  const node = doc.querySelector(".headertitle .title") || doc.querySelector(".title") || doc.querySelector("h1");
  if (node && node.textContent.trim()) return node.textContent.trim();
  const t = (doc.querySelector("title") || {}).textContent || "";
  return t.replace(/\s*[—–-]\s*F\/A-18.*$/i, "").trim() || t.trim();
}

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

export function extractPrevNext(doc, currentPath) {
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

export function filterSidebar(items, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return items || [];
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

export function flattenSidebarHrefs(items) {
  const out = [];
  const walk = (nodes) => {
    (nodes || []).forEach((node) => {
      if (node.href) out.push({ href: node.href, label: node.label });
      walk(node.children);
    });
  };
  walk(items);
  return out;
}

export function parseHtml(html) {
  return new DOMParser().parseFromString(html || "", "text/html");
}
