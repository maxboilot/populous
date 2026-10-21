#!/usr/bin/env python3
# Construit la composition des conseils municipaux des 100 plus grandes villes
# (onglet « Ma ville », bloc « Conseil municipal »).
#
# Sources officielles, publiees sur data.gouv.fr par le ministere de l'Interieur :
#   - « Elections municipales 2026 - Resultats du premier tour » et « ... du
#     second tour » : resultats par commune et par liste, avec la nuance
#     politique attribuee par le ministere et le nombre de sieges au conseil
#     municipal ;
#   - memes jeux : fichiers « Candidats Elus » (sexe et date de naissance de
#     chaque elu) ;
#   - « Repertoire national des elus » : le maire en fonction.
#
# Les elections ont eu lieu les 15 et 22 mars 2026. Cette donnee ne bouge plus
# jusqu'aux prochaines elections (2032) hormis les elections partielles : le
# script se relance a la main, il n'a pas de workflow planifie.
#
# Sortie : data/conseils/<insee>.json, une fiche par ville. Rien n'est invente :
# une information absente reste null (la parite n'est calculee que si le
# nombre d'elus retrouves egale le nombre de sieges).
import csv
import datetime as dt
import io
import json
import pathlib
import sys
import time

import requests

SORTIE = pathlib.Path("data/conseils")
INDEX_VILLES = pathlib.Path("data/villes/index.json")
USER_AGENT = "Populous-conseils (https://github.com/maxboilot/populous)"
DATASET_T1 = "69b82a7de5d58cc06ad35ce0"   # Resultats du premier tour
DATASET_T2 = "69c17fed9f18c7781fd11a14"   # Resultats du second tour
DATASET_RNE = "5c34c4d1634f4173183a64f1"  # Repertoire national des elus
DATE_T1, DATE_T2 = "2026-03-15", "2026-03-22"

# Codes de nuance du ministere de l'Interieur -> libelle francais et famille
# (famille = couleur d'affichage). Libelles redactionnels de l'app : pour un
# code inconnu, on garde le code tel quel et la famille « divers ».
NUANCES = {
    "LEXG": ("Extrême gauche", "xg"), "LFI": ("La France insoumise", "g"),
    "LCOM": ("Parti communiste", "g"), "LSOC": ("Parti socialiste", "g"),
    "LRDG": ("Radicaux de gauche", "g"), "LUG": ("Union de la gauche", "g"),
    "LDVG": ("Divers gauche", "g"), "LVEC": ("Écologistes", "eco"),
    "LECO": ("Autres écologistes", "eco"), "LDVC": ("Divers centre", "c"),
    "LUC": ("Union du centre", "c"), "LHOR": ("Horizons", "c"),
    "LUDI": ("UDI", "c"), "LMDM": ("MoDem", "c"), "LREN": ("Renaissance", "c"),
    "LLR": ("Les Républicains", "d"), "LUD": ("Union de la droite", "d"),
    "LDVD": ("Divers droite", "d"), "LUDR": ("Union des droites pour la République", "d"),
    "LDLF": ("Debout la France", "d"), "LRN": ("Rassemblement national", "xd"),
    "LUXD": ("Union de l'extrême droite", "xd"), "LEXD": ("Extrême droite", "xd"),
    "LDIV": ("Divers", "div"), "LREG": ("Régionalistes", "div"),
}


