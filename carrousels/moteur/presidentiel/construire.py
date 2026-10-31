"""Carrousel « Actu présidentielle 2027 » (HyperFrames) : 5 slides 1080x1350. Pont : la barre des scores du sondage (un segment par candidat).
Données RÉELLES : data/sondages.json (dernier sondage). Aucune photo distante : couleurs de parti uniquement.
Usage : python3 construire.py slide <0-4> | preview | pano"""
import os, json, sys, datetime
from pathlib import Path
from urllib.parse import urlparse
HERE = Path(__file__).parent; REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(HERE.parent / "commun"))
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
D = json.loads((REPO / "data/sondages.json").read_text(encoding="utf-8"))
S = max(D["sondages"], key=lambda s: s["date"])
CAND = {c["cle"]: c for c in D["candidats"]}
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
d = datetime.date.fromisoformat(S["date"]); DATE_FR = f"{d.day} {MOIS[d.month - 1]} {d.year}"
rang = sorted(S["scores"].items(), key=lambda kv: -kv[1])
fr = lambda x: (f"{x:.1f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x)}").replace(".", ",")
nom = lambda k: CAND.get(k, {}).get("nom", k); coul = lambda k: CAND.get(k, {}).get("couleur", "#6F86F0")
tete, deux = rang[0], rang[1]
TOT = sum(s for _, s in rang); BARW = 4200
barre, etiq, x = "", "", 0.0
for k, sc in rang:
    w = BARW * sc / TOT
    barre += f'<div style="left:{x:.1f}px;width:{max(w - 3, 1):.1f}px;background:{coul(k)}"></div>'
    if sc >= 6: etiq += f'<div class="pl" style="left:{100 + x + 6:.0f}px">{nom(k)} {fr(sc)} %</div>'
    x += w
clas = ""
mx = rang[0][1]
for i, (k, sc) in enumerate(rang[:6]):
    clas += (f'<div class="rk" style="top:{360 + i * 118}px"><div class="nm">{nom(k)}</div><div class="tr"></div>'
             f'<div class="fl" style="width:{480 * sc / mx:.0f}px;background:{coul(k)}"></div><div class="pt">{fr(sc)} %</div></div>')
host = (urlparse(S["source"]).hostname or "").removeprefix("www.")
commission = "commission-des-sondages.fr" in host
ecart = tete[1] - deux[1]
ligne = f"Sondage {S['institut']} · {DATE_FR}"
carrousel.assembler(HERE, "modele.html", {
    "%%BARW%%": str(BARW), "%%BARRE%%": barre, "%%ETIQ_BARRE%%": etiq, "%%CLASSEMENT%%": clas,
    "%%TETE_NOM%%": nom(tete[0]), "%%TETE_SCORE%%": json.dumps(tete[1]), "%%TETE_COUL%%": coul(tete[0]), "%%LIGNE_SONDAGE%%": ligne, "%%ECHANTILLON%%": str(S["echantillon"]),
    "%%ECART_1%%": f"{fr(ecart)} point{'s' if ecart >= 2 else ''} d’écart entre", "%%ECART_2%%": f"{nom(tete[0])} et {nom(deux[0])}.",
    "%%SOURCE_1%%": "Commission" if commission else S["institut"], "%%SOURCE_2%%": "des sondages" if commission else DATE_FR,
    "%%SOURCE_TXT%%": f"Sondage {S['institut']} du {DATE_FR}, notice déposée à la Commission des sondages." if commission else f"Sondage {S['institut']} du {DATE_FR}. Source : {host}.",
    "%%SOURCE_PIED%%": "Source : " + (f"Commission des sondages ({host})" if commission else host),
    "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous")}, MODE, IDX, DUR, RW, sombres=(0, 2, 3))
print("index.html :", MODE, IDX if MODE == "slide" else "", "|", S["institut"], S["date"], nom(tete[0]), tete[1])
