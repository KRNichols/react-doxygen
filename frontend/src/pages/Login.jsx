import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { useCopy } from "../copy.jsx";
import { login } from "../api.js";

/**
 * What: Sign-in scene: Okta hop plus demo-account form.
 * Why: This is the portal home; granted/denied accounts land after submit.
 * Who: Routes / and /login (App.jsx).
 * Where: Atmosphere + login card; strings from copy.login / brand.
 * How: POST /api/auth/mock/okta or redirect to /api/auth/login.
 */
export default function Login() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.login;
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  /**
   * What: Jump to the mock (or real) hosted Okta authorize URL.
   * Why: The primary button must match a production Okta start.
   * Who: “Sign in with Okta” click.
   * Where: GET /api/auth/login (Flask).
   * How: Full-page assign so the authorize cookies/state stick.
   */
  function startOkta() {
    window.location.assign("/api/auth/login");
  }

  /**
   * What: Submit demo email/password and route by clearance.
   * Why: Graders and demos need a JSON login without the hosted HTML.
   * Who: The login <form> onSubmit.
   * Where: Stays on / until login() resolves; then /docs if granted or /denied.
   * How: api.login; show copy.login.errorFallback on failure.
   */
  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await login(email, password);
      nav(res.redirect || (res.clearance === "granted" ? "/success" : "/denied"));
    } catch (err) {
      setError(err.message || c.errorFallback);
    } finally {
      setBusy(false);
    }
  }

  /**
   * What: Bind a text field to React state.
   * Why: Email and password inputs share the same change wiring.
   * Who: The two login <input> onChange handlers.
   * Where: Login card only.
   * How: Return a change handler closed over the given setter so both inputs share one factory.
   */
  function onField(setter) {
    /**
     * What: Write this input’s value into the matching useState setter.
     * Why: Controlled inputs must stay in React state for submit.
     * Who: The field’s onChange (created by onField).
     * Where: This page’s form inputs.
     * How: Copy the input’s current text into the closed-over setter so the field stays controlled.
     */
    return function handleChange(e) {
      setter(e.target.value);
    };
  }

  return (
    <div className="stage" data-scene="login">
      <Atmosphere scene="login" />
      <a className="skip-link" href="#main">{brand.skipLink}</a>
      <BrandHeader />
      <main id="main" className="main">
        <section className="hero-copy">
          <p className="hero-kicker">{c.kicker}</p>
          <h1 className="hero-title">{c.title}</h1>
          <p className="sub">{c.sub}</p>
        </section>
        <form className="card" onSubmit={onSubmit}>
          <h2>{c.cardTitle}</h2>
          <p className="sub">{c.cardSub}</p>
          {error ? <div className="err" role="alert" id="login-error">{error}</div> : null}
          <button className="btn" type="button" onClick={startOkta}>
            {c.oktaButton}
          </button>
          <p className="divider">{c.divider}</p>
          <label htmlFor="email">{c.emailLabel} <span className="req">(required)</span></label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            aria-required="true"
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "login-error" : undefined}
            value={email}
            onChange={onField(setEmail)}
          />
          <label htmlFor="password">{c.passwordLabel} <span className="req">(required)</span></label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            aria-required="true"
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "login-error" : undefined}
            value={password}
            onChange={onField(setPassword)}
          />
          <button className="btn ghost" type="submit" disabled={busy}>
            {busy ? c.submitting : c.submit}
          </button>
          <p className="hint">
            {c.hintAuthorizedLabel}: <code>{c.hintAuthorizedEmail}</code> / <code>{c.hintAuthorizedPassword}</code>
            <br />
            {c.hintVisitorLabel}: <code>{c.hintVisitorEmail}</code> / <code>{c.hintVisitorPassword}</code>
          </p>
          <p className="access-link">
            {c.accessPrompt} <Link to="/signup">{c.accessLink}</Link>
          </p>
        </form>
      </main>
      <Footer />
    </div>
  );
}
