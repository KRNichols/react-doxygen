# Portal API

This document describes every `/api` route as implemented in `backend/app.py`,
`backend/doxygen.py`, and `backend/signup_mail.py`. Fields and status codes
below are taken from those handlers. Nothing here is speculative.

The React SPA talks to these routes through the Vite `/api` proxy in
development (`frontend/src/api.js`). Flask also serves the built SPA from
`frontend/dist` when that directory exists.

## Session cookie

The portal session is the Flask cookie named `f18_session`.

| Property | Value |
|---|---|
| Name | `f18_session` |
| HttpOnly | yes |
| SameSite | `Lax` |
| Secure | no (this demo) |
| Lifetime | 8 hours (`PERMANENT_SESSION_LIFETIME`) after a successful login |
| Signed with | `FLASK_SECRET` |

`_set_session` stores `{email, name, callsign, clearance}` in the cookie
session. `_session_user` treats the request as anonymous unless that value is
a dict with an `email`. CORS for `/api/*` allows
`http://localhost:5173` and `http://127.0.0.1:5173` with credentials.

Send the cookie on authenticated calls (`credentials: include` from the SPA).
JSON error bodies are `{ "error": "<message>" }`. When the client does not
ask for JSON (`Accept` prefers HTML, and the body is not JSON), some OAuth
helpers return the same message as plain text instead.

## Demo accounts

| Email | Password | `clearance` | After login |
|---|---|---|---|
| `f18.pilot@boeing.com` | `HornetReady1` | `granted` | session set; JSON `redirect` is `/docs` |
| `visitor@example.com` | `NoClearance` | `denied` | session set; JSON `redirect` is `/denied` |

Wrong password: HTTP **401**, `{ "error": "Invalid email or password." }`, no
session. Denied is a **completed** login (HTTP **200** + cookie), not 401.

## Granted vs denied vs 401 vs docs 403

| Situation | Typical status | Body |
|---|---|---|
| No `f18_session` (or session has no `email`) on `/api/auth/me` or `/api/docs/*` | **401** | `{ "error": "Not authenticated." }` |
| Bad email/password on `POST /api/auth/mock/okta` (JSON) | **401** | `{ "error": "Invalid email or password." }` |
| Granted login (`f18.pilot@boeing.com`) | **200** | session cookie; `clearance` is `granted` |
| Denied login (`visitor@example.com`) | **200** | session cookie; `clearance` is `denied` |
| `GET /api/auth/me` with a denied session | **200** | `{ ..., "clearance": "denied" }` |
| `GET /api/docs/meta` or `GET /api/docs/<path>` with a denied session | **403** | `{ "error": "Not authorized." }` |
| Same docs routes with a granted session | **200** (or 400/404/502 on path/source errors) | meta JSON or document bytes |

Public routes that do **not** require a session: `/api/health`, `/api/copy`,
`/api/auth/login`, `/api/auth/mock/okta`, `/api/auth/callback`,
`/api/auth/logout`, `/api/auth/signup`, `/api/auth/signup/config`, and
(development only) `/api/auth/signup/mailbox`.

---

## `GET /api/health`

- **WHAT:** Liveness payload: `ok`, which IdP, issuer.
- **WHY:** Operators and the frontend can confirm Flask is up.
- **WHO:** Operators curling the process; any client that checks liveness.
- **WHERE:** Always public. No session required.
- **HOW:** `idp` is `mock` when `OKTA_ISSUER` is empty, otherwise `okta`.

**Method:** `GET`  
**Auth:** none  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **200** | Flask handled the request |

### Response JSON (200)

```json
{
  "ok": true,
  "idp": "mock",
  "issuer": null
}
```

| Field | Type | Source |
|---|---|---|
| `ok` | boolean | always `true` |
| `idp` | string | `"mock"` or `"okta"` |
| `issuer` | string or `null` | `OKTA_ISSUER` when set; otherwise `null` |

---

## `GET /api/copy`

- **WHAT:** Public JSON of merged user-facing strings plus `notifyEmail`.
- **WHY:** The SPA renders configurable copy without a frontend rebuild.
- **WHO:** `frontend` `api.copy` / `CopyProvider`; operators curling `/api/copy`.
- **WHERE:** Unauthenticated. Vite proxies it in development.
- **HOW:** `get_copy()` (`backend/copy.json` + `COPY_*` env, mtime cache) then
  attach `notify_address()`.

