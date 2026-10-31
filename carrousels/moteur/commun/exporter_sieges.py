"""Exporte les 577 sièges (géométrie de l'hémicycle + groupes + votes réels d'un scrutin) en JSON pour les carrousels.
Source : index.html du dépôt (groupes, élus) + data/scrutins/<n>.json. Rien d'inventé.
Usage : python3 exporter_sieges.py <n° de scrutin> <fichier de sortie>"""
import json, math, os, sys
from pathlib import Path
REPO = Path(os.environ.get("POPULOUS_REPO") or Path(__file__).resolve().parents[3])

def exporter(numero, sortie):
    s = (REPO / "index.html").read_text(encoding="utf-8"); i = s.index("const DATA = ") + len("const DATA = ")
    APP, _ = json.JSONDecoder().raw_decode(s[i:])
    GROUPES = sorted(APP["groupes"], key=lambda g: g["o"])
    CANON = {"EcoS": "ECOS", "Dem": "DEM", "UDR": "UDDPLR"}              # codes des élus -> codes des groupes
    ORDRE = {g["s"]: i for i, g in enumerate(GROUPES)}
    code = lambda e: CANON.get(e["g"], e["g"])
    hexc = lambda h: [int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    elus = sorted(APP["elus"], key=lambda e: ORDRE[code(e)])             # tri stable : groupe par groupe, de gauche à droite
    NS = len(elus); assert NS == 577, NS
    r_rang = [1.0 + 0.1 * i for i in range(12)]; tot = sum(r_rang)
    n_rang = [round(NS * r / tot) for r in r_rang]; n_rang[-1] += NS - sum(n_rang)
    sieges = []
    for i, (r, n) in enumerate(zip(r_rang, n_rang)):
        for j in range(n): sieges.append((-math.pi / 2 + math.pi * (j + 0.5) / n, r, i))
    sieges.sort(key=lambda s: (round(s[0], 5), s[2]))
    scr = json.loads((REPO / "data" / "scrutins" / f"{numero}.json").read_text(encoding="utf-8"))
    pos = {e["n"]: ("absent" if scr["par_circonscription"].get(e["k"]) in (None, "non_votant") else scr["par_circonscription"].get(e["k"])) for e in APP["elus"]}
    out = {
        "A": [round(s[0], 5) for s in sieges], "R": [round(s[1], 4) for s in sieges], "ROW": [s[2] for s in sieges],
        "GRP": [hexc(next(g["c"] for g in GROUPES if g["s"] == code(e))) for e in elus],
        "NOM": [e["n"] for e in elus], "G": [code(e) for e in elus], "POS": [pos[e["n"]] for e in elus],
        "AGE": [e.get("age", 50) for e in elus], "PRIVE": [1 if e.get("par", "") == "Privé" else 0 for e in elus],
        "GROUPES": [{"s": g["s"], "n": g["n"], "c": hexc(g["c"])} for g in GROUPES],
        "scrutin": {"numero": scr["numero"], "date": scr["date"], "titre": scr["titre"], "adopte": scr["adopte"], "tally": scr["tally"]},
    }
    Path(sortie).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out

if __name__ == "__main__":
    o = exporter(int(sys.argv[1]), sys.argv[2]); print("sieges :", len(o["A"]), "scrutin", o["scrutin"]["numero"], o["scrutin"]["tally"])
