import { useNavigate } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { useCopy } from "../copy.jsx";

/**
 * What: Session-ended scene after sign-out.
 * Why: Confirm the cookie is gone and offer a path back to sign in.
 * Who: Route /logged-out (auth_logout redirect).
 * Where: Depart scene; strings from copy.loggedOut.
 * How: Render copy; Sign in navigates to /.
 */
export default function LoggedOut() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.loggedOut;
  const nav = useNavigate();

  /**
   * What: Return to the login card.
   * Why: The only action on this page is to start a new session.
   * Who: “Sign in” button.
   * Where: Navigate to /.
   * How: Client-side navigate to the login route without a full reload.
   */
  function onSignIn() {
    nav("/");
  }

  return (
    <div className="stage" data-scene="logout">
      <Atmosphere scene="logout" />
      <a className="skip-link" href="#main">{brand.skipLink}</a>
      <BrandHeader />
      <main id="main" className="main">
        <section className="card">
          <p className="hero-kicker">{c.kicker}</p>
          <h1>{c.title}</h1>
          <p className="sub">{c.sub}</p>
          <button className="btn" type="button" onClick={onSignIn}>
            {c.signIn}
          </button>
        </section>
      </main>
      <Footer />
    </div>
  );
}
