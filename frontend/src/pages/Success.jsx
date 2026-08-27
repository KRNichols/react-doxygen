import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { fill, useCopy } from "../copy.jsx";
import { logout, me } from "../api.js";

/**
 * What: Access-granted scene after a cleared login.
 * Why: Authorized demo users (HornetReady1) land here with session details.
 * Who: Route /success (Denied bounces granted sessions here); auth_callback and JSON login land on /docs.
 * Where: Flyby scene; strings from copy.success.
 * How: GET /api/auth/me; bounce denied → /denied and 401 → /.
 */
export default function Success() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.success;
  const nav = useNavigate();
  const [user, setUser] = useState(null);

  /**
   * What: Load the session and keep only granted users on this page.
   * Why: Deep links to /success must not show a visitor as authorized.
   * Who: Success mount effect.
   * Where: GET /api/auth/me.
   * How: nav /denied if not granted; nav / if 401.
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
      });
    return () => {
      cancelled = true;
    };
  }, [nav]);

  /**
   * What: Clear the session and go to the signed-out scene.
   * Why: The granted card must offer a way to end the cookie session.
   * Who: “Sign out” button.
   * Where: POST /api/auth/logout then /logged-out.
   * How: api.logout (ignore errors) then navigate.
   */
  async function onLogout() {
    await logout().catch(() => {});
    nav("/logged-out");
  }

  return (
    <div className="stage" data-scene="success">
      <Atmosphere scene="success" />
      <a className="skip-link" href="#main">{brand.skipLink}</a>
      <BrandHeader />
      <main id="main" className="main">
        <section className="card wide">
          <p className="hero-kicker">{c.kicker}</p>
          <h1>{c.title}</h1>
          <p className="sub">
            {user ? fill(c.sub, { name: user.name }) : c.checking}
          </p>
          {user ? (
            <div className="stats">
              <div className="stat"><span>{c.emailLabel}</span><b>{user.email}</b></div>
              <div className="stat"><span>{c.displayNameLabel}</span><b>{user.callsign}</b></div>
              <div className="stat"><span>{c.statusLabel}</span><b className="ok">{c.statusOk}</b></div>
            </div>
          ) : null}
          <button className="btn" type="button" onClick={() => nav("/docs")}>
            {c.openDocs || "Open documentation"}
          </button>
          <button className="btn ghost" type="button" onClick={onLogout}>
            {c.signOut}
          </button>
        </section>
      </main>
      <Footer />
    </div>
  );
}
