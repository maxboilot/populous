"""Carrousel « Fait du jour » (HyperFrames) : une bande continue de 5 slides 1080x1350 (4:5).
Usage : python3 construire.py slide <0-4> | preview | pano  [MM-JJ]   → écrit index.html (à rendre ensuite)
 - slide i : le clip d'une slide (Instagram : carrousel de vidéos, chaque slide démarre quand on arrive dessus)
 - preview : la bande entière avec caméra qui glisse de slide en slide (aperçu du swipe / version Reel)
 - pano    : la bande à plat 5400x1350, état final (pour vérifier que tout se prolonge d'une slide à l'autre)
Données RÉELLES : data/refs_jour.json de l'app. Source affichée = celle du fait."""
import os, json, re, sys
from pathlib import Path
from urllib.parse import urlparse
HERE = Path(__file__).parent; REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(HERE.parent / "commun"))
import blocs
MODE = sys.argv[1] if len(sys.argv) > 1 else "pano"; IDX = int(sys.argv[2]) if MODE == "slide" else 0
MMJJ = sys.argv[-1] if re.fullmatch(r"\d\d-\d\d", sys.argv[-1]) else "10-27"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
F = json.loads((REPO / "data/refs_jour.json").read_text(encoding="utf-8"))["refs"][MMJJ][0]
ANNEE = int(F["annee"]); AUJ = 2026
def _court(t, n=80): return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(".,;: ") + "…"
TITRE = F["titre"] or _court(F["texte"])        # faits sans titre (Wikipédia) : le texte EST le titre, raccourci en slide 1, complet en slide 2
TEXTE = re.sub(r"\b([IVX]+) e\b", r"\1e", F["texte"])
DATE = f"{int(MMJJ[3:])} {MOIS[int(MMJJ[:2]) - 1]} {ANNEE}".upper()
host = (urlparse(F["source"]).hostname or "").removeprefix("www.")
OFFICIEL = "assemblee-nationale.fr" in host
SURLIGNAGES = {"10-27": ["faible majorité", "primauté du pouvoir législatif"]}.get(MMJJ, [])
LEGENDE = {"10-27": "La IVe République"}.get(MMJJ, "")
def mots(texte, surligne=()):
    ws = texte.split(); marque = [False] * len(ws)
    for ph in surligne:
        p = ph.split()
        for i in range(len(ws) - len(p) + 1):
            if [w.strip(".,;") for w in ws[i:i + len(p)]] == p:
                for j in range(len(p)): marque[i + j] = True
    return " ".join(f'<span class="w{" h" if m else ""}">{w}</span>' for w, m in zip(ws, marque))
PICTO = '<svg viewBox="0 0 160 200" width="160" height="200"><rect x="2" y="30" width="156" height="156" rx="20" fill="#1B3BDB"/><path d="M2 50a20 20 0 0 1 20-20h116a20 20 0 0 1 20 20v28H2z" fill="#3E5EF5"/><rect x="16" y="78" width="128" height="94" rx="12" fill="#fff"/>' + "".join(f'<circle cx="{46 + i * 34}" cy="{106 + j * 34}" r="7" fill="#1B3BDB"/>' for i in range(3) for j in range(2)) + '<rect x="36" y="4" width="12" height="40" rx="6" fill="#1B3BDB"/><rect x="112" y="4" width="12" height="40" rx="6" fill="#1B3BDB"/></svg>'
COLONNES = "".join(f'<div class="col"><div class="strip" data-d="{c}">' + "".join(f"<i>{n % 10}</i>" for n in range(30)) + "</div></div>" for c in str(ANNEE))
def progres(k):
    col = "#fff" if k in (2, 3) else "var(--ink)"
    return "".join(f'<div class="pg" style="left:{187 + j * 144}px;background:{col};opacity:{1 if j == k else .25}"></div>' for j in range(5))
TICKS = "".join(f'<div class="tk" style="left:{2300 + i * 235 - 3}px"></div>' for i in range(9))
DUR, RW = {"slide": (6.5, 1080), "preview": (16.6, 1080), "pano": (4.5, 5400)}[MODE]
_n = len(TEXTE)
CORPS_PX = 70 if _n <= 110 else (58 if _n <= 190 else (50 if _n <= 260 else 44))      # un fait court se lit en grand, un long en plus petit
subs = {"%%CORPS_PX%%": str(CORPS_PX), "%%CORPS_LH%%": str(round(CORPS_PX * 1.45)), "%%RW%%": str(RW), "%%DUR%%": str(DUR), "%%MODE%%": MODE, "%%IDX%%": str(IDX), "%%TICKS%%": TICKS, "%%DATE%%": DATE, "%%COLONNES%%": COLONNES,
        "%%TITRE%%": mots(TITRE), "%%CORPS%%": mots(TEXTE, SURLIGNAGES), "%%ANNEE%%": str(ANNEE), "%%LEGENDE%%": LEGENDE, "%%AGE%%": str(AUJ - ANNEE), "%%AUJ%%": str(AUJ),
        "%%PICTO%%": PICTO, "%%LIGNE_SOURCE%%": "Une source officielle." if OFFICIEL else "Une source citée.", "%%HOTE%%": host,
        "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous"),
        "%%SOURCE_PIED%%": "Source : Assemblée nationale" if OFFICIEL else "Source : " + host}
subs.update({f"%%PROGRES{k + 1}%%": progres(k) for k in range(5)})
blocs.assembler(HERE, "modele.html", subs)
print("index.html :", MODE, IDX if MODE == "slide" else "", MMJJ, "|", host)
