# F/A-18 Program Access Portal

Boeing-branded demonstration. Flask API plus a React/Vite SPA. Mock Okta only
(no live tenant). Not an official Boeing system.

## Demo accounts

- Granted: `f18.pilot@boeing.com` / `HornetReady1` — session clearance granted, then `/docs`.
- Denied: `visitor@example.com` / `NoClearance` — login still completes (HTTP 200 + session); clearance is denied and the SPA goes to `/denied`.
- Wrong password: HTTP 401 and the login error banner. No session.

Denied is a completed login. `GET /api/auth/me` returns `clearance: denied`.

## Routes

- `/` and `/login` — sign in (Okta hop or demo form)
- `/signup` — request access
- `/signup-sent` — request accepted
- `/success` — granted landing (also reachable after login)
- `/docs` — auth-gated Doxygen reader (granted sessions only)
- `/denied` — signed in, no clearance
- `/logged-out` — session cleared

Header chrome is the mark plus program name. Footer is the mark, the demo line, and copyright. There is no flying Hornet animation, no flyout help, and no DocsHero photo band.

## Screenshots

Live captures from http://127.0.0.1:5000 at this SHA (navy BDS, DEMO_LOGIN off, default UNCLASSIFIED banners). Login is copy-left / card-right at >=960px with no email/password, no divider, no demo hints, and no folder box.

### Sign in (`/` / `/login`)

![Sign-in card, copy-left / card-right, Okta only](docs/screenshots/login.png)

### Request access (`/signup`)

![Request program access form](docs/screenshots/signup.png)

### Request sent (`/signup-sent`)

![Access request sent confirmation](docs/screenshots/signup-sent.png)

### Signed in (`/success`)

![Granted session card with Open Documentation](docs/screenshots/success.png)

### Not authorized (`/denied`)

![Denied session card for visitor@example.com](docs/screenshots/denied.png)

### Signed out (`/logged-out`)

![Session ended confirmation](docs/screenshots/logged-out.png)

### Documentation (`/docs`)

![Heroless Doxygen reader on the Main Page](docs/screenshots/docs.png)

## How to run Flask + Vite

1. Copy `backend/.env.example` to `backend/.env` if you need local overrides. Do not commit `.env`. Leave `OKTA_ISSUER` empty for the mock IdP. Set a long random `FLASK_SECRET`. Flask will not boot if `FLASK_SECRET` is missing, empty, or an example/default string.
2. Backend: `python -m pip install -r backend/requirements.txt` then `python backend/app.py` (port 5000).
3. Frontend: in `frontend`, install dependencies and run `npm run dev` (Vite on port 5173, proxies `/api` to Flask).
4. Optional: `npm run build` in `frontend` so Flask can serve `frontend/dist` on port 5000 alone.

## Environment

Only `backend/.env.example` is tracked. Secrets and mailbox dumps stay local (see `.gitignore`).

Signup without `SMTP_HOST` writes a `.eml` under `backend/mailbox/`. `GET /api/copy` serves `backend/copy.json` (plus `COPY_*` overlays) and `classification` `{level, text, color, ink, disclaimer}`.

Granted sessions read Doxygen HTML at `/docs` through `/api/docs/*`. Unset S3 vars to serve `backend/doxygen-mock/html`.

### Variables

Mock Okta (leave `OKTA_ISSUER` empty):

- `OKTA_ISSUER` — empty = mock IdP; set only if you point at a real issuer
- `OKTA_CLIENT_ID` / `OKTA_CLIENT_SECRET` / `OKTA_REDIRECT_URI`
- `FLASK_SECRET` — required. A long random string. Empty, example, or default values refuse to boot. There is no in-code fallback.
- `FLASK_DEBUG`
- `HOST` — Session cookie `f18_session` is Secure unless this is HTTP localhost.
- `DEMO_LOGIN` — off unless `1`/`true`/`yes`. Demo email/password fields stay hidden otherwise.

Signup:

