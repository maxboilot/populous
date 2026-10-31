"""Carrousel « À venir » (HyperFrames) : 5 slides 1080x1350. Pont : une règle de calendrier de 28 jours traverse toutes les slides.
Usage : python3 construire.py slide <0-4> | preview | pano [AAAA-MM-JJ]   —  données RÉELLES : data/agenda.json de l'app"""
import os, json, re, sys, datetime, collections
from pathlib import Path
HERE = Path(__file__).parent; REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(HERE.parent / "commun"))
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
AUJ = next((a for a in sys.argv[2:] if re.fullmatch(r"\d{4}-\d\d-\d\d", a)), datetime.date.today().isoformat())
AG = sorted((a for a in json.loads((REPO / "data/agenda.json").read_text(encoding="utf-8")) if a["date"] >= AUJ), key=lambda a: (a["date"], a["heure"]))
N = len(AG); JOUR = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
def court(txt):
    s = re.sub(r"^(Suite de la discussion (du|de la|des|d’un|de l’) ?|Examen du texte — )", "", txt.strip(), flags=re.I)
    s = re.sub(r"\s*\([^)]*\)", "", s).strip().upper(); lignes, cur = [], ""
    for m in s.split():
        if len((cur + " " + m).strip()) <= 20: cur = (cur + " " + m).strip()
        else: lignes.append(cur); cur = m
    lignes.append(cur)
    if len(lignes) > 2: lignes = lignes[:2]; lignes[1] = (lignes[1][:19] if len(lignes[1]) > 19 else lignes[1]).rstrip() + "…"
    return lignes[:2], s
ITEMS, vus = [], set()
for a in AG:
    l, cle = court(a["ordre_du_jour"])
    if cle in vus: continue
    vus.add(cle); ITEMS.append((a, l))
    if len(ITEMS) == 3: break
d_fr = lambda a: (lambda d: f"{JOUR[d.weekday()]} {d.strftime('%d/%m')} · {a['heure'].replace(':', 'H')}")(datetime.date.fromisoformat(a["date"]))
LIGNES = []
for a, l in ITEMS: LIGNES += [[d_fr(a), True]] + [[x, False] for x in l]
PANH = len(LIGNES) * 78 + 40
items = ""
for i, (a, l) in enumerate(ITEMS):
    y = 490 + i * 235; d = datetime.date.fromisoformat(a["date"]); sep = f'<div class="sepD" style="top:{y + 205}px"></div>' if i < 2 else ""
    items += f'<div class="it"><div class="pillD" style="top:{y}px">{d.strftime("%d/%m")} · {a["heure"]}</div><div class="txtD" style="top:{y + 70}px">{a["ordre_du_jour"]}</div>{sep}</div>'
CNT = collections.Counter(a["date"] for a in AG); D0 = datetime.date.fromisoformat(AUJ); regle = ""
for i in range(28):
    d = D0 + datetime.timedelta(days=i); x = 100 + i * 186; c = CNT.get(d.isoformat(), 0)
    regle += f'<div class="rk" style="left:{x}px;height:{26 if d.weekday() == 0 else 14}px"></div><div class="rl" style="left:{x}px">{d.day}</div>'
    if c: dd = 12 + 5 * min(c, 6); regle += f'<div class="rd" style="left:{x - dd / 2:.0f}px;top:{1262 - dd / 2:.0f}px;width:{dd}px;height:{dd}px"></div>'
nj = len(CNT)
first = AG[0]; d1 = datetime.date.fromisoformat(first["date"])
colonnes = "".join(f'<div class="col"><div class="strip" data-d="{c}">' + "".join(f"<i>{n % 10}</i>" for n in range(30)) + "</div></div>" for c in str(N))
carrousel.assembler(HERE, "modele.html", {"%%REGLE%%": regle, "%%PANH%%": str(PANH), "%%ITEMS%%": items, "%%LIGNES_JSON%%": json.dumps(LIGNES, ensure_ascii=False), "%%COLONNES%%": colonnes,
    "%%JOURS_TXT%%": f"réparties sur {nj} jour{'s' if nj > 1 else ''}", "%%PROCHAIN_DATE%%": f"{JOUR[d1.weekday()]} {d1.strftime('%d/%m')}", "%%PROCHAIN_HEURE%%": first["heure"].replace(":", "H"),
    "%%PROCHAIN_TXT%%": " ".join(f'<span class="w">{w}</span>' for w in first["ordre_du_jour"].split()),
    "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous")}, MODE, IDX, DUR, RW, sombres=(0, 2, 3))
print("index.html :", MODE, IDX if MODE == "slide" else "", "| dès le", AUJ, "|", N, "points sur", nj, "jours")