def get(url, **kw):
    for i in range(4):
        try:
            r = requests.get(url, timeout=180, headers={"User-Agent": USER_AGENT}, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == 3:
                raise
            time.sleep(3 + 4 * i)


def url_ressource(dataset, *mots_requis, interdits=()):
    """URL d'une ressource data.gouv.fr retrouvee par son titre : robuste aux
    changements de date dans le nom de fichier."""
    meta = get(f"https://www.data.gouv.fr/api/1/datasets/{dataset}/").json()
    for res in meta["resources"]:
        titre = res["title"].lower().replace("&#39;", "'")
        if all(m.lower() in titre for m in mots_requis) and not any(x.lower() in titre for x in interdits):
            return res["url"]
    raise RuntimeError(f"ressource introuvable : {dataset} {mots_requis}")


def lignes_csv(url, delimiter=";"):
    """Parcours en flux d'un CSV distant (certains fichiers pesent 35 Mo)."""
    r = get(url, stream=True)
    r.raw.decode_content = True  # le serveur compresse en gzip : decompresser le flux
    texte = io.TextIOWrapper(r.raw, encoding="utf-8-sig", newline="")
    yield from csv.DictReader(texte, delimiter=delimiter)


def nombre(texte):
    try:
        return float(str(texte).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def titre_nom(prenom, nom):
    # Les fichiers donnent NOM en majuscules : on remet « Prénom Nom ».
    nom = nom.title() if nom.isupper() else nom
    return f"{prenom} {nom}".strip()


def resultats_communes(url, codes):
    """code commune -> {participation, listes: [...]} pour les villes voulues."""
    sortie = {}
    for row in lignes_csv(url):
        code = row["Code commune"]
        if code not in codes:
            continue
        listes, i = [], 1
        while f"Nuance liste {i}" in row:
            if row.get(f"Libellé de liste {i}"):
                nuance = row[f"Nuance liste {i}"]
                listes.append({
                    "tete": titre_nom(row.get(f"Prénom candidat {i}", ""), row.get(f"Nom candidat {i}", "")),
                    "nuance": nuance,
                    "famille": NUANCES.get(nuance, (nuance, "div"))[1],
                    "libelle_nuance": NUANCES.get(nuance, (nuance, "div"))[0],
                    "libelle": row[f"Libellé de liste {i}"],
                    "sieges": int(nombre(row.get(f"Sièges au CM {i}")) or 0),
                    "voix_pct": nombre(row.get(f"% Voix/exprimés {i}")),
                })
            i += 1
        sortie[code] = {"participation": nombre(row["% Votants"]), "listes": listes}
    return sortie


def elus(url, codes, depuis):
    """code commune -> liste des (sexe, date de naissance) des elus."""
    sortie = {}
    for row in lignes_csv(url):
        code = row.get("CODCOM", "")
        if code in codes:
            sortie.setdefault(code, []).append((row.get("SEXPSN", ""), row.get("DATNAIPSN", "")))
    return sortie


def maires(url, codes):
    sortie = {}
    for row in lignes_csv(url):
        code = row.get("Code de la commune", "")
        if code in codes:
            sortie[code] = {
                "nom": titre_nom(row.get("Prénom de l'élu", ""), row.get("Nom de l'élu", "")),
                "sexe": row.get("Code sexe", ""),
                "depuis": row.get("Date de début de la fonction") or row.get("Date de début du mandat") or None,
            }
    return sortie


def age(naissance, ref):
    try:
        n = dt.date.fromisoformat(naissance)
    except ValueError:
        return None
    return (ref - n).days / 365.25


def ecrire_si_change(chemin, objet):
    nouveau = {k: v for k, v in objet.items() if k != "genere_le"}
    if chemin.exists():
        try:
            ancien = json.loads(chemin.read_text(encoding="utf-8"))
            if {k: v for k, v in ancien.items() if k != "genere_le"} == nouveau:
                return False
        except ValueError:
            pass
    chemin.write_text(json.dumps(objet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return True


def main():
    t0 = time.time()
    villes = json.loads(INDEX_VILLES.read_text(encoding="utf-8"))["villes"]
    codes = {v["insee"]: v["nom"] for v in villes}
    print(f"{len(codes)} villes")
    res_t1 = resultats_communes(url_ressource(DATASET_T1, "résultats", "communes", interdits=("bv", "polynésie", "arrondissement", "secteur")), codes)
    res_t2 = resultats_communes(url_ressource(DATASET_T2, "résultats", "communes", interdits=("bv", "polynésie", "arrondissement", "secteur", "bureau")), codes)
    print(f"résultats : T1 {len(res_t1)} villes, T2 {len(res_t2)} villes ({time.time() - t0:.0f} s)")
    el_t1 = elus(url_ressource(DATASET_T1, "candidats elus", interdits=("polynésie", "arrondissement")), codes, DATE_T1)
    el_t2 = elus(url_ressource(DATASET_T2, "candidats elus", "france entière", interdits=("polynésie", "arrondissement")), codes, DATE_T2)
    print(f"élus : T1 {len(el_t1)} villes, T2 {len(el_t2)} villes ({time.time() - t0:.0f} s)")
    mairies = maires(url_ressource(DATASET_RNE, "maires"), codes)
    print(f"maires : {len(mairies)} ({time.time() - t0:.0f} s)")

    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ref_t2 = dt.date.fromisoformat(DATE_T2)
    sans, ecrits = [], 0
    for code, nom in codes.items():
        # La liste de reference est celle du dernier tour tenu : le second tour
        # si la commune y a voté, sinon le premier.
        tour = 2 if code in res_t2 and sum(l["sieges"] for l in res_t2[code]["listes"]) > 0 else 1
        res = (res_t2 if tour == 2 else res_t1).get(code)
        if not res or not sum(l["sieges"] for l in res["listes"]):
            sans.append(nom)
            continue
        listes = sorted((l for l in res["listes"] if l["sieges"] > 0), key=lambda l: -l["sieges"])
        total = sum(l["sieges"] for l in listes)
        # Parite et age : tous les elus des deux tours, uniquement si leur
        # nombre est exactement celui des sieges.
        personnes = el_t1.get(code, []) + el_t2.get(code, [])
        femmes = age_moyen = None
        if len(personnes) == total:
            femmes = round(100 * sum(1 for s, _ in personnes if s == "F") / total, 1)
            ages = [a for a in (age(n, ref_t2) for _, n in personnes) if a is not None]
            age_moyen = round(sum(ages) / len(ages), 1) if len(ages) == total else None
        fiche = {
            "insee": code, "nom": nom, "scrutin": "Municipales 2026",
            "tour_decisif": tour, "date": DATE_T2 if tour == 2 else DATE_T1,
            "sieges": total, "participation": res["participation"],
            "listes": listes, "femmes_pct": femmes, "age_moyen": age_moyen,
            "maire": mairies.get(code),
            "sources": {
                "resultats": "https://www.data.gouv.fr/fr/datasets/elections-municipales-2026-resultats-du-second-tour/",
                "maires": "https://www.data.gouv.fr/fr/datasets/repertoire-national-des-elus-1/",
            },
            "votes": None,  # derniers votes et ordre du jour : non disponibles de facon uniforme
            "genere_le": maintenant,
        }
        ecrits += ecrire_si_change(SORTIE / f"{code}.json", fiche)
    print(f"terminé en {time.time() - t0:.0f} s ; {ecrits} fichiers écrits ; sans composition : {sans or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
