"""Reel vertical 1080x1920 (HyperFrames), pilote par un scenario JSON (variable REEL_SCENARIO) :
  {"scenes": [ {"type": "titre|chiffres|cartes|hemicycle|texte|liste", "duree": 4.0, ...} ], "fin": {...}, "source": "..."}
Scenes : titre (eyebrow, titre, tampon, couleur) | chiffres (titre, sous) | cartes (titre, sous, cartes [[titre, texte]]) | hemicycle (titre, sous)
         | texte (kicker, texte) | liste (titre, items) ; **mot** = mot mis en valeur. Les scenes « chiffres » et « hemicycle »
lisent le scrutin dans SIEGES_JSON (cf. commun/exporter_sieges.py). Usage : REEL_SCENARIO=... python3 construire.py"""
import html as H, json, os, re, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "commun"))
import blocs, lecture
SC = json.loads(Path(os.environ["REEL_SCENARIO"]).read_text(encoding="utf-8"))
SE = json.loads(Path(os.environ["SIEGES_JSON"]).read_text(encoding="utf-8")) if os.environ.get("SIEGES_JSON") else None
esc = lambda s: H.escape(str(s), quote=False)
rgb = lambda c: f"rgb({c[0]},{c[1]},{c[2]})"
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

def bleuet_svg(sid, w, h):
    """Bleuet dessine en SVG (coordonnees absolues, viewBox 600x800) : tige, feuilles, deux couronnes de fleurons dentes, coeur violet. Renvoie (svg, js)."""
    import math
    def fleuron(cx, cy, ang, L, W, dec=0.0):
        pts = [(-W * .16, -L * .22), (W * .16, -L * .22), (W * .55, -L * .72), (W * .72, -L * .92), (W * .46, -L * .97), (W * .34, -L * .84), (W * .16, -L * 1.04), (0, -L * .88),
               (-W * .16, -L * 1.04), (-W * .34, -L * .84), (-W * .46, -L * .97), (-W * .72, -L * .92), (-W * .55, -L * .72)]
        a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
        return "M" + " L".join(f"{cx + x * ca - (y + dec) * sa:.1f} {cy + x * sa + (y + dec) * ca:.1f}" for x, y in pts) + "Z"
    CX, CY = 300, 290; out = [f'<svg id="{sid}f" class="abs" viewBox="0 0 600 800" width="{w}" height="{h}" style="overflow:visible"><defs>'
        '<linearGradient id="gb1" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#1B2FB0"/><stop offset="1" stop-color="#5E7DFF"/></linearGradient>'
        '<linearGradient id="gb2" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#2E48D8"/><stop offset="1" stop-color="#8FA9FF"/></linearGradient></defs>'
        f'<g id="{sid}g">',
        f'<path id="{sid}st" d="M300 350 C 296 480, 318 620, 292 790" fill="none" stroke="#3F9A63" stroke-width="15" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>',
        f'<path class="{sid}lf" d="M304 560 C 360 520, 430 520, 468 470 C 440 560, 372 590, 304 580 Z" fill="#4FB27A" transform-origin="304 570"/>',
        f'<path class="{sid}lf" d="M300 660 C 240 630, 170 640, 132 590 C 160 680, 230 710, 298 690 Z" fill="#46A36E"/>']
    n1, n2 = 13, 13
    for k in range(n1): out.append(f'<path class="{sid}p1" d="{fleuron(CX, CY, k * 360 / n1, 200, 62)}" fill="url(#gb1)" stroke="#1B2FB0" stroke-width="1.5" stroke-linejoin="round"/>')
    for k in range(n2): out.append(f'<path class="{sid}p2" d="{fleuron(CX, CY, (k + .5) * 360 / n2, 150, 52)}" fill="url(#gb2)" stroke="#2E48D8" stroke-width="1.2" stroke-linejoin="round"/>')
    out.append(f'<circle class="{sid}cr" cx="{CX}" cy="{CY}" r="46" fill="#2B1F7A"/>')
    for k in range(18):
        r = 8 + 30 * ((k * 7) % 10) / 10; a = k * 2.399; x, y = CX + r * math.cos(a), CY + r * math.sin(a)
        out.append(f'<circle class="{sid}cc" cx="{x:.1f}" cy="{y:.1f}" r="{5 + (k % 3)}" fill="{"#D2549F" if k % 3 == 0 else "#7A52D6"}"/>')
    out.append('</g></svg>')
    js = [f'(function(){{ const T0 = %T0%; const P1 = gsap.utils.toArray("#{sid}f .{sid}p1"), P2 = gsap.utils.toArray("#{sid}f .{sid}p2"), CC = gsap.utils.toArray("#{sid}f .{sid}cc");',
          f'  tl.to("#{sid}st", {{ strokeDashoffset: 0, duration: 1.0, ease: "power2.inOut" }}, T0 + 0.1);',
          f'  tl.fromTo("#{sid}f .{sid}lf", {{ scale: 0, opacity: 0, svgOrigin: "300 600" }}, {{ scale: 1, opacity: 1, duration: 0.7, ease: "back.out(1.6)", stagger: 0.18, svgOrigin: "300 600" }}, T0 + 0.7);',
          f'  tl.fromTo("#{sid}f .{sid}cr", {{ scale: 0, opacity: 0, svgOrigin: "300 290" }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "back.out(2)", svgOrigin: "300 290" }}, T0 + 0.9);',
          f'  P1.forEach((e, k) => tl.fromTo(e, {{ scale: 0, opacity: 0, svgOrigin: "300 290" }}, {{ scale: 1, opacity: 1, duration: 0.75, ease: "back.out(1.5)", svgOrigin: "300 290" }}, T0 + 1.0 + k * 0.06));',
          f'  P2.forEach((e, k) => tl.fromTo(e, {{ scale: 0, opacity: 0, svgOrigin: "300 290" }}, {{ scale: 1, opacity: 1, duration: 0.7, ease: "back.out(1.7)", svgOrigin: "300 290" }}, T0 + 1.5 + k * 0.05));',
          f'  CC.forEach((e, k) => tl.fromTo(e, {{ scale: 0, opacity: 0, svgOrigin: "300 290" }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(3)", svgOrigin: "300 290" }}, T0 + 2.0 + k * 0.03));',
          f'  tl.fromTo("#{sid}g", {{ rotation: -2.2, svgOrigin: "300 790" }}, {{ rotation: 2.2, svgOrigin: "300 790", duration: 3.2, ease: "sine.inOut", yoyo: true, repeat: 3 }}, T0 + 2.4); }})();']
    return "".join(out), "\n".join(js)