**Method:** `GET`  
**Auth:** none  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **200** | Catalog loaded (empty object if the copy file is missing) |

### Response JSON (200)

The body is the merged copy catalog plus one handler-added key:

| Field | Type | Source |
|---|---|---|
| `brand` | object | `copy.json` / `COPY_*` |
| `login` | object | `copy.json` / `COPY_*` |
| `signup` | object | `copy.json` / `COPY_*` |
| `signupSent` | object | `copy.json` / `COPY_*` |
| `success` | object | `copy.json` / `COPY_*` |
| `denied` | object | `copy.json` / `COPY_*` |
| `loggedOut` | object | `copy.json` / `COPY_*` |
| `email` | object | `copy.json` / `COPY_*` |
| `docs` | object | `copy.json` / `COPY_*` |
| `notifyEmail` | string | `SIGNUP_NOTIFY_EMAIL`, default `program.access@localhost` |

Nested keys inside each section match `backend/copy.json` (for example
`brand.programName`, `login.title`, `docs.title`). `COPY_<SECTION>_<KEY>`
overlays replace individual strings before the response is built.

---

## `GET /api/auth/login`

- **WHAT:** Start the authorize hop: CSRF state + redirect to the mock IdP.
- **WHY:** Mirrors a real Okta `/authorize` so the SPA can use the same button.
- **WHO:** “Sign in with Okta”.
- **WHERE:** Mock mode only; **501** if `OKTA_ISSUER` is set.
- **HOW:** `store.create_state`, stash `oauth_state` on the session, redirect
  to `/api/auth/mock/okta`.

**Method:** `GET`  
**Auth:** none (writes `oauth_state` onto a session cookie)  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **302** | Mock IdP enabled; `Location` is `/api/auth/mock/okta?...` |
| **501** | `OKTA_ISSUER` is set (real Okta is not implemented in this demo) |

### Redirect (302)

`Location` is `/api/auth/mock/okta` with query:

| Query | Value |
|---|---|
| `client_id` | `OKTA_CLIENT_ID` (default `mock-f18-client`) |
| `response_type` | `code` |
| `scope` | `openid profile email` |
| `redirect_uri` | `OKTA_REDIRECT_URI` (default `http://localhost:5173/api/auth/callback`) |
| `state` | newly minted CSRF state |

### Error JSON (501, when the client wants JSON)

```json
{
  "error": "Real Okta is not configured in this demo. Unset OKTA_ISSUER to use the mock IdP."
}
```

---

## `GET /api/auth/mock/okta`

- **WHAT:** Mock hosted login page, or a JSON hint for the SPA.
- **WHY:** Local demos need an IdP without a live Okta tenant.
- **WHO:** Browser redirect from `/api/auth/login`; SPA `GET` with `Accept: application/json`.
- **WHERE:** Disabled when `OKTA_ISSUER` is set.
- **HOW:** Validate `state` when present; render HTML or JSON.

**Method:** `GET`  
**Auth:** none  
**Request body:** none  
**Query:** `state`, `client_id`, `redirect_uri`, `error` (HTML error banner)

### Status codes

| Status | When |
|---|---|
| **200** | HTML login page, or JSON when `Accept` prefers `application/json` over `text/html` |
| **400** | `state` was supplied and is missing or expired |
| **404** | `OKTA_ISSUER` is set (mock IdP disabled) |

### Response JSON (200, JSON Accept)

```json
{
  "idp": "mock",
  "client_id": "mock-f18-client",
  "state": "",
  "hint": "POST {email, password} to this URL."
}
```

`client_id` and `state` echo the query (falling back to `OKTA_CLIENT_ID` and
`""`). HTML responses are the hosted mock login form, not JSON.

### Error JSON

| Status | `error` |
|---|---|
| **400** | `Invalid or expired authorize state.` |
| **404** | `Mock IdP is disabled because OKTA_ISSUER is set.` |

---

## `POST /api/auth/mock/okta`

- **WHAT:** Authenticate against the two demo accounts and issue a session
  (JSON) or an authorization code (HTML form).
- **WHY:** The login card’s demo-account path and the hosted form share one IdP.
- **WHO:** `frontend` `login()`; browser form POST.
- **WHERE:** Same URL as GET; disabled when `OKTA_ISSUER` is set.
- **HOW:** `store.authenticate`; issue a code; JSON callers exchange immediately
  via `_set_session`.

