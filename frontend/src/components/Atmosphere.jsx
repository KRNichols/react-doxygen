import { useState } from "react";
import { pickStill } from "../stills.js";

/**
 * What: Full-stage background still from the expanded F-18 pack.
 * Why: Every page background should flip through Super Hornet photos on reload, not recycled heroes.
 * Who: Login, Signup, SignupSent, Success, Denied, LoggedOut.
 * Where: First child of .stage; CSS sizes the img and paints the navy overlay.
 * How: pickStill once per mount; decorative img with aria-hidden; no motion.
 */
export default function Atmosphere({ scene = "login" }) {
  const [shot] = useState(() => pickStill());
  return (
    <div className="stage-bg" data-scene={scene} aria-hidden="true">
      {shot && shot.src ? <img src={shot.src} alt="" /> : null}
    </div>
  );
}