html_s, js_s, t = [], [], 0.0
FIN_D = float(SC.get("fin", {}).get("duree", 3.8))
taille = lambda n: (80, 98) if n <= 70 else (70, 86) if n <= 110 else (60, 76) if n <= 160 else (52, 66)
for i, s in enumerate(SC["scenes"]):
    d = max(float(s.get("duree", 4)), lecture.duree_min(s)); sid = f"sc{i}"; ty = s["type"]; h = [f'<div id="{sid}" class="sc v"><div class="in">']; j = [f'scene("#{sid}", {t:.2f}, {d});']
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
        dl = lecture.delais_items(s)[0]; cs = s["cartes"]; ch = 250 if len(cs) == 3 else 300; gap = 20; y0 = 520 + (3 - len(cs)) * (ch + gap) // 2
        h += [f'<div class="c" id="{sid}n" style="top:300px;font-size:80px;color:#fff;letter-spacing:-.01em">{esc(s.get("titre", "De quoi parle ce texte ?"))}</div>',
              f'<div class="c" id="{sid}m" style="top:410px;font-size:40px;font-weight:500;color:#A0B0F0">{esc(s.get("sous", ""))}</div>']
        for k, (ct, cx) in enumerate(cs):
            h.append(f'<div class="ex" id="{sid}x{k}" style="top:{y0 + k * (ch + gap)}px;height:{ch}px"><div class="exe">{esc(ct)}</div><div class="ext">{md(cx)}</div></div>')
            j += [f'tl.fromTo("#{sid}x{k}", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + dl[k]:.2f});']
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
        dl = lecture.delais_items(s)[0]; its = s["items"]; rh = 150; g = 18
        if s.get("parcours"):
            for k in range(1, len(its)):
                h.append(f'<div id="{sid}cn{k}" class="abs" style="left:135px;top:{470 + (k - 1) * (rh + g) + 115}px;width:6px;height:{rh + g - 80}px;background:#4668FF;border-radius:3px;transform-origin:50% 0;transform:scaleY(0)"></div>')
                j.append(f'tl.fromTo("#{sid}cn{k}", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.35, ease: "power2.inOut" }}, {t + dl[k] - 0.3:.2f});')
        h += [f'<div class="c" id="{sid}n" style="top:300px;font-size:72px;color:#fff;letter-spacing:-.01em">{esc(s["titre"])}</div>']
        for k, it in enumerate(its):
            txt, coul = (it, None) if isinstance(it, str) else (it[0], it[1])
            if coul: badge = f'<div class="num" style="background:{coul};border:4px solid rgba(255,255,255,.85);font-size:0">&nbsp;</div>'
            elif s.get("numerote"): badge = f'<div class="num">{k + 1}</div>'
            else: badge = '<div class="num" style="background:transparent"><div style="position:absolute;left:28px;top:28px;width:24px;height:24px;border-radius:50%;background:#8FA6FF"></div></div>'
            h.append(f'<div class="row" id="{sid}r{k}" style="top:{470 + k * (rh + g)}px">{badge}<div class="rt"><div>{md(txt)}</div></div></div>')
            j.append(f'tl.fromTo("#{sid}r{k}", {{ x: 90, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.5, ease: "power3.out" }}, {t + dl[k]:.2f});')
        j += [f'blurIn_("#{sid}n", {t:.2f});']
    elif ty == "chiffre":
        ring = bool(s.get("anneau")); cy = 800 if ring else 770; nz = 250 if ring else 320; N = int(s["nombre"])
        h.append(f'<div class="kick" id="{sid}e" style="top:340px;left:0;width:1080px;text-align:center">{esc(s.get("kicker", ""))}</div>')
        if ring:
            h.append(f'<svg class="abs" width="760" height="760" viewBox="0 0 760 760" style="left:160px;top:{cy - 380}px"><circle cx="380" cy="380" r="350" fill="none" stroke="rgba(160,180,255,.18)" stroke-width="24"/>'
                     f'<circle id="{sid}ring" cx="380" cy="380" r="350" fill="none" stroke="#4668FF" stroke-width="24" stroke-linecap="round" stroke-dasharray="2199.1" stroke-dashoffset="2199.1" transform="rotate(-90 380 380)"/></svg>')
        h += [f'<div class="c" id="{sid}n" style="top:{cy - nz // 2 - 10}px;font-size:{nz}px;line-height:{nz}px;color:#fff;letter-spacing:-.04em">0</div>',
              f'<div class="c" id="{sid}u" style="top:{cy + (110 if ring else 215)}px;font-size:{60 if not ring else 56}px;font-weight:800;color:#8FA6FF">{esc(s.get("unite", ""))}</div>',
              f'<div class="c" id="{sid}m" style="top:{1280 if ring else 1180}px;font-size:42px;font-weight:500;color:#C5D0FF">{md(s["sous"]) if s.get("sous") else ""}</div>']
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'rise("#{sid}u", {t + 1.2:.2f}, 20, 0.4);', f'rise("#{sid}m", {t + 1.9:.2f}, 20, 0.4);',
              f'(function(){{ const el = document.getElementById("{sid}n"); DRAW.push(T => {{ el.textContent = Math.round({N} * outExpo(clamp((T - {t:.2f} - 0.3) / 1.3))); }}); }})();']
        if ring: j.append(f'tl.fromTo("#{sid}ring", {{ strokeDashoffset: 2199.1 }}, {{ strokeDashoffset: 0, duration: 2.4, ease: "power2.inOut" }}, {t + 0.3:.2f});')
    elif ty == "points":
        gs = s["groupes"]; N = sum(g["n"] for g in gs); cols = 7 if N <= 20 else round((N * 1.38) ** 0.5); rows = -(-N // cols)
        pitch = min(940 / cols, 700 / rows, 120); r = min(pitch * 0.40, 50); x0 = (1080 - cols * pitch) / 2 + pitch / 2; y0 = 540 + (700 - rows * pitch) / 2 + pitch / 2
        pts, fins, i, D = [], [], 0, 2.6
        for g in gs:
            for _ in range(g["n"]):
                rw, cl = divmod(i, cols); pts.append([round(x0 + cl * pitch, 1), round(y0 + rw * pitch, 1), round(r, 1), round(0.4 + D * (i / N) ** 0.9, 2), g["couleur"]]); i += 1
            fins.append(0.4 + D * ((i - 1) / N) ** 0.9 + 0.35)
        h += [f'<canvas id="{sid}c" width="1080" height="1920"></canvas>', f'<div class="kick" id="{sid}e" style="top:330px;left:0;width:1080px;text-align:center">{esc(s.get("kicker", ""))}</div>']
        if s.get("titre"): h.append(f'<div class="c" id="{sid}n" style="top:400px;font-size:68px;color:#fff;letter-spacing:-.01em">{md(s["titre"])}</div>')
        ly = 1290
        for gi, g in enumerate(gs):
            if not g.get("label"): continue
            h.append(f'<div class="abs" id="{sid}l{gi}" style="left:0;width:1080px;top:{ly}px;display:flex;justify-content:center;align-items:center;gap:24px;font-size:46px;line-height:1;white-space:nowrap;color:#fff">'
                     f'<span style="width:34px;height:34px;border-radius:50%;background:{rgb(g["couleur"])}"></span><span>{md(g["label"])}</span></div>')
            j.append(f'rise("#{sid}l{gi}", {t + fins[gi]:.2f}, 22, 0.45);'); ly += 78
        if s.get("sous"): h.append(f'<div class="c" id="{sid}m" style="top:{ly + 20}px;font-size:40px;font-weight:500;color:#A0B0F0">{md(s["sous"])}</div>'); j.append(f'rise("#{sid}m", {t + fins[-1] + 0.5:.2f}, 18, 0.45);')
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'blurIn_("#{sid}n", {t + 0.2:.2f});' if s.get("titre") else '',
              f'(function(){{ const cv = document.getElementById("{sid}c").getContext("2d"), P = {json.dumps(pts)}; DRAW.push(T => {{ const lt = T - {t:.2f}; cv.clearRect(0, 0, 1080, 1920); if (lt < 0) return;'
              f' P.forEach(p => {{ const a = lt - p[3]; if (a < 0) return; const k = outBack(clamp(a / 0.28)); cv.fillStyle = rgb(p[4]); cv.beginPath(); cv.arc(p[0], p[1], p[2] * k, 0, 6.2832); cv.fill(); }}); }}); }})();']
    elif ty == "etapes":
        its = s["etapes"]; n = len(its); hb = 300 if n <= 2 else 250; gp = 100; tot = n * hb + (n - 1) * gp; y0 = (500 if s.get("titre") else 420) + (1000 - tot) // 2
        dl = lecture.delais_items(s)[0]; lock = bool(s.get("verrou")); coche = bool(s.get("coche", lock))
        if s.get("titre"): h.append(f'<div class="c" id="{sid}n" style="top:320px;font-size:64px;color:#fff;letter-spacing:-.01em">{esc(s["titre"])}</div>'); j.append(f'blurIn_("#{sid}n", {t:.2f});')
        for k, it in enumerate(its):
            top = y0 + k * (hb + gp)
            h.append(f'<div class="ex" id="{sid}x{k}" style="top:{top}px;height:{hb}px"><div class="exe">{esc(it.get("kicker", ""))}</div>'
                     f'<div class="ext" style="top:80px;font-size:50px;line-height:58px;font-weight:800">{md(it["titre"])}<div style="font-size:34px;line-height:44px;font-weight:500;color:#BECAFF;margin-top:12px">{md(it.get("sous", ""))}</div></div>'
                     f'<div id="{sid}ck{k}" class="abs" style="right:34px;top:30px;width:64px;height:64px;opacity:0"><svg viewBox="0 0 64 64" width="64" height="64"><circle cx="32" cy="32" r="30" fill="rgb(69,150,109)"/><path d="M18 33 l10 10 l19 -22" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg></div>'
                     + (f'<div id="{sid}lk{k}" class="abs" style="right:34px;top:30px;width:64px;height:64px"><svg viewBox="0 0 64 64" width="64" height="64"><rect x="12" y="28" width="40" height="30" rx="7" fill="#8FA6FF"/><path d="M20 28 v-8 a12 12 0 0 1 24 0 v8" fill="none" stroke="#8FA6FF" stroke-width="6"/></svg></div>' if lock and k else '') + '</div>')
            if k: h.append(f'<div id="{sid}ar{k}" class="abs" style="left:480px;top:{top - gp + 28}px;width:120px;height:44px;opacity:0"><svg width="120" height="44" viewBox="0 0 120 44"><path d="M30 8 L60 36 L90 8" fill="none" stroke="#8FA6FF" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg></div>')
            if k == 0 or not lock: j.append(f'tl.fromTo("#{sid}x{k}", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + dl[k]:.2f});')
            else:
                j += [f'tl.fromTo("#{sid}x{k}", {{ y: 40, opacity: 0, scale: 0.96 }}, {{ y: 0, opacity: 0.32, scale: 1, duration: 0.5, ease: "power3.out" }}, {t + dl[0] + 0.6:.2f});',
                      f'tl.to("#{sid}x{k}", {{ opacity: 1, duration: 0.45, ease: "power2.out" }}, {t + dl[k]:.2f});',
                      f'tl.to("#{sid}lk{k}", {{ scale: 0, rotation: -25, opacity: 0, duration: 0.35, ease: "back.in(2)", transformOrigin: "50% 50%" }}, {t + dl[k]:.2f});']
            if k: j.append(f'tl.fromTo("#{sid}ar{k}", {{ y: -14, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: "power3.out" }}, {t + dl[k] - 0.25:.2f});')
            if coche and k: j.append(f'tl.fromTo("#{sid}ck{k - 1}", {{ scale: 0, opacity: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(2.6)" }}, {t + dl[k] - 0.35:.2f});')
    elif ty == "compare":
        g, dr, bas = s["gauche"], s["droite"], s.get("bas"); dl = lecture.delais_items(s)[0]; ch = 400 if bas else 470
        if s.get("titre"): h.append(f'<div class="c" id="{sid}n" style="top:320px;font-size:64px;color:#fff;letter-spacing:-.01em">{esc(s["titre"])}</div>'); j.append(f'blurIn_("#{sid}n", {t:.2f});')
        for k, (c, lx, col) in enumerate(((g, 70, "#FFB27A"), (dr, 560, "#8FA6FF"))):
            h.append(f'<div class="ex" id="{sid}x{k}" style="left:{lx}px;width:450px;top:470px;height:{ch}px"><div class="exe" style="color:{col}">{esc(c.get("kicker", ""))}</div>'
                     f'<div class="ext" style="top:90px;width:380px;font-size:52px;line-height:60px;font-weight:800">{md(c["titre"])}<div style="font-size:36px;line-height:46px;font-weight:500;color:#BECAFF;margin-top:16px">{md(c.get("sous", ""))}</div></div></div>')
            j.append(f'tl.fromTo("#{sid}x{k}", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + dl[k]:.2f});')
        if bas:
            h += [f'<div id="{sid}ar" class="abs" style="left:0;width:1080px;top:{470 + ch + 8}px;height:90px;opacity:0"><svg width="1080" height="90" viewBox="0 0 1080 90"><path d="M295 10 L295 40 L540 40 L540 76 M785 10 L785 40 L540 40" fill="none" stroke="#8FA6FF" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg></div>',
                  f'<div class="ex" id="{sid}x2" style="top:{470 + ch + 110}px;height:250px"><div class="exe">{esc(bas.get("kicker", ""))}</div><div class="ext" style="top:56px;font-size:50px;line-height:58px;font-weight:800">{md(bas["titre"])}<div style="font-size:36px;line-height:46px;font-weight:500;color:#BECAFF;margin-top:12px">{md(bas.get("sous", ""))}</div></div></div>']
            j += [f'tl.fromTo("#{sid}ar", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {t + dl[2] - 0.3:.2f});',
                  f'tl.fromTo("#{sid}x2", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + dl[2]:.2f});']
    elif ty == "mois":
        M = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
        h.append(f'<div class="kick" id="{sid}e" style="top:330px;left:0;width:1080px;text-align:center">{esc(s.get("kicker", ""))}</div>')
        for m, nom in enumerate(M):
            lx, ty_ = 71 + (m % 4) * 241, 460 + (m // 4) * 241
            h.append(f'<div class="ex" id="{sid}t{m}" style="left:{lx}px;width:215px;top:{ty_}px;height:215px;border-radius:34px"><div class="c" style="left:0;width:215px;top:48px;font-size:52px;color:#fff">{nom}</div>'
                     f'<div id="{sid}d{m}" class="c" style="left:0;width:215px;top:132px;font-size:30px;font-weight:700;color:#8FA6FF">1 jour</div></div>')
            j += [f'tl.fromTo("#{sid}t{m}", {{ scale: 0.6, opacity: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.8)" }}, {t + 0.5 + m * 0.17:.2f});',
                  f'tl.fromTo("#{sid}d{m}", {{ scale: 0.4, opacity: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(3)" }}, {t + 0.85 + m * 0.17:.2f});']
        h += [f'<div class="c" id="{sid}n" style="top:1245px;font-size:60px;color:#fff;letter-spacing:-.01em">{md(s.get("titre", ""))}</div>', f'<div class="c" id="{sid}m" style="top:1335px;font-size:40px;font-weight:500;color:#A0B0F0">{md(s.get("sous", ""))}</div>']
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'blurIn_("#{sid}n", {t + 3.0:.2f});', f'rise("#{sid}m", {t + 3.4:.2f}, 18, 0.45);']
    elif ty == "bleuet":
        tr_ = ""
        if s.get("texte"):          # variante texte : petit bleuet en haut, kicker + texte dessous
            svg, jf = bleuet_svg(sid, 420, 560); sz, lh = taille(len(s["texte"]))
            h += [f'<div class="abs" style="left:330px;top:90px;width:420px;height:560px">{svg}</div>', f'<div class="kick" id="{sid}e" style="top:730px">{esc(s.get("kicker", ""))}</div>',
                  f'<div class="big" id="{sid}t" style="top:812px;font-size:{sz - 8}px;line-height:{lh - 8}px">{mots(s["texte"])}</div>']
            j += [jf.replace("%T0%", f"{t:.2f}"), f'rise("#{sid}e", {t + 0.3:.2f}, -16, 0.4);', f'words("#{sid}t .w", {t + 0.6:.2f}, 0.07);']
        else:                       # variante titre : grand bleuet, bande tricolore, kicker, titre
            svg, jf = bleuet_svg(sid, 600, 800)
            h += [f'<div class="abs" style="left:240px;top:100px;width:600px;height:800px">{svg}</div>',
                  f'<div id="{sid}tri" class="abs" style="left:90px;top:972px;width:300px;height:10px;display:flex;transform-origin:0 50%"><i style="flex:1;background:#2E48D8"></i><i style="flex:1;background:#fff"></i><i style="flex:1;background:#E1000F"></i></div>',
                  f'<div class="kick" id="{sid}e" style="top:1020px">{esc(s.get("eyebrow", ""))}</div>', f'<div class="ttl" id="{sid}t" style="top:1100px;font-size:92px;line-height:108px">{mots(s["titre"])}</div>']
            j += [jf.replace("%T0%", f"{t:.2f}"), f'tl.fromTo("#{sid}tri", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.7, ease: "power3.inOut" }}, {t + 2.0:.2f});',
                  f'rise("#{sid}e", {t + 2.2:.2f}, -16, 0.4);', f'words("#{sid}t .w", {t + 2.5:.2f}, 0.07);']
    elif ty == "loi_resume":
        col = {"vert": "rgb(69,150,109)", "orange": "rgb(255,140,80)"}.get(s.get("couleur", "orange"), "rgb(255,140,80)")
        tt = s["titre"]; nn = len(tt); sz, lh = (62, 74) if nn <= 70 else (54, 66) if nn <= 110 else (48, 58)
        ts, tc, tu, _fin = lecture.delais_loi_resume(s); cf = s["chiffres"]
        h += [f'<div class="kick" id="{sid}e" style="top:290px">{esc(s.get("eyebrow", ""))}</div>',
              f'<div class="ttl" id="{sid}t" style="top:345px;font-size:{sz}px;line-height:{lh}px">{mots(tt)}</div>',
              f'<div class="stamp" id="{sid}s" style="color:{col};border-color:{col};top:650px">{esc(s["tampon"])}</div>']
        for k, (cle, lab, couleur) in enumerate((("pour", "POUR", "rgb(120,200,150)"), ("contre", "CONTRE", "rgb(255,150,100)"), ("abstention", "ABSTENTION", "#BECAFF")) if cf else ()):      # cf None : texte sans scrutin public, pas de chiffres
            lx = 120 + k * 300
            h += [f'<div class="cnt" id="{sid}k{k}" style="left:{lx}px;top:880px;font-size:76px">0</div>', f'<div class="lab" style="left:{lx}px;top:975px;color:{couleur}">{lab}</div>']
            j.append(f'(function(){{ const el = document.getElementById("{sid}k{k}"); DRAW.push(T => {{ el.textContent = Math.round({int(cf[cle])} * outExpo(clamp((T - {t + tc:.2f}) / 1.0))); }}); }})();')
        j += [f'rise("#{sid}e", {t + 0.15:.2f}, -16, 0.4);', f'words("#{sid}t .w", {t + 0.3:.2f}, 0.05);',
              f'tl.fromTo("#{sid}s", {{ scale: 1.6, opacity: 0, rotation: -5.7, transformOrigin: "50% 50%" }}, {{ scale: 0.5, opacity: 1, rotation: -5.7, duration: 0.2, ease: "power3.out" }}, {t + ts:.2f});']
        for k in range(3 if cf else 0):
            j.append(f'tl.fromTo("#{sid}k{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {t + tc:.2f});')
        if s.get("suite"):
            hc = max(190, min(320, 110 + 50 * -(-len(s["suite"]) // 38)))
            h.append(f'<div class="ex" id="{sid}x" style="top:{1060 if cf else 900}px;height:{hc}px"><div class="exe">La suite</div><div class="ext">{esc(s["suite"])}</div></div>')
            j.append(f'tl.fromTo("#{sid}x", {{ y: 70, opacity: 0, scale: 0.96, transformOrigin: "50% 50%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }}, {t + tu:.2f});')
    if SC.get("source") and i == len(SC["scenes"]) - 1:
        long_ = len(SC["source"]) > 70                       # source longue : sur deux lignes, plus petite (sinon elle deborde de l'ecran)
        h.append(f'<div class="srcp" style="top:{1395 if s["type"] == "loi_resume" else 1360}px{";white-space:normal;padding:0 70px;box-sizing:border-box;font-size:22px;line-height:28px" if long_ else ""}">{esc(SC["source"])}</div>')
    h.append("</div></div>"); html_s += h; js_s += j; t += d
F = SC.get("fin", {})
ZOOM = SC.get("effet_fin") == "zoom"      # option : silence de « pause_fin » s apres la derniere scene (le halo du fond gonfle), puis la carte Populous arrive en zoom arriere sur la reprise
P = float(SC.get("pause_fin", 1.75)); F0 = t + P if ZOOM else t - 0.3
fh, fj = blocs.finale(F0, (F.get("eyebrow", "Populous"), 430), [(F.get("ligne1", "Chaque scrutin,"), 66, 520, "var(--ink)"), (F.get("ligne2", "siège par siège."), 66, 610, "var(--accent)")],
                      (330, 1290), (180, 860, 1.0), [(F.get("accroche", "Chaque scrutin, sur Populous."), 44, 700, "var(--corps)", 1040, 1.6)], 1400, (F.get("source", "App gratuite, sans compte, sans publicité"), 1520, 2.4), zoom=ZOOM)
if ZOOM: fj += f'\ntl.fromTo("#glow", {{ scale: 1 }}, {{ scale: 2.6, duration: {P}, ease: "power2.in", transformOrigin: "50% 42%" }}, {t:.2f});'
if ZOOM: fj += f'\ntl.fromTo("#flood", {{ opacity: 0 }}, {{ opacity: 0.9, duration: {P}, ease: "power3.in" }}, {t:.2f});\ntl.set("#flood", {{ opacity: 0 }}, {F0 + 0.7:.2f});'
DUREE = F0 + FIN_D
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