**Method:** `POST`  
**Auth:** none (success sets `f18_session`)  
**Request body:** JSON or form fields

| Field | Required | Notes |
|---|---|---|
| `email` | yes | stripped; lookup is case-insensitive |
| `password` | yes | exact match against the demo account |
| `state` | no | form/JSON, or `?state=` query; minted if missing |

### Status codes

| Status | When |
|---|---|
| **200** | JSON body (`Content-Type: application/json`) and credentials are valid |
| **302** | HTML/form success → `/api/auth/callback?code=&state=`; form failure → back to this URL with `error=` |
| **400** | JSON path: authorization code exchange failed |
| **401** | JSON/form-as-JSON: invalid email or password |
| **404** | `OKTA_ISSUER` is set |

### Response JSON (200)

Granted (`f18.pilot@boeing.com` / `HornetReady1`):

```json
{
  "ok": true,
  "redirect": "/docs",
  "clearance": "granted",
  "email": "f18.pilot@boeing.com"
}
```

Denied (`visitor@example.com` / `NoClearance`):

```json
{
  "ok": true,
  "redirect": "/denied",
  "clearance": "denied",
  "email": "visitor@example.com"
}
```

| Field | Type | Source |
|---|---|---|
| `ok` | boolean | `true` |
| `redirect` | string | `/docs` if `clearance == "granted"`, else `/denied` |
| `clearance` | string | `"granted"` or `"denied"` |
| `email` | string | authenticated user’s email |

### Error JSON

| Status | `error` |
|---|---|
| **401** | `Invalid email or password.` |
| **400** | `Authorization code exchange failed.` |
| **404** | `Mock IdP is disabled because OKTA_ISSUER is set.` |

---

## `GET /api/auth/callback`

- **WHAT:** Exchange the authorization code, set the session, redirect by clearance.
- **WHY:** Completes the OAuth code flow after the mock IdP.
- **WHO:** Mock IdP form redirect.
- **WHERE:** After authorize; uses session `oauth_state` for CSRF when present.
- **HOW:** `store.exchange_code`, `_set_session`, then `/docs` or `/denied`.

**Method:** `GET`  
**Auth:** none (success sets `f18_session`)  
**Request body:** none  
**Query:** `code`, `state`

### Status codes

| Status | When |
|---|---|
| **302** | Code exchanged; `Location` is `/docs` (granted) or `/denied` (denied) |
| **400** | Missing `code`/`state`, CSRF state mismatch, or invalid/expired code |

### Error JSON (400, when the client wants JSON)

| `error` |
|---|
| `Missing code or state.` |
| `State mismatch. Possible CSRF.` |
| `Invalid or expired authorization code.` |

The handler compares `state` to session `oauth_state` only when that session
value is already set. A mismatch is 400. A missing expected state is not
treated as a mismatch.

---

## `GET|POST /api/auth/logout`

- **WHAT:** Clear the session and send the user to the signed-out page.
- **WHY:** Success “Sign out” and GET logout links must end the cookie session.
- **WHO:** `frontend` `api.logout`; GET/POST `/api/auth/logout`.
- **WHERE:** Portal session cookie.
- **HOW:** `session.clear()`; JSON `{ok, redirect}` or 302 `/logged-out`.

**Method:** `GET` or `POST`  
**Auth:** none (clears `f18_session` if present)  
**Request body:** none required

JSON is returned when the request is JSON (`request.is_json`) or when the
method is `POST` and `Accept` contains `application/json`. Otherwise the
handler redirects.

### Status codes

| Status | When |
|---|---|
| **200** | JSON response (see above) |
| **302** | `Location: /logged-out` |

### Response JSON (200)

```json
{
  "ok": true,
  "redirect": "/logged-out"
}
```

---

## `GET /api/auth/me`

- **WHAT:** Return the current session user (`email`, `name`, `callsign`, `clearance`).
- **WHY:** Success/Denied pages decide which scene to show.
- **WHO:** `frontend` `api.me`.
- **WHERE:** Requires a valid `f18_session`; **401** otherwise.
- **HOW:** `_session_user()` then jsonify the stored fields.

**Method:** `GET`  
**Auth:** `f18_session` cookie  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **200** | Session has a user dict with `email` (granted **or** denied) |
| **401** | No session, or session user is missing `email` |

