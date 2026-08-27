"""F/A-18 Hornet program access portal — Flask API + mock OIDC.

When OKTA_ISSUER is unset the built-in mock IdP is used. Session is an
httpOnly Flask cookie signed with FLASK_SECRET.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
)
from flask_cors import CORS

from copy_text import get_copy
from doxygen import register_docs
from mock_okta import store
from signup_mail import (
    is_dev,
    list_mailbox,
    notify_address,
    send_signup_notice,
    smtp_configured,
    validate_signup,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent
DIST = ROOT.parent / "frontend" / "dist"

OKTA_ISSUER = (os.environ.get("OKTA_ISSUER") or "").strip()
OKTA_CLIENT_ID = os.environ.get("OKTA_CLIENT_ID", "mock-f18-client")
OKTA_CLIENT_SECRET = os.environ.get("OKTA_CLIENT_SECRET", "mock-f18-secret")
OKTA_REDIRECT_URI = os.environ.get(
    "OKTA_REDIRECT_URI", "http://localhost:5173/api/auth/callback"
)
USE_MOCK = not OKTA_ISSUER

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-f18-portal-secret")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_NAME="f18_session",
    PERMANENT_SESSION_LIFETIME=8 * 60 * 60,
)

CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
    supports_credentials=True,
)


def _wants_json() -> bool:
    """
    What: Decide whether this request should get a JSON error/body.
    Why: The mock IdP serves both a hosted HTML page and SPA JSON.
    Who: _error and mock_okta_hosted.
    Where: Incoming Flask request headers/body.
    How: True if the body is JSON or Accept prefers application/json over HTML.
    """
    if request.is_json:
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def _session_user() -> dict | None:
    """
    What: Return the signed-in user dict from the Flask session, or None.
    Why: /api/auth/me and clearance gates need a validated session payload.
    Who: auth_me (and any route that checks login).
    Where: httpOnly f18_session cookie.
    How: Require a dict with an email; otherwise treat as anonymous.
    """
    user = session.get("user")
    if not isinstance(user, dict) or not user.get("email"):
        return None
    return user


def _set_session(user) -> None:
    """
    What: Replace the session with the mock-IdP user fields we expose to the SPA.
    Why: After a successful code exchange the browser must stay signed in.
    Who: mock_okta_hosted (JSON path) and auth_callback.
    Where: Flask session cookie for this portal.
    How: Clear, mark permanent, store email/name/callsign/clearance.
    """
    session.clear()
    session.permanent = True
    session["user"] = {
        "email": user.email,
        "name": user.name,
        "callsign": user.callsign,
        "clearance": user.clearance,
    }


def _error(message: str, status: int = 400):
    """
    What: Return an error as JSON or plain text depending on the client.
    Why: SPA callers need {error}; the hosted mock page needs a string.
    Who: auth_login, mock_okta_hosted, auth_callback.
    Where: OAuth and mock-IdP failure paths.
    How: jsonify when JSON is wanted; otherwise (message, status).
    """
    if _wants_json() or request.is_json:
        return jsonify({"error": message}), status
    return message, status


@app.get("/api/health")
def health():
    """
    What: Liveness payload: ok, which IdP, issuer.
    Why: Operators and the frontend can confirm Flask is up.
    Who: GET /api/health, frontend api.health.
    Where: Always public.
    How: USE_MOCK when OKTA_ISSUER is empty.
    """
    return jsonify(
        {
            "ok": True,
            "idp": "mock" if USE_MOCK else "okta",
            "issuer": OKTA_ISSUER or None,
        }
    )


@app.get("/api/auth/login")
def auth_login():
    """
    What: Start the authorize hop: CSRF state + redirect to the mock IdP.
    Why: Mirrors a real Okta /authorize so the SPA can use the same button.
    Who: "Sign in with Okta" (GET /api/auth/login).
    Where: Mock mode only; 501 if OKTA_ISSUER is set.
    How: store.create_state, stash oauth_state, redirect to /api/auth/mock/okta.
    """
    if not USE_MOCK:
        return _error(
            "Real Okta is not configured in this demo. Unset OKTA_ISSUER to use the mock IdP.",
            501,
        )

    state, _nonce = store.create_state(OKTA_CLIENT_ID, OKTA_REDIRECT_URI)
    session["oauth_state"] = state
    params = urlencode(
        {
            "client_id": OKTA_CLIENT_ID,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": OKTA_REDIRECT_URI,
            "state": state,
        }
    )
    return redirect(f"/api/auth/mock/okta?{params}")


@app.route("/api/auth/mock/okta", methods=["GET", "POST"])
def mock_okta_hosted():
    """
    What: Mock hosted login page and token issuer.
    Why: Local demos need an IdP without a live Okta tenant.
    Who: auth_login redirect, SPA login() POST, browser form POST.
    Where: GET/POST /api/auth/mock/okta (disabled when OKTA_ISSUER is set).
    How: GET renders HTML or JSON; POST authenticates, issues a code, exchanges or redirects.
    """
    if not USE_MOCK:
        return _error("Mock IdP is disabled because OKTA_ISSUER is set.", 404)

    if request.method == "GET":
        state = request.args.get("state", "")
        rec = store.peek_state(state) if state else None
        if state and rec is None:
            return _error("Invalid or expired authorize state.", 400)
        if _wants_json():
            return jsonify(
                {
                    "idp": "mock",
                    "client_id": request.args.get("client_id", OKTA_CLIENT_ID),
                    "state": state,
                    "hint": "POST {email, password} to this URL.",
                }
            )
        return render_template_string(
            MOCK_LOGIN_HTML,
            state=state,
            client_id=request.args.get("client_id", OKTA_CLIENT_ID),
            redirect_uri=request.args.get("redirect_uri", OKTA_REDIRECT_URI),
            error=request.args.get("error", ""),
        )

    payload = request.get_json(silent=True) if request.is_json else None
    form = payload or request.form
    email = (form.get("email") or "").strip()
    password = form.get("password") or ""
    state = (form.get("state") or request.args.get("state") or "").strip()

    user = store.authenticate(email, password)
    if user is None:
        if request.is_json or _wants_json():
            return jsonify({"error": "Invalid email or password."}), 401
        qs = urlencode(
            {
                "state": state,
                "client_id": request.args.get("client_id", OKTA_CLIENT_ID),
                "redirect_uri": request.args.get("redirect_uri", OKTA_REDIRECT_URI),
                "error": "Invalid email or password.",
            }
        )
        return redirect(f"/api/auth/mock/okta?{qs}")

    rec = store.peek_state(state) if state else None
    if rec is None:
        # SPA testers can POST credentials without a prior authorize hop.
        state, nonce = store.create_state(OKTA_CLIENT_ID, OKTA_REDIRECT_URI)
        session["oauth_state"] = state
        rec = store.peek_state(state)
    else:
        nonce = rec.nonce
        session["oauth_state"] = state

    code = store.issue_code(
        user=user,
        state=state,
        nonce=nonce,
        client_id=rec.client_id,
        redirect_uri=rec.redirect_uri,
    )

    if request.is_json:
        # Complete the exchange in-process so the SPA can navigate once.
        exchanged = store.exchange_code(code, state)
        if exchanged is None:
            return jsonify({"error": "Authorization code exchange failed."}), 400
        session.pop("oauth_state", None)
        _set_session(exchanged.user)
        dest = "/docs" if exchanged.user.clearance == "granted" else "/denied"
        return jsonify(
            {
                "ok": True,
                "redirect": dest,
                "clearance": exchanged.user.clearance,
                "email": exchanged.user.email,
            }
        )

    return redirect(f"/api/auth/callback?{urlencode({'code': code, 'state': state})}")


@app.get("/api/auth/callback")
def auth_callback():
    """
    What: Exchange the authorization code, set the session, redirect by clearance.
    Why: Completes the OAuth code flow after the mock IdP (or a real one later).
    Who: Mock IdP redirect; GET /api/auth/callback.
    Where: After authorize; uses session oauth_state for CSRF.
    How: store.exchange_code, _set_session, /docs if granted else /denied.
    """
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    expected = session.get("oauth_state")

    if not code or not state:
        return _error("Missing code or state.", 400)
    if expected and expected != state:
        return _error("State mismatch. Possible CSRF.", 400)

    rec = store.exchange_code(code, state)
    if rec is None:
        return _error("Invalid or expired authorization code.", 400)

    session.pop("oauth_state", None)
    _set_session(rec.user)
    dest = "/docs" if rec.user.clearance == "granted" else "/denied"
    return redirect(dest)


@app.route("/api/auth/logout", methods=["GET", "POST"])
def auth_logout():
    """
    What: Clear the session and send the user to the signed-out page.
    Why: Success "Sign out" and GET logout links must end the cookie session.
    Who: frontend api.logout; GET/POST /api/auth/logout.
    Where: Portal session cookie.
    How: session.clear(); JSON {ok, redirect} or 302 /logged-out.
    """
    session.clear()
    if request.is_json or (
        request.method == "POST" and "application/json" in request.headers.get("Accept", "")
    ):
        return jsonify({"ok": True, "redirect": "/logged-out"})
    return redirect("/logged-out")


@app.get("/api/auth/me")
def auth_me():
    """
    What: Return the current session user (email, name, callsign, clearance).
    Why: Success/Denied pages decide which scene to show.
    Who: frontend api.me; GET /api/auth/me.
    Where: Requires a valid f18_session; 401 otherwise.
    How: _session_user() then jsonify the stored fields.
    """
    user = _session_user()
    if user is None:
        return jsonify({"error": "Not authenticated."}), 401
    return jsonify(
        {
            "email": user["email"],
            "name": user.get("name"),
            "callsign": user.get("callsign"),
            "clearance": user.get("clearance"),
        }
    )


@app.get("/api/copy")
def api_copy():
    """
    What: Public JSON of merged user-facing strings plus notifyEmail.
    Why: The SPA renders configurable copy without a frontend rebuild.
    Who: frontend api.copy / CopyProvider; operators curling /api/copy.
    Where: GET /api/copy (unauthenticated; Vite proxies it in dev).
    How: get_copy() (copy.json + COPY_* env, mtime cache) then attach notify_address().
    """
    data = get_copy()
    data["notifyEmail"] = notify_address()
    return jsonify(data)


@app.get("/api/auth/signup/config")
def signup_config():
    """
    What: Public notify-address for the request-access form.
    Why: Signup copy can show who will receive the email.
    Who: frontend signupConfig (fallback if /api/copy is unused).
    Where: GET /api/auth/signup/config.
    How: notify_address() from SIGNUP_NOTIFY_EMAIL.
    """
    return jsonify({"notifyEmail": notify_address()})


@app.get("/api/auth/signup/mailbox")
def signup_mailbox():
    """
    What: List the last few mock notification .eml files.
    Why: Local demos can prove signup mail without a real inbox.
    Who: Dev tools / GET /api/auth/signup/mailbox.
    Where: Development only (FLASK_DEBUG); 404 otherwise.
    How: list_mailbox() plus notifyEmail and mocked flag.
    """
    if not is_dev():
        return jsonify({"error": "Mailbox listing is available in development only."}), 404
    return jsonify(
        {
            "notifyEmail": notify_address(),
            "mocked": not smtp_configured(),
            "messages": list_mailbox(),
        }
    )


@app.post("/api/auth/signup")
def signup():
    """
    What: Validate a request-access form and notify SIGNUP_NOTIFY_EMAIL.
    Why: Visitors without an account need a way to ask for access.
    Who: frontend api.signup; POST /api/auth/signup.
    Where: JSON {name, email, organization?}; mailbox and optional SMTP.
    How: validate_signup then send_signup_notice; 400/502 on failure.
    """
    payload = request.get_json(silent=True)
    applicant, err = validate_signup(payload)
    if err:
        return jsonify({"error": err}), 400
    try:
        result = send_signup_notice(applicant)
    except Exception as exc:
        return jsonify({"error": f"Failed to send notification: {exc}"}), 502
    return jsonify(
        {
            "ok": True,
            "notifyEmail": result["to"],
            "mocked": result["mocked"],
            "messageId": result["id"],
        }
    )



register_docs(app, _session_user)


if DIST.is_dir():

    @app.route("/", defaults={"path": ""})
    @app.route("/\u003cpath:path\u003e")
    def spa_fallback(path: str):
        """
        What: Serve the built React app (index.html or a static asset).
        Why: Production can run a single Flask process without Vite.
        Who: Browser navigations that are not /api/*.
        Where: Only registered when frontend/dist exists.
        How: send_from_directory for real files; otherwise index.html.
        """
        if path.startswith("api/"):
            abort(404)
        target = DIST / path
        if path and target.is_file():
            return send_from_directory(DIST, path)
        return send_from_directory(DIST, "index.html")


MOCK_LOGIN_HTML = """
\u003c!DOCTYPE html\u003e
\u003chtml lang="en"\u003e
\u003chead\u003e
  \u003cmeta charset="utf-8" /\u003e
  \u003cmeta name="viewport" content="width=device-width, initial-scale=1" /\u003e
  \u003ctitle\u003eMock Okta · F/A-18 Program\u003c/title\u003e
  \u003clink rel="preconnect" href="https://fonts.googleapis.com" /\u003e
  \u003clink rel="preconnect" href="https://fonts.gstatic.com" crossorigin /\u003e
  \u003clink href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Oswald:wght@500;600&display=swap" rel="stylesheet" /\u003e
  \u003cstyle\u003e
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: Inter, system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 50% -10%, #12306a 0%, #0A1628 55%, #060b14 100%);
      color: #f4f6f8;
    }
    .card {
      width: min(420px, 92vw); padding: 2rem 1.75rem 1.5rem;
      background: rgba(10, 22, 40, 0.84);
      border: 1px solid rgba(200, 210, 220, 0.16);
      border-radius: 12px;
      box-shadow: 0 24px 60px rgba(0,0,0,.45);
    }
    .eyebrow { color: #8aa0c4; letter-spacing: .18em; font-size: .68rem; text-transform: uppercase; margin: 0 0 .4rem; }
    h1 { font-family: Oswald, Inter, sans-serif; font-weight: 600; letter-spacing: .04em; margin: 0 0 .35rem; font-size: 1.55rem; }
    p.sub { margin: 0 0 1.4rem; color: #c5ced8; font-size: .92rem; }
    label { display: block; font-size: .78rem; color: #c5ced8; margin: .7rem 0 .28rem; }
    input {
      width: 100%; padding: .7rem .75rem; border-radius: 8px;
      border: 1px solid rgba(200,210,220,.22); background: #0d1a30; color: #fff;
      font: inherit;
    }
    input:focus { outline: 2px solid #0033A0; outline-offset: 2px; border-color: #5b8cff; }
    button {
      width: 100%; margin-top: 1.15rem; padding: .8rem 1rem; border: 0; border-radius: 8px;
      background: #0033A0; color: #fff; font-weight: 600; font-size: .95rem; cursor: pointer;
    }
    button:hover { background: #1a4dcc; }
    button:focus-visible { outline: 2px solid #fff; outline-offset: 3px; }
    .err {
      background: rgba(180, 40, 40, .18); border: 1px solid rgba(255,120,120,.35);
      color: #ffd4d4; padding: .65rem .75rem; border-radius: 8px; margin-bottom: 1rem; font-size: .88rem;
    }
    .hint { margin: 1.1rem 0 0; font-size: .75rem; color: #8aa0c4; line-height: 1.45; }
    code { color: #e8eef8; }
  \u003c/style\u003e
\u003c/head\u003e
\u003cbody\u003e
  \u003cmain class="card"\u003e
    \u003cp class="eyebrow"\u003eMock identity provider\u003c/p\u003e
    \u003ch1\u003eSign in to continue\u003c/h1\u003e
    \u003cp class="sub"\u003eF/A-18 Program Access · hosted Okta stand-in\u003c/p\u003e
    {% if error %}
      \u003cdiv class="err" role="alert"\u003e{{ error }}\u003c/div\u003e
    {% endif %}
    \u003cform method="post" action="/api/auth/mock/okta"\u003e
      \u003cinput type="hidden" name="state" value="{{ state }}" /\u003e
      \u003cinput type="hidden" name="client_id" value="{{ client_id }}" /\u003e
      \u003cinput type="hidden" name="redirect_uri" value="{{ redirect_uri }}" /\u003e
      \u003clabel for="email"\u003eEmail\u003c/label\u003e
      \u003cinput id="email" name="email" type="email" autocomplete="username" required /\u003e
      \u003clabel for="password"\u003ePassword\u003c/label\u003e
      \u003cinput id="password" name="password" type="password" autocomplete="current-password" required /\u003e
      \u003cbutton type="submit"\u003eAuthenticate\u003c/button\u003e
    \u003c/form\u003e
    \u003cp class="hint"\u003e
      Demo accounts\u003cbr /\u003e
      \u003ccode\u003ef18.pilot@boeing.com\u003c/code\u003e / \u003ccode\u003eHornetReady1\u003c/code\u003e → granted\u003cbr /\u003e
      \u003ccode\u003evisitor@example.com\u003c/code\u003e / \u003ccode\u003eNoClearance\u003c/code\u003e → denied
    \u003c/p\u003e
  \u003c/main\u003e
\u003c/body\u003e
\u003c/html\u003e
"""


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False")
    app.run(host="0.0.0.0", port=5000, debug=debug)
