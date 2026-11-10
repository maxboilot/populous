"""Outils communs des carrousels HyperFrames : modes, barres de progression, assemblage."""
import math, os, re, sys
from pathlib import Path
COMMUN = Path(__file__).parent
NB = int(os.environ.get("NB_SLIDES") or 5)          # nombre de slides du carrousel (5 par defaut ; 3 pour « decision »)
def contexte():
    """python3 construire.py slide <0..NB-1> | preview | pano [MM-JJ ou autre]"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "pano"
    idx = int(sys.argv[2]) if mode == "slide" else 0
    dur, rw = {"slide": (6.5, 1080), "preview": (round(3.3 * (NB - 1) + 3.4, 1), 1080), "pano": (4.5, 1080 * NB)}[mode]
    return mode, idx, dur, rw
def progres(k, sombres=()):
    col = "#fff" if k in sombres else "var(--ink)"
    return "".join(f'<div class="pg" style="left:{(1080 - 130 - 144 * (NB - 1)) // 2 + j * 144}px;background:{col};opacity:{1 if j == k else .25}"></div>' for j in range(NB))
def assembler(dossier, modele, subs, mode, idx, dur, rw, sombres=()):
    import blocs
    css = (COMMUN / "carrousel.css").read_text(encoding="utf-8"); js = (COMMUN / "carrousel.js").read_text(encoding="utf-8")
    base = {"%%RW%%": str(rw), "%%DUR%%": str(dur), "%%MODE%%": mode, "%%IDX%%": str(idx), "%%NB%%": str(NB)}
    for k, v in base.items(): css = css.replace(k, v); js = js.replace(k, v)
    allsubs = {"/*%%CSS_CARROUSEL%%*/": css, "/*%%JS_CARROUSEL%%*/": js, **base}
    allsubs.update({f"%%PROGRES{k + 1}%%": progres(k, sombres) for k in range(NB)})
    allsubs.update(subs)
    blocs.assembler(dossier, modele, allsubs)
def cartes_auto(expl, y0=330, zone=790, gap=24, min_h=240):
    """Cartes « Ce que c'est / Ce vote / La suite » empilees dans la zone [y0, y0+zone] : la taille du texte diminue (35 -> 24 px) tant que l'ensemble ne tient pas.
    Estimation prudente de la largeur (0,56 em par caractere, 850 px utiles). Renvoie (html, y_fin)."""
    for fs in (35, 32, 30, 28, 26, 24):
        lh = round(fs * 1.31); cpl = int(850 / (fs * 0.56))
        contenu = [74 + lh * max(1, math.ceil(len(tx) / cpl)) + 36 for _, tx in expl]
        for hs in ([max(min_h, h) for h in contenu], contenu):          # hauteur minimale d'abord (aspect habituel), sinon au plus juste
            total = sum(hs) + gap * (len(hs) - 1)
            if total <= zone: break
        if total <= zone: break
    y = y0 + max(0, (zone - total) // 2); html = ""
    for i, ((tt, tx), h) in enumerate(zip(expl, hs)):
        html += f'<div class="ex" id="ex{i}" style="top:{y}px;height:{h}px"><div class="exe">{tt}</div><div class="ext" style="font-size:{fs}px;line-height:{lh}px">{tx}</div></div>'
        y += h + gap
    return html, y - gap