### Response JSON (200) — granted

```json
{
  "email": "f18.pilot@boeing.com",
  "name": "LT. Callsign Viper",
  "callsign": "VIPER",
  "clearance": "granted"
}
```

### Response JSON (200) — denied

```json
{
  "email": "visitor@example.com",
  "name": "Guest Visitor",
  "callsign": "CIVILIAN",
  "clearance": "denied"
}
```

| Field | Type | Source |
|---|---|---|
| `email` | string | session |
| `name` | string or `null` | session (`user.get("name")`) |
| `callsign` | string or `null` | session (`user.get("callsign")`) |
| `clearance` | string or `null` | session (`user.get("clearance")`) — `"granted"` or `"denied"` for demo accounts |

### Error JSON (401)

```json
{
  "error": "Not authenticated."
}
```

---

## `POST /api/auth/signup`

- **WHAT:** Validate a request-access form and notify `SIGNUP_NOTIFY_EMAIL`.
- **WHY:** Visitors without an account need a way to ask for access.
- **WHO:** `frontend` `api.signup`.
- **WHERE:** JSON `{name, email, organization?}`; mailbox and optional SMTP.
- **HOW:** `validate_signup` then `send_signup_notice`; 400/502 on failure.

**Method:** `POST`  
**Auth:** none  
**Request body:** JSON object

| Field | Required | Validation |
|---|---|---|
| `name` | yes | non-empty after strip; max 120 characters |
| `email` | yes | non-empty; max 254 characters; matches `^[^@\s]+@[^@\s]+$` |
| `organization` | no | max 200 characters; omitted/blank stored as `null` |

### Status codes

| Status | When |
|---|---|
| **200** | Notification written (mailbox `.eml`; SMTP only if `SMTP_HOST` is set) |
| **400** | Missing/invalid JSON or field validation failed |
| **502** | `send_signup_notice` raised |

### Response JSON (200)

```json
{
  "ok": true,
  "notifyEmail": "program.access@localhost",
  "mocked": true,
  "messageId": "<message-id>"
}
```

| Field | Type | Source |
|---|---|---|
| `ok` | boolean | `true` |
| `notifyEmail` | string | `result["to"]` — `notify_address()` |
| `mocked` | boolean | `true` when `SMTP_HOST` is unset |
| `messageId` | string | email `Message-ID` header (`result["id"]`) |

### Error JSON (400)

`error` is exactly one of:

- `JSON body with name and email is required.`
- `Name is required.`
- `Name is too long.`
- `Email is required.`
- `Enter a valid email address.`
- `Organization is too long.`

### Error JSON (502)

```json
{
  "error": "Failed to send notification: <exception>"
}
```

---

## `GET /api/auth/signup/config`

- **WHAT:** Public notify-address for the request-access form.
- **WHY:** Signup copy can show who will receive the email.
- **WHO:** Frontend signup config (fallback if `/api/copy` is unused).
- **WHERE:** Always public.
- **HOW:** `notify_address()` from `SIGNUP_NOTIFY_EMAIL`.

**Method:** `GET`  
**Auth:** none  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **200** | Always |

### Response JSON (200)

```json
{
  "notifyEmail": "program.access@localhost"
}
```

---

## `GET /api/auth/signup/mailbox`

- **WHAT:** List the last few mock notification `.eml` files.
- **WHY:** Local demos can prove signup mail without a real inbox.
- **WHO:** Dev tools.
- **WHERE:** Development only (`FLASK_DEBUG`); **404** otherwise.
- **HOW:** `list_mailbox()` plus `notifyEmail` and `mocked`.

**Method:** `GET`  
**Auth:** none  
**Request body:** none

`is_dev()` is true unless `FLASK_DEBUG` is `0`, `false`, or `False`.
`list_mailbox()` returns at most 8 newest `backend/mailbox/*.eml` (and
legacy `*.json`) files.

### Status codes

| Status | When |
|---|---|
| **200** | Development mode |
| **404** | Not development |

### Response JSON (200)

```json
{
  "notifyEmail": "program.access@localhost",
  "mocked": true,
  "messages": []
}
```

| Field | Type | Source |
|---|---|---|
| `notifyEmail` | string | `notify_address()` |
| `mocked` | boolean | `not smtp_configured()` (`SMTP_HOST` unset → `true`) |
| `messages` | array | parsed mailbox entries, newest first |

