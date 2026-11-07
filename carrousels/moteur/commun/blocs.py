"""Blocs communs : image finale (carte Populous + badges), assemblage d'un projet HyperFrames à partir d'un gabarit."""
import json
from pathlib import Path
COMMUN = Path(__file__).parent

def finale(t0, eyebrow, lignes, cartes, mot, tags, badges_y, src, extra='', push=True, zoom=False):
    """Image finale commune. t0 : début absolu (s). Renvoie (html, js).
    cartes=(haut, bas) de la carte ; lignes=[(texte, taille, y, couleur_css)] alignées à gauche (x=130) ;
    mot=(taille, y, t_rel_début) ; tags=[(texte, taille, graisse, couleur_css, y, t_rel)] centrés ; src=(texte, y, t_rel)."""
    top, bot = cartes
    h = [f'<div id="scF" class="sc" data-layout-allow-overflow>', '<div class="fill bg-grey"></div>', '<div class="wm" style="left:853px"><span>Populous</span></div>',
         f'<div id="cardF" class="card" style="left:70px;top:{top}px;width:940px;height:{bot - top}px"></div>',
         f'<div id="qF1" class="q" style="left:5px;top:{top - 195}px">“</div>', f'<div id="qF2" class="q" style="left:775px;top:{bot - 195}px">”</div>',
         f'<div class="eb" id="ebF" style="left:130px;top:{eyebrow[1] - 17}px">{eyebrow[0]}</div>']
    for i, (tx, sz, y, col) in enumerate(lignes):
        h.append(f'<div id="lnF{i}" class="abs" style="left:130px;top:{y - sz // 2}px;font-size:{sz}px;line-height:1;white-space:nowrap;color:{col}">{tx}</div>')
    sz, y, _ = mot
    h.append(f'<div id="popF" class="c" style="top:{y - sz // 2}px;font-size:{sz}px;letter-spacing:-.02em;color:var(--ink)">' + "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous") + '</div>')
    for i, (tx, sz2, gr, col, y2, _t) in enumerate(tags):
        h.append(f'<div id="tgF{i}" class="c" style="top:{y2 - sz2 // 2}px;font-size:{sz2}px;font-weight:{gr};color:{col}">{tx}</div>')
    by = badges_y - 74
    h.append(f'<div id="bAS" class="badge" style="left:70px;top:{by}px"><small>Télécharger dans</small><b>l’App Store</b></div>')
    h.append(f'<div id="bGP" class="badge" style="left:560px;top:{by}px"><small>DISPONIBLE SUR</small><b>Google Play</b></div>')
    h.append(f'<div id="srcF" class="c" style="top:{src[1] - 13}px;font-size:28px;font-weight:500;color:var(--gris)">{src[0]}</div>')
    h.append(extra)
    if zoom: h.append('<div id="flashF" style="position:absolute;left:0;top:0;width:1080px;height:1920px;background:#fff;opacity:0;pointer-events:none"></div>')
    h.append('</div>')
    js = [f'const F0 = {t0};',
          ('tl.fromTo("#scF", { scale: 1.5, opacity: 0, filter: "blur(16px)", transformOrigin: "540px 960px" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out" }, F0);'
           'tl.fromTo("#flashF", { opacity: 0.55 }, { opacity: 0, duration: 0.4, ease: "power2.out" }, F0);' if zoom else
           'tl.fromTo("#scF", { y: 1920 }, { y: 0, duration: 0.36, ease: "power3.inOut" }, F0);' if push else ''),
          'tl.fromTo(["#cardF", "#qF1", "#qF2"], { scale: 0.88, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.3)", transformOrigin: "540px 770px" }, F0 + 0.1);',
          'tl.fromTo("#ebF", { opacity: 0 }, { opacity: 1, duration: 0.3 }, F0 + 0.3);']
    for i, (tx, sz, y, col) in enumerate(lignes):
        js.append(f'tl.fromTo("#lnF{i}", {{ opacity: 0, x: 40 }}, {{ opacity: 1, x: 0, duration: 0.3, ease: "power3.out" }}, F0 + {0.4 + 0.15 * i});')
    js.append(f'tl.fromTo("#popF .l", {{ y: 110, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.28, ease: "back.out(2.6)", stagger: 0.04 }}, F0 + {mot[2]});')
    for i, (tx, sz2, gr, col, y2, tt) in enumerate(tags):
        js.append(f'tl.fromTo("#tgF{i}", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: "power3.out" }}, F0 + {tt});')
    js.append(f'tl.fromTo("#bAS", {{ scale: 1.8, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "power3.out", transformOrigin: "50% 50%" }}, F0 + {badges_y and 1.5});')
    js.append(f'tl.fromTo("#bGP", {{ scale: 1.8, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "power3.out", transformOrigin: "50% 50%" }}, F0 + 1.75);')
    js.append(f'tl.fromTo("#srcF", {{ opacity: 0 }}, {{ opacity: 0.9, duration: 0.3 }}, F0 + {src[2]});')
    return "\n".join(h), "\n".join(js)

def assembler(dossier, modele, subs):
    """Lit gabarit/<modele>, insère CSS/JS communs et les valeurs `subs`, écrit index.html."""
    html = (dossier / "gabarit" / modele).read_text(encoding="utf-8")
    base = {"/*%%CSS_COMMUN%%*/": (COMMUN / "base.css").read_text(encoding="utf-8"), "/*%%LIB_JS%%*/": (COMMUN / "lib.js").read_text(encoding="utf-8")}
    for k, v in {**base, **subs}.items(): html = html.replace(k, v)
    (dossier / "index.html").write_text(html, encoding="utf-8")
