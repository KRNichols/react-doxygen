import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { useCopy } from "../copy.jsx";
import { me } from "../api.js";

/**
 * What: Access-denied scene after a verified but uncleared login.
 * Why: visitor@example.com is a completed login, not a 401.
 * Who: Route /denied; auth_callback when clearance is denied.
 * Where: Abort scene; strings from copy.denied.
 * How: GET /api/auth/me; bounce granted → /success and 401 → /.
 */
export default function Denied() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.denied;
  const nav = useNavigate();
  const [user, setUser] = useState(null);

  /**
   * What: Load the session and keep only non-granted users here.
   * Why: A granted cookie must not see the abort copy.
   * Who: Denied mount effect.
   * Where: GET /api/auth/me.
   * How: nav /success if granted; nav / if 401.
   */
  useEffect(() => {
    let cancelled = false;
    me()
      .then((data) => {
        if (cancelled) return;
        if (data.clearance === "granted") {
          nav("/success", { replace: true });
          return;
        }
        setUser(data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) nav("/", { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [nav]);

  /**
   * What: Return the visitor to the sign-in card.
   * Why: Denied is a finished login; they need a path back to try another account.
   * Who: “Return to sign in” button.
   * Where: Navigate to /.
   * How: Client-side navigate to the login route without a full reload.
   */
  function onReturn() {
    nav("/");
  }

  return (
    <div className="stage" data-scene="denied">
      <Atmosphere scene="denied" />
      <a className="skip-link" href="#main">{brand.skipLink}</a>
      <BrandHeader />
      <main id="main" className="main">
        <section className="card">
          <p className="hero-kicker">{c.kicker}</p>
          <h1>{c.title}</h1>
          <p className="sub">{c.sub}</p>
          {user ? (
            <div className="stats">
              <div className="stat"><span>{c.emailLabel}</span><b>{user.email}</b></div>
              <div className="stat"><span>{c.statusLabel}</span><b className="bad">{c.statusBad}</b></div>
            </div>
          ) : (
            <p className="sub">{c.checking}</p>
          )}
          <button className="btn ghost" type="button" onClick={onReturn}>
            {c.returnButton}
          </button>
        </section>
      </main>
      <Footer />
    </div>
  );
}
