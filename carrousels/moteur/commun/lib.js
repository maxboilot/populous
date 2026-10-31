/* Outils communs des films Populous : courbes, hémicycle (plat et en perspective), générateur pseudo-aléatoire stable. */
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const prog = (t, t0, d) => clamp((t - t0) / d);
const outCubic = p => 1 - Math.pow(1 - p, 3);
const outExpo = p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p));
const inOut = p => 3 * p * p - 2 * p * p * p;
const outBack = (p, s = 1.9) => { p -= 1; return 1 + (s + 1) * p * p * p + s * p * p; };
const lerp = (a, b, p) => a + (b - a) * p;
const rng = seed => () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const rgb = c => `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
const mixc = (a, b, p) => [lerp(a[0], b[0], p), lerp(a[1], b[1], p), lerp(a[2], b[2], p)];
const dot = (ctx, x, y, r, c) => { if (r < 0.4) return; ctx.fillStyle = rgb(c); ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832); ctx.fill(); };
/* hémicycle vu de face : positions plates */
const hemiPlat = (SE, cx, cy, s) => SE.A.map((a, i) => [cx + s * SE.R[i] * Math.sin(a), cy - s * SE.R[i] * Math.cos(a)]);
/* hémicycle en perspective (même projection que le moteur Python) */
function hemiPersp(ctx, SE, yaw, f, recul, camh, cx, cy, cols, rayon, scal, ringa) {
  const n = SE.A.length, cs = Math.cos(yaw), sn = Math.sin(yaw), P = [];
  for (let k = 0; k < n; k++) {
    const X = SE.R[k] * Math.sin(SE.A[k]), Zc = SE.R[k] * Math.cos(SE.A[k]) + recul;
    const Xr = X * cs - Zc * sn, Zr = X * sn + Zc * cs;
    if (Zr <= 0.5) continue;
    P.push([k, Zr, cx + f * Xr / Zr, cy + f * (camh - 0.11 * SE.ROW[k]) / Zr, f * rayon / Zr]);
  }
  P.sort((a, b) => b[1] - a[1]);
  for (const [k, Zr, x, y, rr] of P) {
    const r = rr * (scal ? scal[k] : 1);
    if (x < -r || x > 1080 + r || y < -r || y > 1920 + r) continue;
    dot(ctx, x, y, r, cols[k]);
    if (ringa && ringa[k] > 0.05 && r < 22) { ctx.strokeStyle = "#fff"; ctx.lineWidth = Math.max(1, r * 0.15); ctx.beginPath(); ctx.arc(x, y, r * (1.3 + 1.2 * (1 - ringa[k])), 0, 6.2832); ctx.stroke(); }
  }
}
