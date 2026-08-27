import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import BrandHeader from "../components/BrandHeader.jsx";
import { useCopy } from "../copy.jsx";
import { docsMeta, fetchDocHtml, fetchDocText, logout, me } from "../api.js";
import {
  buildSidebar,
  extractBodyHtml,
  extractPrevNext,
  extractTitle,
  extractToc,
  filterSidebar,
  flattenSidebarHrefs,
  highlightText,
  parseHtml,
  parseNavtree,
} from "../docsParse.js";
import "./Docs.css";

/**
 * What: Normalize a /docs/* splat into a Doxygen object path.
 * Why: /docs and /docs/ must load index.html; deep links keep their file.
 * Who: Docs page when reading useParams / location.
 * Where: Frontend route /docs and /docs/*.
 * How: Strip leading slashes; default to index.html.
 */
function docPathFromRoute(splat) {
  const raw = (splat || "").replace(/^\/+/, "");
  return raw || "index.html";
}

/**
 * What: Compare a sidebar href to the active document path.
 * Why: The left rail highlights the page the user is reading.
 * Who: SidebarTree (is-active) and resolvedPager (findIndex).
 * Where: Client-side navigation state.
 * How: Strip a leading /docs/ and any hash, then compare the remaining paths for exact equality.
 */
function sameDoc(href, current) {
  if (!href || !current) return false;
  const a = href.replace(/^\/docs\//, "").split("#")[0];
  const b = current.replace(/^\/docs\//, "").split("#")[0];
  return a === b;
}

/**
 * What: Count href-bearing nodes in a filtered sidebar tree.
 * Why: Search needs an aria-live result count, not a silent filter.
 * Who: Docs toolbar when query is non-empty.
 * Where: visibleSidebar after filterSidebar.
 * How: Recurse children; count items that have an href.
 */
function countSidebar(items) {
  if (!items || !items.length) return 0;
  let n = 0;
  for (const item of items) {
    if (item.href) n += 1;
    n += countSidebar(item.children);
  }
  return n;
}

/**
 * What: Demote Doxygen body h1 tags so the reader has a single page heading.
 * Why: docs-page-title is the article h1; a second h1 fails 1.3.1.
 * Who: Docs article inject.
 * Where: extractBodyHtml output before dangerouslySetInnerHTML.
 * How: Replace heading-one tags with heading-two, case-insensitive.
 */
function demoteProseH1(html) {
  const src = String(html || "");
  return src.split("<h1").join("<h2").split("</h1>").join("</h2>");
}

/**
 * What: Recursively render a sidebar tree with active highlighting.
 * Why: Modules/classes/files nest; the rail must keep that shape.
 * Who: Docs left column.
 * Where: items from buildSidebar, already filterSidebar'd.
 * How: <ul> of Links to /docs/<href>; is-active when sameDoc.
 */
function SidebarTree({ items, current }) {
  if (!items || !items.length) return null;
  return (
    <ul className="docs-nav">
      {items.map((item) => {
        const href = item.href ? `/docs/${item.href.replace(/^\/docs\//, "")}` : "";
        const active = sameDoc(item.href, current);
        return (
          <li key={`${item.label}-${item.href}`}>
            {href ? (
              <Link className={active ? "is-active" : ""} to={href} aria-current={active ? "page" : undefined}>
                {item.label}
              </Link>
            ) : (
              <span>{item.label}</span>
            )}
            <SidebarTree items={item.children} current={current} />
          </li>
        );
      })}
    </ul>
  );
}

/**
 * What: Auth-gated Doxygen reader for granted sessions only.
 * Why: Program docs must never render for denied or logged-out users.
 * Who: Routes /docs and /docs/*.
 * Where: Fetches /api/docs/* with the session cookie; BDS header, no footer columns.
 * How: me() gate, proxy HTML, strip Doxygen chrome, inject article, client search.
 */
export default function Docs() {
  const copy = useCopy();
  const c = copy.docs || {};
  const brand = copy.brand || {};
  const nav = useNavigate();
  const location = useLocation();
  const params = useParams();
  const docPath = docPathFromRoute(params["*"]);
  const articleRef = useRef(null);

  const [user, setUser] = useState(null);
  const [meta, setMeta] = useState(null);
  const [sidebar, setSidebar] = useState([]);
  const [html, setHtml] = useState("");
  const [title, setTitle] = useState("");
  const [toc, setToc] = useState([]);
  const [pager, setPager] = useState({ prev: null, next: null });
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  /**
   * What: Gate the reader to granted sessions only.
   * Why: Denied and anonymous users must never see proxied Doxygen HTML.
   * Who: Docs mount.
   * Where: GET /api/auth/me then stay on /docs or bounce.
   * How: clearance !== granted → /denied; 401 → /.
   */
  useEffect(() => {
    let cancelled = false;
    me()
      .then((data) => {
        if (cancelled) return;
        if (data.clearance !== "granted") {
          nav("/denied", { replace: true });
          return;
        }
        setUser(data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) nav("/", { replace: true });
        else if (err.status === 403) nav("/denied", { replace: true });
        else nav("/", { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [nav]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;

    /**
     * What: Load navtree/index once so the left rail can list the tree.
     * Why: Sidebar should not refetch on every in-reader navigation.
     * Who: Granted Docs session after me() succeeds.
     * Where: /api/docs/meta, navtree.js, index.html.
     * How: Parallel fetch; buildSidebar from navtree or index links.
     */
    async function loadTree() {
      try {
        const [m, indexHtml, navText] = await Promise.all([
          docsMeta(),
          fetchDocHtml("index.html"),
          fetchDocText("navtree.js").catch(() => ""),
        ]);
        if (cancelled) return;
        setMeta(m);
        const indexDoc = parseHtml(indexHtml);
        const tree = parseNavtree(navText);
        setSidebar(buildSidebar(tree, indexDoc));
      } catch (err) {
        if (cancelled) return;
        if (err.status === 401) nav("/", { replace: true });
        else if (err.status === 403) nav("/denied", { replace: true });
      }
    }

    loadTree();
    return () => {
      cancelled = true;
    };
  }, [user, nav]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;

    /**
     * What: Fetch one Doxygen page and inject its stripped body.
     * Why: Each /docs/* route should show that object's article, not an iframe.
     * Who: Docs when docPath changes.
     * Where: GET /api/docs/<path> (credentials included).
     * How: parseHtml, extractBodyHtml/title/prev-next; 401/403 bounce.
     */
    async function loadPage() {
      setLoading(true);
      try {
        const raw = await fetchDocHtml(docPath);
        if (cancelled) return;
        const doc = parseHtml(raw);
        setTitle(extractTitle(doc));
        setHtml(extractBodyHtml(doc, docPath));
        setPager(extractPrevNext(doc, docPath));
      } catch (err) {
        if (cancelled) return;
        if (err.status === 401) nav("/", { replace: true });
        else if (err.status === 403) nav("/denied", { replace: true });
        else setHtml(`<p>${(c.empty || "No documentation is available.")}</p>`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadPage();
    return () => {
      cancelled = true;
    };
  }, [user, docPath, nav]);

  useEffect(() => {
    const root = articleRef.current;
    if (!root) return;
    setToc(extractToc(root));
    highlightText(root, query);
  }, [html, query]);

  const visibleSidebar = useMemo(() => filterSidebar(sidebar, query), [sidebar, query]);

  const resolvedPager = useMemo(() => {
    if (pager.prev || pager.next) return pager;
    const flat = flattenSidebarHrefs(sidebar);
    const idx = flat.findIndex((item) => sameDoc(item.href, docPath));
    if (idx < 0) return { prev: null, next: null };
    /**
     * What: Turn a flattened sidebar node into a pager {href, label}.
     * Why: Sidebar hrefs are bare filenames; the Link needs a /docs/ route.
     * Who: resolvedPager when HTML has no rel=prev/next.
     * Where: Docs article pager under the injected body.
     * How: Prefix /docs/ once and keep the label; null stays null.
     */
    const wrap = (item) =>
      item ? { href: `/docs/${item.href.replace(/^\/docs\//, "")}`, label: item.label } : null;
    return { prev: wrap(flat[idx - 1]), next: wrap(flat[idx + 1]) };
  }, [pager, sidebar, docPath]);

  /**
   * What: End the session from the reader toolbar.
   * Why: The chrome-free header has no Menu; sign-out still has to live somewhere.
   * Who: Toolbar Sign out control on /docs.
   * Where: POST /api/auth/logout then /logged-out.
   * How: logout() ignore errors, then navigate.
   */
  async function onLogout() {
    await logout().catch(() => {});
    nav("/logged-out");
  }

  /**
   * What: Intercept in-article link clicks so HTML pages stay in the reader.
   * Why: Rewritten hrefs are /docs/... but hash links should scroll locally.
   * Who: Article pane onClick.
   * Where: Injected Doxygen body.
   * How: preventDefault for /docs paths; let /api/docs assets download.
   */
  function onArticleClick(event) {
    const a = event.target.closest("a");
    if (!a || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey) return;
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) {
      event.preventDefault();
      const id = decodeURIComponent(href.slice(1));
      const el = articleRef.current?.querySelector(`[id="${CSS.escape(id)}"]`);
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      return;
    }
    if (href.startsWith("/docs/")) {
      event.preventDefault();
      nav(href);
    }
  }

  const pageTitle = title || meta?.title || (c.title || "F/A-18 Mission Software");

  useEffect(() => {
    if (pageTitle) document.title = `${pageTitle} | Boeing`;
  }, [pageTitle]);

  return (
    <div className="docs-stage">
      <a className="skip-link" href="#docs-article">
        {(brand.skipLink || "Skip to content")}
      </a>
      <BrandHeader />
      <div className="docs-toolbar">
        <span className="docs-toolbar-title">{meta?.title || (c.title || "F/A-18 Mission Software")}</span>
        <label className="docs-search" htmlFor="docs-search">
          <span className="sr-only">{(c.searchLabel || "Search documentation")}</span>
          <input
            id="docs-search"
            name="q"
            type="search"
            autoComplete="off"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={(c.searchPlaceholder || "Search this document")}
          />
        </label>
        <p className="sr-only" aria-live="polite">
          {query ? (countSidebar(visibleSidebar) ? (countSidebar(visibleSidebar) + " matching pages") : (c.empty || "No matching pages")) : ""}
        </p>
        <button className="docs-signout" type="button" onClick={onLogout}>
          {(c.signOut || "Sign out")}
        </button>
      </div>
      <div className="docs-shell">
        <aside className="docs-sidebar" aria-label={(c.sidebarTitle || "Contents")}>
          <p className="docs-rail-title">{(c.sidebarTitle || "Contents")}</p>
          <SidebarTree items={visibleSidebar} current={docPath} />
        </aside>
        <main id="docs-article" className="docs-article" tabIndex={-1} onClick={onArticleClick}>
          {loading ? (
            <p className="docs-status" aria-live="polite">{(c.loading || "Loading documentation…")}</p>
          ) : (
            <div className="docs-article-inner" key={location.pathname}>
              {meta && !meta.configured ? (
                <p className="docs-note">{(c.mockNote || "Using local mock documentation.")}</p>
              ) : null}
              {title ? <h1 className="docs-page-title">{title}</h1> : null}
              <div
                ref={articleRef}
                className="docs-prose"
                dangerouslySetInnerHTML={{ __html: demoteProseH1(html) }}
              />
              <nav className="docs-pager" aria-label="Page">
                {resolvedPager.prev ? (
                  <Link to={resolvedPager.prev.href}>
                    ← {(c.prev || "Previous")}: {resolvedPager.prev.label}
                  </Link>
                ) : (
                  <span className="is-disabled" />
                )}
                {resolvedPager.next ? (
                  <Link to={resolvedPager.next.href}>
                    {(c.next || "Next")}: {resolvedPager.next.label} →
                  </Link>
                ) : (
                  <span className="is-disabled" />
                )}
              </nav>
            </div>
          )}
        </main>
        <aside className="docs-toc" aria-label={(c.tocTitle || "On this page")}>
          <p className="docs-rail-title">{(c.tocTitle || "On this page")}</p>
          {toc.map((item) => (
            <a key={item.id} className={`lvl-${item.level}`} href={`#${item.id}`}>
              {item.text}
            </a>
          ))}
        </aside>
      </div>
    </div>
  );
}
