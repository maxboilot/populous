"""Carrousel « Texte voté sans scrutin public » (HyperFrames) : 3 slides 1080x1350 en une bande continue : le texte + tampon, de quoi il parle (ce que c'est / ce vote / la suite), Populous.
Pas de chiffres ni d'hémicycle : il n'y a pas de scrutin public à montrer (rien n'est inventé).
Usage : NB_SLIDES=3 DECISION_JSON='{...}' python3 construire.py slide <0-2> | preview | pano"""
import os, json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "commun"))
os.environ.setdefault("NB_SLIDES", "3")
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
D = json.loads(os.environ["DECISION_JSON"])        # {titre, date_fr, adopte, explication: [[titre, texte], ...], source, source_pied}
EXPL = D["explication"]
assert len(EXPL) == 3, "DECISION_JSON : 3 blocs [titre, texte] (Ce que c'est / Ce vote / La suite)"
STAMP, STAMPCOL = ("ADOPTÉ", "rgb(69,150,109)") if D["adopte"] else ("REJETÉ", "rgb(255,140,80)")
TT = D["titre"]
cartes, fin_cartes = carrousel.cartes_auto(EXPL)
carrousel.assembler(HERE, "modele.html", {"%%DATE%%": D["date_fr"].upper(), "%%TITRE%%": " ".join(f'<span class="w">{w}</span>' for w in TT.split()),
    "%%STAMP%%": STAMP, "%%STAMPCOL%%": STAMPCOL, "%%CARTES%%": cartes, "%%SRC_TOP%%": str(fin_cartes + 30), "%%SRC_EXPL%%": D["source"], "%%EYEBROW%%": "Texte voté",
    "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous"), "%%SOURCE_PIED%%": D["source_pied"]}, MODE, IDX, DUR, RW, sombres=(0, 1))
print("index.html :", MODE, IDX if MODE == "slide" else "", "|", STAMP)
