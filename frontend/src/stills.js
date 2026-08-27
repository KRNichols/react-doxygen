/**
 * Shared F/A-18 Super Hornet still pack for Atmosphere page backgrounds.
 * Not used on /docs. Distinct from the leftover /heroes and earth files.
 */

export const F18_STILLS = [
  { src: "/stills/f18-01.jpg", alt: "F/A-18E Super Hornet launching from USS Carl Vinson" },
  { src: "/stills/f18-02.jpg", alt: "F/A-18 Super Hornet parked on a carrier flight deck" },
  { src: "/stills/f18-03.jpg", alt: "F/A-18 Super Hornet afterburner blast on the flight deck" },
  { src: "/stills/f18-04.jpg", alt: "F/A-18E Super Hornet breaking the sound barrier" },
  { src: "/stills/f18-05.jpg", alt: "F/A-18E Super Hornet preparing to launch from USS Harry S. Truman" },
  { src: "/stills/f18-06.jpg", alt: "F/A-18E Super Hornet launching from USS George Washington" },
  { src: "/stills/f18-07.jpg", alt: "F/A-18F Super Hornet of VFA-103 aboard USS Abraham Lincoln" },
];

/**
 * What: Pick one Super Hornet still from the shared pack.
 * Why: Login/success/denied/logout backgrounds rotate on reload without Hornet motion.
 * Who: Atmosphere on first render.
 * Where: frontend/src/stills.js, consumed by Atmosphere on non-docs stages.
 * How: Random index into F18_STILLS; the same object is kept until reload.
 */
export function pickStill() {
  return F18_STILLS[Math.floor(Math.random() * F18_STILLS.length)] || F18_STILLS[0];
}