Each successfully parsed `.eml` message:

| Field | Type |
|---|---|
| `id` | `Message-ID` or `null` |
| `to` | `To` or `null` |
| `from` | `From` or `null` |
| `subject` | `Subject` or `null` |
| `timestamp` | `X-F18-Submitted` or `Date` |
| `filename` | mailbox file name |
| `applicant.name` | `X-F18-Applicant-Name` |
| `applicant.email` | `X-F18-Applicant-Email` |
| `applicant.organization` | `X-F18-Applicant-Org` (absent when the applicant omitted org) |
| `preview` | first 500 characters of the plain body |

A parse failure is `{ "filename": "<name>", "error": "<exception>" }` instead.
Legacy `.json` files are returned as their parsed object plus `filename`.

### Error JSON (404)

```json
{
  "error": "Mailbox listing is available in development only."
}
```

---

## `GET /api/docs/meta`

- **WHAT:** Return `{configured, source, title}` for the granted session.
- **WHY:** The SPA labels the reader without fetching HTML first.
- **WHO:** `frontend` `docsMeta`.
- **WHERE:** Auth-gated; **401** / **403** otherwise.
- **HOW:** `require_granted` then `meta_payload()`. Never returns AWS keys or
  bucket names.

**Method:** `GET`  
**Auth:** `f18_session` with `clearance == "granted"`  
**Request body:** none

### Status codes

| Status | When |
|---|---|
| **200** | Granted session |
| **401** | No session |
| **403** | Session present but `clearance` is not `granted` |

### Response JSON (200)

```json
{
  "configured": false,
  "source": "mock",
  "title": "F/A-18 Mission Software"
}
```

| Field | Type | Source |
|---|---|---|
| `configured` | boolean | `true` when source is not `mock` |
| `source` | string | `"s3-public"` if `S3_DOXYGEN_BASE_URL` is set; else `"s3"` if `S3_DOXYGEN_BUCKET` is set; else `"mock"` |
| `title` | string | `copy.json` `docs.title`, else `F/A-18 Mission Software` |

### Error JSON

| Status | `error` |
|---|---|
| **401** | `Not authenticated.` |
| **403** | `Not authorized.` |

---

## `GET /api/docs/<path>`

- **WHAT:** Proxy one allowlisted Doxygen object (HTML, CSS, JS, image, font).
- **WHY:** The browser must never talk to S3 directly or see AWS keys.
- **WHO:** The documentation reader (pages + rewritten asset URLs).
- **WHERE:** Granted session only. Unset `S3_DOXYGEN_*` serves
  `backend/doxygen-mock/html`.
- **HOW:** `require_granted`, `normalize_doc_path`, `fetch_doc`, `Response`
  with MIME.

`GET /api/docs` and `GET /api/docs/` serve `index.html`. The path `meta` is
handled by `GET /api/docs/meta` (same JSON as above).

**Method:** `GET`  
**Auth:** `f18_session` with `clearance == "granted"`  
**Request body:** none

Allowed extensions: `.html`, `.css`, `.js`, `.png`, `.svg`, `.gif`, `.jpg`,
`.jpeg`, `.woff`, `.woff2`, `.ico`, `.map`, `.md`. Empty path or a trailing
slash becomes `index.html`. NUL, `..` segments, and non-allowlisted
extensions fail `normalize_doc_path` and return **400**. A literal `..`
in the URL may be rejected by the HTTP stack as a Werkzeug HTML **404**
before this handler runs.

### Status codes

| Status | When |
|---|---|
| **200** | Granted session and the object was fetched |
| **400** | Path failed `normalize_doc_path` |
| **401** | No session |
| **403** | Session present but `clearance` is not `granted` |
| **404** | Sanitized path did not resolve to an object |
| **502** | Documentation source raised (S3/HTTP failure other than not-found) |

### Success (200)

Raw file bytes. Not JSON.

| Header | Value |
|---|---|
| `Content-Type` | MIME from the object or extension fallback |
| `Cache-Control` | `private, max-age=60` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Docs-Source` | `mock`, `s3-public`, or `s3` |

### Error JSON

| Status | `error` |
|---|---|
| **400** | `Invalid document path.` |
| **401** | `Not authenticated.` |
| **403** | `Not authorized.` |
| **404** | `Document not found.` |
| **502** | `Documentation source failed: <exception>` |
