/* Socle des carrousels : modes slide / preview / pano, caméra, horloge pour les canvas. */
const MODE = "%%MODE%%", IDX = %%IDX%%, SW = 1080, DURATION = %%DUR%%;
const tl = gsap.timeline({ paused: true });
const A = MODE === "preview" ? [0, 3.3, 6.6, 9.9, 13.2] : [0, 0, 0, 0, 0];          // instant d'arrivée de chaque slide
const st = i => (MODE === "preview" ? (i === 0 ? 0.2 : A[i] - 0.35) : 0.2);          // début de l'animation de la slide i
const on = i => MODE !== "slide" || i === IDX;
const q = s => gsap.utils.toArray(s);
const S = { t: 0 };
if (MODE === "slide") gsap.set("#cam", { x: -IDX * SW });
if (MODE === "preview") { gsap.set("#cam", { x: 0 }); for (let i = 1; i < 5; i++) tl.to("#cam", { x: -i * SW, duration: 0.9, ease: "power3.inOut" }, A[i] - 0.9); }
const chipArrow = (sel, t0) => tl.to(sel, { x: 12, duration: 0.45, ease: "sine.inOut", yoyo: true, repeat: 7 }, t0);
const pop = (sel, t0, d = 0.6) => tl.fromTo(sel, { scale: 0.4, opacity: 0, transformOrigin: "50% 50%" }, { scale: 1, opacity: 1, duration: d, ease: "back.out(1.7)", stagger: 0.1 }, t0);
const rise = (sel, t0, y = 30, d = 0.5, stg = 0.1) => tl.fromTo(sel, { y, opacity: 0 }, { y: 0, opacity: 1, duration: d, ease: "power3.out", stagger: stg }, t0);
const blurIn = (sel, t0, dx = 0, d = 0.5, stg = 0.1) => tl.fromTo(sel, { x: dx, opacity: 0, filter: "blur(12px)" }, { x: 0, opacity: 1, filter: "blur(0px)", duration: d, ease: "expo.out", stagger: stg }, t0);
const words = (sel, t0, stg = 0.05) => tl.fromTo(sel, { y: 40, opacity: 0, filter: "blur(8px)" }, { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out", stagger: stg }, t0);
/* Vignette d'ouverture (slide 1, video) : l'image 0 EST la slide terminee (c'est elle qu'Instagram prend pour la miniature de la grille),
   puis un fondu rapide et l'animation d'entree se joue. Les autres slides et les modes preview / pano ne changent pas. */
const POSTER = MODE === "slide" && IDX === 0 ? { hold: 0.14, fade: 0.2, final: 6.2 } : null;
if (POSTER) {
  const cam = document.getElementById("cam"), fg = document.createElement("div");
  fg.id = "fg"; fg.style.cssText = "position:absolute;left:0;top:0;width:5400px;height:1350px";
  Array.from(cam.children).filter(e => !e.classList.contains("abs")).forEach(e => fg.appendChild(e));   // tout sauf les fonds
  cam.appendChild(fg);
}
function fin(tick) {
  tl.to(S, { t: DURATION, duration: DURATION, ease: "none", onUpdate: tick || (() => {}) }, 0);
  window.__timelines = window.__timelines || {};
  if (!POSTER) { window.__timelines["main"] = tl; tl.seek(0); return; }
  const P = POSTER.hold + POSTER.fade, master = gsap.timeline({ paused: true }), px = { t: 0 };
  const rendre = () => {
    const t = px.t, a = t < POSTER.hold ? 1 : t < P ? 1 - (t - POSTER.hold) / POSTER.fade : 1;
    gsap.set("#fg", { opacity: a, filter: t >= POSTER.hold && t < P ? "blur(" + (8 * (1 - a)).toFixed(2) + "px)" : "none" });
    tl.time(t < P ? POSTER.final : t - P, false);              // avant le fondu : slide terminee ; apres : l'animation d'entree, depuis le debut
  };
  master.to(px, { t: DURATION, duration: DURATION, ease: "none", onUpdate: rendre }, 0);
  window.__timelines["main"] = master;
  master.seek(0); rendre();
}
