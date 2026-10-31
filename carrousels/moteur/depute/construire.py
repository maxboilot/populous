"""Carrousel « Député du jour » (HyperFrames) : 5 slides 1080x1350, bande continue (le portrait du député chevauche la couture 1|2).
Usage : python3 construire.py slide <0-4> | preview | pano  [Nom complet du député]   —  données : atlas officiel de l'app, élus, commun/sieges.json"""
import os, json, sys
from pathlib import Path
HERE = Path(__file__).parent; REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(HERE.parent / "commun")); sys.path.insert(0, str(REPO))
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
NOM_COMPLET = next((a for a in sys.argv[2:] if not a.isdigit() and a not in ("slide", "preview", "pano")), "Christine Le Nabour")
s = (REPO / "index.html").read_text(encoding="utf-8"); i = s.index("const DATA = ") + len("const DATA = ")
DATA, _ = json.JSONDecoder().raw_decode(s[i:])
E = next(e for e in DATA["elus"] if e["n"] == NOM_COMPLET)
try:
    from publier_reseaux import DEP_NAMES; DEP = DEP_NAMES.get(E["dep"], E["dep"])
except Exception:
    DEP = E["dep"]
SE = json.loads((Path(os.environ.get("SIEGES_JSON") or HERE.parent / "commun" / "sieges.json")).read_text(encoding="utf-8")); SCR = SE["scrutin"]
PRENOM, NOM = E["n"].split(" ", 1); fem = E["c"] == "Mme"
POS = SE["POS"][SE["NOM"].index(E["n"])]
LAB = {"pour": "A voté pour", "contre": "A voté contre", "abstention": "S’est abstenue" if fem else "S’est abstenu", "absent": "Absente lors du vote" if fem else "Absent lors du vote"}
COL = {"pour": "rgb(69,150,109)", "contre": "rgb(177,89,53)", "abstention": "rgb(128,139,195)", "absent": "rgb(84,98,166)"}
TT = SCR["titre"].replace("l’", "").replace("l'", "", 1).strip().rstrip("."); TT = TT[0].upper() + TT[1:]
ci = "1re" if E["ci"] == 1 else f"{E['ci']}e"
a = E["a"]; cx, cy = a % 24, a // 24
bg = lambda d: f"background-size:{24 * d}px {25 * d}px;background-position:{-cx * d}px {-cy * d}px"
x = 70; onglets = ""
for n, sub, w in [("Vote", "dernier scrutin", 220), ("Groupe", "appartenance", 220), ("Âge", "années", 220), ("Parcours", "avant le mandat", 250)]:
    onglets += f'<div class="tab" style="left:{x}px;width:{w}px"><b>{n}</b><small>{sub}</small></div>'; x += w + 12
compact = {k: SE[k] for k in ("A", "R", "ROW", "GRP", "POS", "NOM", "AGE", "PRIVE")}
carrousel.assembler(HERE, "modele.html", {"%%PORT_BG480%%": bg(480), "%%PORT_BG220%%": bg(220), "%%GRPCOL%%": E["col"], "%%PRENOM%%": PRENOM, "%%NOM%%": NOM, "%%GSIGLE%%": E["g"], "%%GNOM%%": E["gn"],
    "%%LIEU%%": f"{DEP} · {ci} circonscription · {E['age']} ans", "%%PRO%%": E["pro"] or "Non renseignée", "%%TITREV%%": TT, "%%POSCOL%%": COL[POS], "%%POSLAB%%": LAB[POS], "%%ONGLETS%%": onglets,
    "%%SIEGES_JSON%%": json.dumps(compact), "%%ELUS_JSON%%": json.dumps([[e["a"], e["col"]] for e in DATA["elus"]]), "%%ATLAS_IDX%%": str(a), "%%NOM_COMPLET%%": E["n"],
    "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous")}, MODE, IDX, DUR, RW, sombres=(2, 3))
print("index.html :", MODE, IDX if MODE == "slide" else "", "|", E["n"], POS)
