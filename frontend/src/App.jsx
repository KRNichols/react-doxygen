import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Success from "./pages/Success.jsx";
import Denied from "./pages/Denied.jsx";
import LoggedOut from "./pages/LoggedOut.jsx";
import Signup from "./pages/Signup.jsx";
import SignupSent from "./pages/SignupSent.jsx";
import Docs from "./pages/Docs.jsx";

/**
 * What: Move keyboard focus to the new page main after a route change.
 * Why: WCAG 2.4.3 — SPA navigation must not leave focus on a gone control.
 * Who: App on every BrowserRouter pathname change.
 * Where: The screen main landmark (tabIndex -1), not the heading box.
 * How: querySelector main then h1 fallback; focus with preventScroll so no fat outline box.
 */
function FocusOnRoute() {
  const location = useLocation();
  useEffect(() => {
    const target = document.querySelector("main") || document.querySelector("h1");
    if (!target) return;
    target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
  }, [location.pathname]);
  return null;
}

/**
 * What: Top-level route table for the portal screens.
 * Why: Each scene (login, signup, granted, denied, out) is its own page.
 * Who: main.jsx via <App />.
 * Where: Browser paths /, /login, /signup, /signup-sent, /success, /docs, /denied, /logged-out.
 * How: react-router Routes; unknown paths Navigate to /; FocusOnRoute after paint.
 */
export default function App() {
  return (
    <>
      <FocusOnRoute />
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/signup-sent" element={<SignupSent />} />
        <Route path="/success" element={<Success />} />
        <Route path="/docs/*" element={<Docs />} />
        <Route path="/docs" element={<Docs />} />
        <Route path="/denied" element={<Denied />} />
        <Route path="/logged-out" element={<LoggedOut />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
