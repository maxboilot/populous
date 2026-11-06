"""Reel vertical 1080x1920 (HyperFrames), pilote par un scenario JSON (variable REEL_SCENARIO) :
  {"scenes": [ {"type": "titre|chiffres|cartes|hemicycle|texte|liste", "duree": 4.0, ...} ], "fin": {...}, "source": "..."}
Scenes : titre (eyebrow, titre, tampon, couleur) | chiffres (titre, sous) | cartes (titre, sous, cartes [[titre, texte]]) | hemicycle (titre, sous)
         | texte (kicker, texte) | liste (titre, items) ; **mot** = mot mis en valeur. Les scenes « chiffres » et « hemicycle »
lisent le scrutin dans SIEGES_JSON (cf. commun/exporter_sieges.py). Usage : REEL_SCENARIO=... python3 construire.py"""
import html as H, json, os, re, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "commun"))
import blocs
SC = json.loads(Path(os.environ["REEL_SCENARIO"]).read_text(encoding="utf-8"))
SE = json.loads(Path(os.environ["SIEGES_JSON"]).read_text(encoding="utf-8")) if os.environ.get("SIEGES_JSON") else None
esc = lambda s: H.escape(str(s), quote=False)
md = lambda s: re.sub(r"\*\*(.+?)\*\*", r'<span class="k">\1</span>', esc(s))
def mots(texte, cl="w"):
    """Un <span> par mot (animation mot a mot) ; **a b** met en valeur plusieurs mots d'affilee (la ponctuation apres ** est permise)."""
    out, k = [], False
    for w in str(texte).split():
        ouvre = w.startswith("**"); ferme = w.rstrip(".,;:!?)»”…").endswith("**") and len(w.replace("**", "")) > 0
        if ouvre: k = True
        out.append(f'<span class="{cl}{" k" if k else ""}" style="display:inline-block">{esc(w.replace("**", ""))}</span>')
        if ferme and k: k = False
    return " ".join(out)
