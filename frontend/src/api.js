const jsonHeaders = { "Content-Type": "application/json", Accept: "application/json" };

/**
 * What: Parse a fetch Response as JSON and throw on HTTP errors.
 * Why: Every portal API helper needs the same {error} → Error mapping.
 * Who: login, logout, me, signup, copy, docsMeta.
 * Where: SPA calls to /api/* (Vite proxy in dev).
 * How: res.json(); if !ok raise Error with status and body.
 */
async function read(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || res.statusText || "Request failed");
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}

/**
 * What: POST demo credentials to the mock IdP and complete login in one hop.
 * Why: The login card’s demo-account path skips the hosted HTML page.
 * Who: Login.onSubmit.
 * Where: POST /api/auth/mock/okta JSON {email, password}.
 * How: fetch + read; session cookie is set by Flask.
 */
export function login(email, password) {
  return fetch("/api/auth/mock/okta", {
    method: "POST",
    credentials: "include",
    headers: jsonHeaders,
    body: JSON.stringify({ email, password }),
  }).then(read);
}

/**
 * What: End the portal session.
 * Why: Success “Sign out” must clear the httpOnly cookie.
 * Who: Success.onLogout.
 * Where: POST /api/auth/logout.
 * How: fetch + read; server clears the session.
 */
export function logout() {
  return fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
  }).then(read);
}

/**
 * What: Current session user (email, name, callsign, clearance).
 * Why: Success/Denied pick the right scene from clearance.
 * Who: Success and Denied effects.
 * Where: GET /api/auth/me; 401 if signed out.
 * How: fetch + read with credentials.
 */
export function me() {
  return fetch("/api/auth/me", {
    credentials: "include",
    headers: { Accept: "application/json" },
  }).then(read);
}

/**
 * What: Submit a request-access form.
 * Why: Visitors without an account notify SIGNUP_NOTIFY_EMAIL.
 * Who: Signup.onSubmit.
 * Where: POST /api/auth/signup JSON {name, email, organization}.
 * How: fetch + read; server writes mailbox and optional SMTP.
 */
export function signup({ name, email, organization }) {
  return fetch("/api/auth/signup", {
    method: "POST",
    credentials: "include",
    headers: jsonHeaders,
    body: JSON.stringify({ name, email, organization }),
  }).then(read);
}

/**
 * What: Merged user-facing copy plus notifyEmail.
 * Why: Every branded page reads strings from the backend, not hardcoded JSX.
 * Who: CopyProvider / useCopy.
 * Where: GET /api/copy (copy.json + COPY_* env).
 * How: fetch + read.
 */
export function copy() {
  return fetch("/api/copy", {
    credentials: "include",
    headers: { Accept: "application/json" },
  }).then(read);
}


/**
 * What: Read documentation source metadata for a granted session.
 * Why: The reader labels the tree and can show a mock notice.
 * Who: Docs.jsx after login clearance is granted.
 * Where: GET /api/docs/meta (session cookie).
 * How: Same JSON read() helper as the other API calls.
 */
export function docsMeta() {
  return fetch("/api/docs/meta", {
    credentials: "include",
    headers: { Accept: "application/json" },
  }).then(read);
}

/**
 * What: Fetch a documentation object as text (HTML or JS).
 * Why: The reader parses HTML/navtree locally; it must see 401/403 status.
 * Who: Docs.jsx page and sidebar loaders.
 * Where: GET /api/docs/<path> with credentials.
 * How: Throw an Error with .status when the response is not ok.
 */
export async function fetchDocText(path) {
  const clean = String(path || "index.html").replace(/^\/+/, "");
  const res = await fetch(`/api/docs/${clean}`, { credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.error || res.statusText || "Request failed");
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return res.text();
}

/**
 * What: Fetch a Doxygen HTML page through the auth proxy.
 * Why: Alias used by the article pane so call sites stay obvious.
 * Who: Docs.jsx loadPage / loadTree.
 * Where: Same as fetchDocText.
 * How: Delegate to fetchDocText.
 */
export function fetchDocHtml(path) {
  return fetchDocText(path);
}