- `SIGNUP_NOTIFY_EMAIL` (default `program.access@localhost`)
- `SIGNUP_FROM_EMAIL`
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_STARTTLS` — unset host writes `backend/mailbox/*.eml`

Doxygen (`/docs` via `/api/docs/*`; no live S3 required):

- unset all `S3_DOXYGEN_*` → `backend/doxygen-mock/html`
- `S3_DOXYGEN_BASE_URL` — public prefix (wins)
- `S3_DOXYGEN_BUCKET` / `S3_DOXYGEN_PREFIX` / `S3_DOXYGEN_REGION` — private bucket

Copy overlays:

- `COPY_<SECTION>_<KEY>` e.g. `COPY_LOGIN_TITLE`
- `COPY_FILE` — alternate catalog path

Classification banner (display-only; copy root `.env.example` to `.env`):

- `CLASSIFICATION` — same key as the GitLab CI/CD dropdown. Options: `UNCLASSIFIED` (default), `CUI`, `CONFIDENTIAL`, `SECRET`, `TOP SECRET`, `ITAR`, `CUSTOM`
- `CLASSIFICATION_TEXT` — optional override for the banner words on any level
- `CLASSIFICATION_CUSTOM_TEXT` / `CLASSIFICATION_CUSTOM_COLOR` — used when `CLASSIFICATION=CUSTOM`
- This is a label. It is not an ATO or a claim the demo can hold CUI or classified.
- `GET /api/copy` How: catalog + `notifyEmail` + `classification` `{level, text, color, ink, disclaimer}`

## Checks and CI

`make check` is the fast local lint + five-part comment gate + approved-package allowlist.

`make ci` is the portable product contract (also `scripts/pipeline.sh`): ruff, comments `--all`, unused-code, approved packages, pytest, frontend lint/test, frontend build.

Approved first-party packages (current tree only; not an ATO and not scanner-proof): [docs/approved-packages.md](docs/approved-packages.md). `make packages` fails any name not on that list.

GitHub Actions (`.github/workflows/ci.yml`) is the hosted pipeline. GitLab CI (`.gitlab-ci.yml`) uses the same contract — both call `make ci` / the pipeline script. A separate security workflow runs pip-audit and production high+ Node audit so advisory noise does not fail the product gate.

Actions: https://github.com/KRNichols/react-doxygen/actions

`make review` is the GitLab MR reviewer bot (python3 + curl, no extra packages). On a laptop it is a dry-run: it scans the local diff, prints one note, and does not call the API. On a GitLab `merge_request_event` it reads the MR diff and this pipeline's job results, posts one MR note, Approves when product gates pass and the diff has no blocking findings, and unapproves if a later push fails. `security:pip` / pip-audit staying red does not block (accepted Flask, flask-cors, and python-dotenv pins). `backend`, `frontend`, `quality`, `build`, and `security:node` do. A missing `GITLAB_REVIEWER_TOKEN` fails the review job with setup steps; it never fakes an Approve.

### GitLab MR reviewer bot

This bot is GitLab-only. There is no GitHub Actions reviewer job.

1. Create a GitLab Project Access Token with the `api` scope and a role that can approve merge requests (Developer or Maintainer).
2. Add CI/CD variable `GITLAB_REVIEWER_TOKEN` (masked). The job uses `CI_API_V4_URL`, so GitLab.com and self-managed both work.
3. Add that project-bot user as an eligible (and required, if you want the wait gone) MR reviewer under Settings → Merge requests.

Local check: `make review` or `make review` with `--dry-run` (via `sh scripts/review-mr.sh --dry-run`).

## API

Route-by-route request bodies, response JSON, and status codes are in
[docs/api.md](docs/api.md).

The portal session is the httpOnly `f18_session` cookie (SameSite=Lax,
eight-hour lifetime, Secure unless `HOST` is HTTP localhost), signed with
`FLASK_SECRET`. The SPA sends it on `/api/*` with `credentials: include`. A
successful mock login — granted or denied — sets the cookie;
`GET /api/auth/me` then returns `clearance: granted` or `clearance: denied`.
No cookie is **401**. Documentation routes additionally return **403** when
the session exists but clearance is not granted.

`POST /api/auth/logout` clears `f18_session` on POST only. GET must not log
anyone out. GET does not clear the session (404 or 405).

`GET /api/auth/callback`: session `oauth_state` is always required and must
match.

`GET|POST /api/auth/mock/okta` is off unless `DEMO_LOGIN` is on. **403** when
`DEMO_LOGIN` is off.