html_s, js_s, t = [], [], 0.0
FIN_D = float(SC.get("fin", {}).get("duree", 3.8))
taille = lambda n: (80, 98) if n <= 70 else (70, 86) if n <= 110 else (60, 76) if n <= 160 else (52, 66)
for i, s in enumerate(SC["scenes"]):
    d = float(s.get("duree", 4)); sid = f"sc{i}"; ty = s["type"]; h = [f'<div id="{sid}" class="sc v"><div class="in">']; j = [f'scene("#{sid}", {t:.2f}, {d});']
    if ty == "titre":
        col = {"vert": "rgb(69,150,109)", "orange": "rgb(255,140,80)"}.get(s.get("couleur", "orange"), "rgb(255,140,80)")
        n = len(s["titre"])
        if s.get("tampon"): sz, lh, ky, ty_ = (72, 88, 300, 372) if n <= 60 else (62, 76, 300, 372) if n <= 110 else (54, 66, 300, 372)
        else: sz, lh, ky, ty_ = (96, 114, 560, 640) if n <= 36 else (84, 100, 560, 640) if n <= 60 else (72, 88, 560, 640)     # titre pedagogique : grand, au centre
        h += [f'<div class="kick" id="{sid}e" style="top:{ky}px">{esc(s.get("eyebrow", ""))}</div>',
              f'<div class="ttl" id="{sid}t" style="top:{ty_}px;font-size:{sz}px;line-height:{lh}px">{mots(s["titre"])}</div>']
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'words("#{sid}t .w", {t + 0.3:.2f}, 0.06);']
        if s.get("tampon"):
            h.append(f'<div class="stamp" id="{sid}s" style="color:{col};border-color:{col}">{esc(s["tampon"])}</div>')
            ts = t + 1.7
            j += [f'tl.fromTo("#{sid}s", {{ scale: 2.6, opacity: 0, rotation: -5.7, transformOrigin: "50% 50%" }}, {{ scale: 1, opacity: 1, rotation: -5.7, duration: 0.18, ease: "power3.out" }}, {ts:.2f});',
                  f'tl.fromTo("#{sid}s", {{ x: 0 }}, {{ x: 0, keyframes: [{{ x: 16, duration: 0.05 }}, {{ x: -11, duration: 0.05 }}, {{ x: 6, duration: 0.05 }}, {{ x: 0, duration: 0.05 }}], immediateRender: false }}, {ts + 0.18:.2f});']
    elif ty == "chiffres":
        TY = SE["scrutin"]["tally"]; votants = TY["pour"] + TY["contre"] + TY["abstention"]
        bins = [{"k": k, "n": TY[k], "x": x} for k, x in (("pour", 170), ("contre", 410), ("abstention", 650), ("absent", 890))]
        lab = {"pour": "POUR", "contre": "CONTRE", "abstention": "ABSTENTION", "absent": "ABSENTS"}
        h += [f'<canvas id="{sid}c" width="1080" height="1920"></canvas>', f'<div class="c" id="{sid}n" style="top:300px;font-size:104px;color:#fff;letter-spacing:-.02em">{s.get("titre", f"{votants} votants.")}</div>',
              f'<div class="c" id="{sid}m" style="top:436px;font-size:64px;color:#A0B0F0">{esc(s.get("sous", "sur 577 députés."))}</div>']
        for b_i, b in enumerate(bins):
            h += [f'<div id="{sid}k{b_i}" class="cnt" style="left:{b["x"] - 120}px">0</div><div class="lab" style="left:{b["x"] - 120}px">{lab[b["k"]]}</div>']
        j += [f'blurIn_("#{sid}n", {t:.2f});', f'rise("#{sid}m", {t + 0.2:.2f}, 20, 0.4);',
              f'RAIN({json.dumps(bins)}, "{sid}c", "{sid}k", {t:.2f});']
    elif ty == "cartes":
        cs = s["cartes"]; ch = 250 if len(cs) == 3 else 300; gap = 20; y0 = 520 + (3 - len(cs)) * (ch + gap) // 2
        h += [f'<div class="c" id="{sid}n" style="top:300px;font-size:80px;color:#fff;letter-spacing:-.01em">{esc(s.get("titre", "De quoi parle ce texte ?"))}</div>',
              f'<div class="c" id="{sid}m" style="top:410px;font-size:40px;font-weight:500;color:#A0B0F0">{esc(s.get("sous", ""))}</div>']
        for k, (ct, cx) in enumerate(cs):
            h.append(f'<div class="ex" id="{sid}x{k}" style="top:{y0 + k * (ch + gap)}px;height:{ch}px"><div class="exe">{esc(ct)}</div><div class="ext">{md(cx)}</div></div>')
            j += [f'tl.fromTo("#{sid}x{k}", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + 0.8 + k * 0.9:.2f});']
        j += [f'blurIn_("#{sid}n", {t:.2f});', f'rise("#{sid}m", {t + 0.2:.2f}, 18, 0.4);']
    elif ty == "hemicycle":
        h += [f'<canvas id="{sid}c" width="1080" height="1920"></canvas>', f'<div class="c" id="{sid}n" style="top:300px;font-size:100px;color:#fff;letter-spacing:-.02em">{esc(s.get("titre", "Siège par siège."))}</div>',
              f'<div class="c" id="{sid}m" style="top:430px;font-size:44px;font-weight:500;color:#A0B0F0">{esc(s.get("sous", "Un point = un député"))}</div>']
        j += [f'blurIn_("#{sid}n", {t:.2f});', f'rise("#{sid}m", {t + 0.25:.2f}, 20, 0.4);', f'HEMI("{sid}c", {t:.2f});']
    elif ty == "texte":
        sz, lh = taille(len(s["texte"]))
        h += [f'<div class="kick" id="{sid}e" style="top:470px">{esc(s.get("kicker", ""))}</div>',
              f'<div class="big" id="{sid}t" style="top:552px;font-size:{sz}px;line-height:{lh}px">{mots(s["texte"])}</div>']
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'words("#{sid}t .w", {t + 0.35:.2f}, 0.07);']
    elif ty == "liste":
        its = s["items"]; rh = 150; g = 18
        h += [f'<div class="c" id="{sid}n" style="top:300px;font-size:72px;color:#fff;letter-spacing:-.01em">{esc(s["titre"])}</div>']
        for k, it in enumerate(its):
            txt, coul = (it, None) if isinstance(it, str) else (it[0], it[1])
            if coul: badge = f'<div class="num" style="background:{coul};border:4px solid rgba(255,255,255,.85);font-size:0">&nbsp;</div>'
            elif s.get("numerote"): badge = f'<div class="num">{k + 1}</div>'
            else: badge = '<div class="num" style="background:transparent"><div style="position:absolute;left:28px;top:28px;width:24px;height:24px;border-radius:50%;background:#8FA6FF"></div></div>'
            h.append(f'<div class="row" id="{sid}r{k}" style="top:{470 + k * (rh + g)}px">{badge}<div class="rt"><div>{md(txt)}</div></div></div>')
            j.append(f'tl.fromTo("#{sid}r{k}", {{ x: 90, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.5, ease: "power3.out" }}, {t + 0.7 + k * 0.55:.2f});')
        j += [f'blurIn_("#{sid}n", {t:.2f});']
    if SC.get("source") and i == len(SC["scenes"]) - 1:
        h.append(f'<div class="srcp" style="top:1360px">{esc(SC["source"])}</div>')
    h.append("</div></div>"); html_s += h; js_s += j; t += d
