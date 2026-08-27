import { Link, useLocation } from "react-router-dom";
import Atmosphere from "../components/Atmosphere.jsx";
import BrandHeader, { Footer } from "../components/BrandHeader.jsx";
import { fill, useCopy } from "../copy.jsx";

/**
 * What: Confirmation that the access request was emailed.
 * Why: Applicants need proof their details went to the program contact.
 * Who: Route /signup-sent after a successful Signup submit.
 * Where: Hold scene; strings from copy.signupSent.
 * How: Prefer location.state.notifyEmail, else copy.notifyEmail from /api/copy.
 */
export default function SignupSent() {
  const copy = useCopy();
  const brand = copy.brand;
  const c = copy.signupSent;
  const location = useLocation();
  const notifyEmail = location.state?.notifyEmail || copy.notifyEmail || "";
  const sub = notifyEmail ? fill(c.subNotify, { notifyEmail }) : c.sub;

  return (
    <div className="stage" data-scene="login">
      <Atmosphere scene="login" />
      <a className="skip-link" href="#main">{brand.skipLink}</a>
      <BrandHeader />
      <main id="main" className="main">
        <section className="card">
          <p className="hero-kicker">{c.kicker}</p>
          <h1>{c.title}</h1>
          <p className="sub">{sub}</p>
          <Link className="btn ghost" to="/">
            {c.returnButton}
          </Link>
        </section>
      </main>
      <Footer />
    </div>
  );
}
