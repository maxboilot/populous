"""Outils communs des carrousels HyperFrames : modes, barres de progression, assemblage."""
import re, sys
from pathlib import Path
COMMUN = Path(__file__).parent
def contexte():
    """python3 construire.py slide <0-4> | preview | pano [MM-JJ ou autre]"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "pano"
    idx = int(sys.argv[2]) if mode == "slide" else 0
    dur, rw = {"slide": (6.5, 1080), "preview": (16.6, 1080), "pano": (4.5, 5400)}[mode]
    return mode, idx, dur, rw
def progres(k, sombres=()):
    col = "#fff" if k in sombres else "var(--ink)"
    return "".join(f'<div class="pg" style="left:{187 + j * 144}px;background:{col};opacity:{1 if j == k else .25}"></div>' for j in range(5))
def assembler(dossier, modele, subs, mode, idx, dur, rw, sombres=()):
    import blocs
    css = (COMMUN / "carrousel.css").read_text(encoding="utf-8"); js = (COMMUN / "carrousel.js").read_text(encoding="utf-8")
    base = {"%%RW%%": str(rw), "%%DUR%%": str(dur), "%%MODE%%": mode, "%%IDX%%": str(idx)}
    for k, v in base.items(): css = css.replace(k, v); js = js.replace(k, v)
    allsubs = {"/*%%CSS_CARROUSEL%%*/": css, "/*%%JS_CARROUSEL%%*/": js, **base}
    allsubs.update({f"%%PROGRES{k + 1}%%": progres(k, sombres) for k in range(5)})
    allsubs.update(subs)
    blocs.assembler(dossier, modele, allsubs)
