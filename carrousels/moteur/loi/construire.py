"""Carrousel « Loi votée » (HyperFrames) : 5 slides 1080x1350, bande continue (la barre des 577 voix traverse toutes les slides) : le texte + tampon, de quoi il parle, les chiffres, l'hémicycle, Populous.
Usage : python3 construire.py slide <0-4> | preview | pano   —  données : commun/sieges.json (python3 -I ../commun/exporter_sieges.py <n° de scrutin>)"""
import os, json, sys, datetime
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "commun"))
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
SE = json.loads((Path(os.environ.get("SIEGES_JSON") or HERE.parent / "commun" / "sieges.json")).read_text(encoding="utf-8"))
SCR = SE["scrutin"]; TY = SCR["tally"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
d = datetime.date.fromisoformat(SCR["date"]); DATE_FR = f"{d.day} {MOIS[d.month - 1]} {d.year}"
TT = SCR["titre"].replace("l’", "").replace("l'", "", 1).strip().rstrip("."); TT = TT[0].upper() + TT[1:]
if os.environ.get("TITRE_VOTE"): TT = os.environ["TITRE_VOTE"]        # titre synthétique relu par un humain (cf. publier_reseaux.py --type vote)
EXPL = json.loads(os.environ.get("EXPLICATION_LOI") or "[]")        # [[« Ce que c'est », texte], ...] relu par un humain (cf. publier_reseaux.py --resume)
SRC_EXPL = os.environ.get("SOURCE_EXPLICATION", "")
assert len(EXPL) in (2, 3), "EXPLICATION_LOI : 2 ou 3 blocs [titre, texte] (relus par un humain)"
OBJET = (SE["scrutin"].get("type") or "").replace("scrutin public ", "").strip()
EYEBROW = ("Vote solennel" if SE["scrutin"].get("solennel") else "Texte voté")
VOTANTS = TY["pour"] + TY["contre"] + TY["abstention"]
STAMP, STAMPCOL = ("ADOPTÉ", "rgb(69,150,109)") if SCR["adopte"] else ("REJETÉ", "rgb(255,140,80)")
COL = {"pour": (69, 150, 109), "contre": (177, 89, 53), "abstention": (128, 139, 195), "absent": (62, 74, 134)}
rgbs = lambda c: f"rgb({c[0]},{c[1]},{c[2]})"
N = sum(TY[k] for k in ("pour", "contre", "abstention", "absent")); BARW = 4200
barre, etiq, x = "", "", 0.0
fin_etiq = [0.0, 0.0]
LABC = {"pour": "rgb(90,200,160)", "contre": "rgb(230,130,80)", "abstention": "rgb(170,180,235)", "absent": "rgb(150,160,215)"}
LABT = {"pour": f"{TY['pour']} pour", "contre": f"{TY['contre']} contre", "abstention": f"{TY['abstention']} abstention", "absent": f"{TY['absent']} absents"}
for k in ("pour", "contre", "abstention", "absent"):
    w = BARW * TY[k] / N
    barre += f'<div style="left:{x:.1f}px;width:{max(w - 3, 1):.1f}px;background:{rgbs(COL[k])}"></div>'
    lx = 100 + x + 6 if k != "absent" else 1120
    niveau = 0 if lx >= fin_etiq[0] + 14 else 1                 # étiquettes qui se chevauchent : la suivante monte d'un cran
    fin_etiq[niveau] = lx + 15.5 * len(LABT[k])
    etiq += f'<div class="vl" style="left:{lx:.0f}px;top:{1246 - 36 * niveau}px;color:{LABC[k]}">{LABT[k]}</div>'
    x += w
BINS = [{"k": "pour", "n": TY["pour"], "x": 170}, {"k": "contre", "n": TY["contre"], "x": 410}, {"k": "abstention", "n": TY["abstention"], "x": 650}, {"k": "absent", "n": TY["absent"], "x": 890}]
LAB = {"pour": "POUR", "contre": "CONTRE", "abstention": "ABSTENTION", "absent": "ABSENTS"}
compt = "".join(f'<div id="cnt{i}" class="cnt" style="left:{b["x"] - 120}px">0</div><div class="lab" style="left:{b["x"] - 120}px">{LAB[b["k"]]}</div>' for i, b in enumerate(BINS))
cartes, fin_cartes = carrousel.cartes_auto(EXPL, y0=312)
compact = {k: SE[k] for k in ("A", "R", "ROW", "GRP", "POS")}
carrousel.assembler(HERE, "modele.html", {"%%BARRE%%": barre, "%%ETIQ_BARRE%%": etiq, "%%BARW%%": str(BARW), "%%DATE%%": DATE_FR.upper(), "%%TITRE%%": " ".join(f'<span class="w">{w}</span>' for w in TT.split()),
    "%%STAMP%%": STAMP, "%%STAMPCOL%%": STAMPCOL, "%%COMPTEURS%%": compt, "%%CARTES%%": cartes, "%%SOUS_EXPL%%": {2: "Deux choses à savoir.", 3: "Trois choses à savoir."}[len(EXPL)], "%%EYEBROW%%": EYEBROW, "%%VOTANTS%%": str(VOTANTS), "%%SRC_EXPL%%": SRC_EXPL, "%%SRC_TOP%%": str(max(fin_cartes + 30, 1138)), "%%SIEGES_JSON%%": json.dumps(compact), "%%BINS_JSON%%": json.dumps(BINS),
    "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous"),
    "%%SOURCE_PIED%%": f"Source : Assemblée nationale · scrutin n°{SCR['numero']} du {DATE_FR}"}, MODE, IDX, DUR, RW, sombres=(0, 1, 2, 3))
print("index.html :", MODE, IDX if MODE == "slide" else "", "| scrutin", SCR["numero"], STAMP)
