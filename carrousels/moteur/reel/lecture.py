"""Temps de lecture des Reels : chaque carte / rangee n'apparait qu'une fois la precedente lue, et chaque scene dure au moins le temps de lire son contenu.
Vitesse : 0,22 s par mot (≈ 270 mots/min, lecture rapide mais confortable sur mobile) + une marge par bloc."""
import re
MOT = 0.22
def n_mots(t): return len(re.sub(r"\*\*", "", str(t)).split())
def lire(*t, base=0.4): return base + MOT * sum(n_mots(x) for x in t)
def delais_items(s):
    """(decalages, fin_de_lecture) en secondes depuis le debut de la scene, pour une scene « cartes » ou « liste »."""
    if s["type"] == "cartes": blocs, t = [(c[0], c[1]) for c in s["cartes"]], 0.9
    elif s["type"] == "etapes": blocs, t = [(e.get("kicker", ""), e["titre"], e.get("sous", "")) for e in s["etapes"]], 0.9
    elif s["type"] == "compare":
        blocs, t = [(c.get("kicker", ""), c["titre"], c.get("sous", "")) for c in (s["gauche"], s["droite"])] + ([(s["bas"]["titre"], s["bas"].get("sous", ""))] if s.get("bas") else []), 0.9
    else: blocs, t = [((it if isinstance(it, str) else it[0]),) for it in s["items"]], 0.8
    out = []
    for b in blocs: out.append(round(t, 2)); t += lire(*b)
    return out, t
def delais_loi_resume(s):
    """(tampon, chiffres, carte « la suite », fin de lecture) en secondes depuis le debut d'une scene « loi_resume » : le titre est lu avant le tampon, puis les chiffres, puis la suite."""
    nt = n_mots(s["titre"]); ts = min(0.9 + 0.11 * nt, 3.4); tc = ts + 0.5; tu = tc + 1.2
    fin = (tu + 0.5 + MOT * n_mots(s["suite"]) + 0.8) if s.get("suite") else tc + 1.8 + 0.8
    return round(ts, 2), round(tc, 2), round(tu, 2), round(fin, 2)


def duree_min(s):
    ty = s["type"]
    if ty in ("cartes", "liste", "etapes", "compare"): return round(delais_items(s)[1] + 0.6, 2)
    if ty == "points": return round(max(5.4, 3.6 + MOT * sum(n_mots(g.get("label", "")) for g in s["groupes"]) + 0.6), 2)
    if ty == "loi_resume": return delais_loi_resume(s)[3]
    if ty == "chiffre": return round(max(4.6, 3.0 + MOT * n_mots(s.get("sous", "")) + 0.8), 2)
    if ty == "mois": return 5.6
    if ty == "bleuet": return round(max(4.6, 0.4 + MOT * n_mots(s.get("texte") or s.get("titre", "")) + 0.7), 2) if s.get("texte") else 5.2     # le bleuet a besoin de ~4,5 s pour eclore
    if ty == "texte": return round(0.4 + MOT * n_mots(s["texte"]) + 0.7, 2)
    if ty == "titre": return round(max(0.4 + MOT * n_mots(s["titre"]) + 0.6, 3.0 if s.get("tampon") else 0), 2) if not s.get("tampon") else round(max(0.4 + MOT * n_mots(s["titre"]) + 0.6, 3.0), 2)
    return 5.8 if ty == "chiffres" else 5.4                       # hemicycle
