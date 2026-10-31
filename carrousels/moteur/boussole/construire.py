"""Carrousel « Boussole » (HyperFrames) : 5 slides 1080x1350. Pont : la boussole est à cheval sur la couture 1|2.
Scrutins RÉELS : data/historique.json. L'écran « Ton résultat 80 % » est une ILLUSTRATION (marquée « EXEMPLE » à l'image), noms de groupes masqués.
Usage : python3 construire.py slide <0-4> | preview | pano"""
import os, json, math, sys, datetime
from pathlib import Path
HERE = Path(__file__).parent; REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(HERE.parent / "commun"))
import carrousel
MODE, IDX, DUR, RW = carrousel.contexte()
SE = json.loads((Path(os.environ.get("SIEGES_JSON") or HERE.parent / "commun" / "sieges.json")).read_text(encoding="utf-8"))
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
LOIS = [l for l in json.loads((REPO / "data/historique.json").read_text(encoding="utf-8"))["lois"] if l.get("titre")][:10]
def carte(i):
    l = LOIS[i]; d = datetime.date.fromisoformat(l["date"])
    pg = "".join(f'<div class="pg2" style="left:{50 + k * 62}px;background:{"#1B3BDB" if k <= i else "#E2E4F0"}"></div>' for k in range(len(LOIS)))
    stamp = {0: ("POUR", "rgb(27,138,107)", -12), 1: ("CONTRE", "rgb(196,80,28)", 12)}.get(i, ("", "#fff", 0))
    return (f'<div class="cd"><div class="num">{i + 1} / {len(LOIS)} — SCRUTIN RÉEL</div>{pg}<div class="ti">{l["titre"]}</div>'
            f'<div class="dt">{d.day} {MOIS[d.month - 1]} {d.year} · {"Adopté" if l["adopte"] else "Rejeté"} à l’Assemblée nationale.</div>'
            '<div class="bt" style="top:470px;height:76px;line-height:76px;border-radius:38px;background:rgb(27,138,107);font-size:36px">Pour</div>'
            '<div class="bt" style="top:558px;height:64px;line-height:64px;border-radius:32px;background:#F0F1F8;color:#4A5578;font-size:32px">Neutre</div>'
            '<div class="bt" style="top:634px;height:64px;line-height:64px;border-radius:32px;background:rgb(196,80,28);font-size:32px">Contre</div>'
            f'<div class="st" style="color:{stamp[1]};transform:rotate({stamp[2]}deg)">{stamp[0]}</div></div>')
cartes = "".join(carte(i) for i in (2, 1, 0))              # fond -> devant
NOMS = [330, 300, 400, 280, 360]; RES = [80, 70, 65, 50, 48]; res = ""
for i, v in enumerate(RES):
    y = 850 + i * 88; t = min(1, i / 4)
    col = f"rgb({255 + (130 - 255) * t:.0f},160,{60 + (255 - 60) * t:.0f})"
    res += (f'<div class="rrow"><div class="rb" style="top:{y - 18}px;width:{NOMS[i]}px"></div><div class="rt" style="top:{y + 30}px"></div>'
            f'<div class="rf" style="top:{y + 30}px;width:{900 * v / 100:.0f}px;background:{col}"></div><div class="rp" style="top:{y - 22}px">{v} %</div></div>')
ticks = ""
for k in range(12):
    th = k * math.pi / 6; r0 = 330 * (0.86 if k % 3 == 0 else 0.92); r1 = 330 * 0.99
    ticks += f'<line x1="{math.cos(th) * r0:.1f}" y1="{math.sin(th) * r0:.1f}" x2="{math.cos(th) * r1:.1f}" y2="{math.sin(th) * r1:.1f}" stroke="#FFE2B0" stroke-width="8" opacity=".6"/>'
gcode = {g["s"]: i for i, g in enumerate(SE["GROUPES"])}
compact = {k: SE[k] for k in ("A", "R", "ROW", "GRP")}
carrousel.assembler(HERE, "modele.html", {"%%TICKS%%": ticks, "%%CARTES%%": cartes, "%%RESULTATS%%": res, "%%GI_JSON%%": json.dumps([gcode[g] for g in SE["G"]]),
    "%%SIEGES_JSON%%": json.dumps(compact), "%%LETTRES%%": "".join(f'<span class="l" style="display:inline-block">{c}</span>' for c in "Populous")}, MODE, IDX, DUR, RW, sombres=(2, 3))
print("index.html :", MODE, IDX if MODE == "slide" else "", "|", len(LOIS), "scrutins réels")
