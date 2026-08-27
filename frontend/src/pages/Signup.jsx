import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { fill, useCopy } from "../copy.jsx";
import { signup } from "../api.js";

/**
 * What: Request-access form that notifies SIGNUP_NOTIFY_EMAIL.
 * Why: Visitors without a demo account need a way to ask for access.
 * Who: Route /signup.
 * Where: Same patrol scene as login; strings from copy.signup.
 * How: POST /api/auth/signup then navigate to /signup-sent.
 */
export default function Signup() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.signup;
  const notifyEmail = copy.notifyEmail || "";
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [organization, setOrganization] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  /**
   * What: Validate-via-server and send the access request.
   * Why: The mailbox / SMTP path lives on Flask, not in the browser.
   * Who: The signup <form> onSubmit.
   * Where: /signup → /signup-sent with notifyEmail in location state.
   * How: api.signup; copy.signup.errorFallback if the request fails.
   */
  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await signup({ name, email, organization });
      nav("/signup-sent", {
        replace: true,
        state: { notifyEmail: res.notifyEmail, mocked: res.mocked },
      });
    } catch (err) {
      setError(err.message || c.errorFallback);
    } finally {
      setBusy(false);
    }
  }

  /**
   * What: Bind a text field to React state.
   * Why: Name, email, and organization inputs share the same change wiring.
   * Who: The three signup <input> onChange handlers.
   * Where: Signup card only.
   * How: Return a change handler closed over the given setter so the three inputs share one factory.
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

  const cardSub = notifyEmail
    ? fill(c.cardSubNotify, { notifyEmail })
    : c.cardSub;

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
          <p className="sub">{cardSub}</p>
          {error ? <div className="err" role="alert" id="signup-error">{error}</div> : null}
          <label htmlFor="name">{c.nameLabel} <span className="req">(required)</span></label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            required
            aria-required="true"
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "signup-error" : undefined}
            maxLength={120}
            value={name}
            onChange={onField(setName)}
          />
          <label htmlFor="email">{c.emailLabel} <span className="req">(required)</span></label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            aria-required="true"
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "signup-error" : undefined}
            value={email}
            onChange={onField(setEmail)}
          />
          <label htmlFor="organization">
            {c.organizationLabel} <span className="optional">{c.optional}</span>
          </label>
          <input
            id="organization"
            name="organization"
            type="text"
            autoComplete="organization"
            maxLength={200}
            value={organization}
            onChange={onField(setOrganization)}
          />
          <button className="btn" type="submit" disabled={busy}>
            {busy ? c.submitting : c.submit}
          </button>
          <p className="access-link">
            {c.signinPrompt} <Link to="/">{c.signinLink}</Link>
          </p>
        </form>
      </main>
      <Footer />
    </div>
  );
}