F = SC.get("fin", {})
fh, fj = blocs.finale(t - 0.3, (F.get("eyebrow", "Populous"), 430), [(F.get("ligne1", "Chaque scrutin,"), 66, 520, "var(--ink)"), (F.get("ligne2", "siège par siège."), 66, 610, "var(--accent)")],
                      (330, 1290), (180, 860, 1.0), [(F.get("accroche", "Chaque scrutin, sur Populous."), 44, 700, "var(--corps)", 1040, 1.6)], 1400, (F.get("source", "App gratuite, sans compte, sans publicité"), 1520, 2.4))
DUREE = t - 0.3 + FIN_D
JS_FUNCS = '''const blurIn_ = (sel, t0) => tl.fromTo(sel, { opacity: 0, filter: "blur(12px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }, t0);
function RAIN(BINS, cid, kid, t0) {
  const COLN = 12, DOT = 6.6, PIT = 16, BASE = 1180, DOTS = [];
  BINS.forEach((b, bi) => { for (let s = 0; s < b.n; s++) DOTS.push([bi, s]); });
  const rr = rng(4), ordre = DOTS.map((_, i) => i);
  for (let i = ordre.length - 1; i > 0; i--) { const j = Math.floor(rr() * (i + 1)); [ordre[i], ordre[j]] = [ordre[j], ordre[i]]; }
  const LAND = new Array(DOTS.length); ordre.forEach((idx, rank) => { LAND[idx] = 0.3 + 1.9 * Math.pow(rank / DOTS.length, 0.85); });
  const cv = document.getElementById(cid).getContext("2d"), els = BINS.map((b, i) => document.getElementById(kid + i));
  DRAW.push(T => {
    const lt = T - t0; cv.clearRect(0, 0, 1080, 1920); if (lt < 0 || lt > 12) return;
    cv.strokeStyle = "rgb(80,96,170)"; cv.lineWidth = 3; BINS.forEach(b => { cv.beginPath(); cv.moveTo(b.x - 100, BASE + 12); cv.lineTo(b.x + 100, BASE + 12); cv.stroke(); });
    const landed = BINS.map(() => 0);
    DOTS.forEach(([bi, s], i) => {
      const b = BINS[bi]; if (lt < LAND[i] - 0.42) return;
      const row = Math.floor(s / COLN), col = s % COLN, xt = b.x - (COLN - 1) * PIT / 2 + col * PIT + (row % 2) * 3, yt = BASE - row * PIT; let y;
      if (lt < LAND[i]) { const qq = (lt - (LAND[i] - 0.42)) / 0.42; y = 330 + (yt - 330) * qq * qq; } else { const e = lt - LAND[i]; y = yt - 5 * Math.exp(-e * 14) * Math.abs(Math.sin(e * 24)); landed[bi]++; }
      dot(cv, xt, y, DOT, V[b.k]);
    });
    els.forEach((el, i) => { el.textContent = landed[i]; });
  });
}
function HEMI(cid, t0) {
  const cv = document.getElementById(cid).getContext("2d"), NS = SE.A.length, AN = SE.A.map(a => (a + Math.PI / 2) / Math.PI), VOTE = SE.POS.map(p => V[p]);
  DRAW.push(T => {
    const lt = T - t0; cv.clearRect(0, 0, 1080, 1920); if (lt < 0) return;
    const qq = inOut(clamp(lt / 4.5)), wave = lerp(-0.3, 1.3, inOut(prog(lt, 0.3, 1.2))), cols = [], scal = [], ringa = [];
    for (let k = 0; k < NS; k++) {
      let m = clamp((wave - AN[k]) / 0.2); m = m * m * (3 - 2 * m); cols.push(mixc(SE.GRP[k], VOTE[k], m));
      const p = (lt > 0.3 && wave < 1.25) ? Math.exp(-Math.abs(wave - AN[k]) * 12) : 0; scal.push(1 + 0.5 * p); ringa.push(p);
    }
    hemiPersp(cv, SE, lerp(0.34, -0.26, qq), lerp(600, 700, qq), lerp(2.2, 1.4, qq), lerp(2.0, 1.5, qq), 540, lerp(640, 590, qq), cols, 0.05, scal, ringa);
  });
}'''
compact = {k: SE[k] for k in ("A", "R", "ROW", "GRP", "POS")} if SE else {"A": [], "R": [], "ROW": [], "GRP": [], "POS": []}
blocs.assembler(HERE, "modele.html", {"%%SCENES%%": "\n".join(html_s), "%%SCENES_JS%%": JS_FUNCS + "\n" + "\n".join(js_s), "%%FINALE_HTML%%": fh, "%%FINALE_JS%%": fj,
                "%%DUREE%%": f"{DUREE:.2f}", "%%SIEGES_JSON%%": json.dumps(compact)})
print(f"index.html : {len(SC['scenes'])} scenes + fin, {DUREE:.1f} s")
