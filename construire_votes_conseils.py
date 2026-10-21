#!/usr/bin/env python3
# Votes des conseils municipaux : derniere seance publiee, par ville.
#
# Il n'existe pas de base nationale des votes des conseils municipaux : chaque
# ville publie (ou non) ses deliberations a sa facon. Ce script a donc un
# adaptateur par ville, et ne couvre que les villes dont la source est ouverte,
# structuree et verifiee. Une ville sans adaptateur n'a simplement pas de
# fichier : l'app affiche « pas encore disponible », jamais une valeur inventee.
#
# Villes branchees (verifie le 21 octobre 2026) :
#   Toulouse (31555)         Toulouse Metropole Open Data, « Deliberations a
#                            partir de mars 2026 - Mairie de Toulouse » : type de
#                            vote et position des groupes (pas de decompte).
#   Clermont-Ferrand (63113) Clermont Auvergne Metropole Open Data,
#                            « Deliberations votees » : decompte pour / contre /
#                            abstention, MAIS arrete a septembre 2024 (ancien
#                            conseil, avant les municipales de mars 2026).
#
# Constat pour les autres villes demandees (a revoir si leurs sources changent) :
#   Paris      ordres du jour et PDF, pas de resultats de votes en donnees ouvertes.
#   Lyon       deliberations en PDF ; pages d'actes bloquees aux requetes automatiques.
#   Bordeaux   documents du conseil en PDF ; site indisponible lors des essais.
#   Marseille  liste des deliberations en donnees ouvertes, arretee a 2024, sans
#              resultat de vote (lien vers le texte seulement).
#
# Sortie : data/votes/<insee>.json
import datetime as dt
import json
import pathlib
import re
import sys
import time

import requests

SORTIE = pathlib.Path("data/votes")
CONSEILS = pathlib.Path("data/conseils")
USER_AGENT = "Populous-votes (https://github.com/maxboilot/populous)"
MOIS = {"janv": 1, "janvier": 1, "févr": 2, "fevr": 2, "février": 2, "mars": 3, "avr": 4, "avril": 4, "mai": 5,
        "juin": 6, "juil": 7, "juillet": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}


def get_json(url, params, essais=4):
    for i in range(essais):
        try:
            r = requests.get(url, params=params, timeout=90, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == essais - 1:
                raise
            time.sleep(2 + 3 * i)


def toutes_les_lignes(base, dataset, **params):
    lignes, decalage = [], 0
    while True:
        page = get_json(f"{base}/api/explore/v2.1/catalog/datasets/{dataset}/records",
                        {"limit": 100, "offset": decalage, **params}).get("results", [])
        lignes += page
        if len(page) < 100:
            return lignes
        decalage += 100


def espaces(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


def ecrire_si_change(chemin, objet):
    """Ne reecrit un fichier que si son contenu a change (hors `genere_le`)."""
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


def date_election(insee):
    """Date du scrutin municipal 2026 de la ville (fichier conseils), pour savoir
    si la derniere seance publiee date de l'ancien conseil."""
    try:
        return json.loads((CONSEILS / f"{insee}.json").read_text(encoding="utf-8"))["date"]
    except (OSError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------- Toulouse
def date_toulouse(texte):
    m = re.match(r"(\d{1,2})-([a-zéèûô]+)\.?-(\d{2,4})$", (texte or "").strip().lower())
    if not m or m.group(2) not in MOIS:
        return None
    an = int(m.group(3)) + (2000 if int(m.group(3)) < 100 else 0)
    return dt.date(an, MOIS[m.group(2)], int(m.group(1))).isoformat()


def positions_toulouse(texte):
    """« Contre\\n\\n\\tGroupe A\\n\\tGroupe B\\n\\nAbstention\\n\\n\\tGroupe C » -> dict."""
    sortie = {"contre": [], "abstention": [], "ne_participe_pas": [], "pour": []}
    cles = {"Contre": "contre", "Abstention": "abstention", "Pour": "pour", "Ne participe pas au vote": "ne_participe_pas"}
    morceaux = re.split(r"(?m)^(Contre|Abstention|Pour|Ne participe pas au vote)[ \t]*$", texte or "")
    for i in range(1, len(morceaux), 2):
        for nom in re.split(r"\n\s*", morceaux[i + 1].strip()):
            if nom.strip():
                sortie[cles[morceaux[i]]].append(espaces(nom))
    return {k: v for k, v in sortie.items() if v}


def toulouse():
    base, dataset = "https://data.toulouse-metropole.fr", "deliberations-a-partir-de-mars-2026-mairie-de-toulouse"
    lignes = toutes_les_lignes(base, dataset)
    for x in lignes:
        x["_date"] = date_toulouse(x.get("date_conseil"))
    lignes = [x for x in lignes if x["_date"]]
    derniere = max(x["_date"] for x in lignes)
    seance = [x for x in lignes if x["_date"] == derniere]
    types = [espaces(x.get("type_vote")) for x in seance]
    unanimite = sum(1 for t in types if t == "Adopté à l'unanimité")
    majorite = sum(1 for t in types if t == "Adopté")
    rejetees = sum(1 for t in types if t == "Rejeté")
    prend_acte = sum(1 for t in types if t.startswith("Le Conseil Municipal prend acte"))
    retirees = sum(1 for t in types if t.startswith("Retiré"))

    def rang(p):  # rejetes d'abord, puis contre, puis abstentions
        return (0 if p["resultat"] == "rejete" else 1, -len(p["positions"].get("contre", [])),
                -len(p["positions"].get("abstention", [])), p["titre"])
    points = []
    for x in seance:
        t = espaces(x.get("type_vote"))
        pos = positions_toulouse(x.get("vote"))
        if t not in ("Adopté", "Rejeté") or not (t == "Rejeté" or pos.get("contre") or pos.get("abstention")):
            continue
        points.append({"titre": espaces(x["titre"]), "resultat": "rejete" if t == "Rejeté" else "adopte",
                       "positions": {k: v for k, v in pos.items() if k in ("contre", "abstention")}})
    points.sort(key=rang)
    return {
        "insee": "31555", "nom": "Toulouse",
        "source": {"nom": "Toulouse Métropole Open Data — délibérations de la mairie depuis mars 2026",
                   "url": f"{base}/explore/dataset/{dataset}/"},
        "derniere_seance": {
            "date": derniere, "total": len(seance), "unanimite": unanimite, "majorite": majorite,
            "rejetees": rejetees, "prend_acte": prend_acte, "retirees": retirees,
            "contestees": len(points), "points": points[:6],
        },
    }


# ---------------------------------------------------------- Clermont-Ferrand
def clermont():
    base, dataset = "https://opendata.clermontmetropole.eu", "deliberations-votees-ville-de-clermont-ferrand"
    # Les 100 plus recentes suffisent : une seance compte quelques dizaines de points.
    recentes = get_json(f"{base}/api/explore/v2.1/catalog/datasets/{dataset}/records",
                        {"limit": 100, "order_by": "delib_date desc"}).get("results", [])
    derniere = max(x["delib_date"] for x in recentes)
    seance = [x for x in recentes if x["delib_date"] == derniere]
    avec = [x for x in seance if x.get("vote_pour") is not None]
    unanimite = majorite = rejetees = egalite = 0
    points = []
    for x in avec:
        pour, contre, abst = int(x["vote_pour"]), int(x["vote_contre"] or 0), int(x["vote_abstention"] or 0)
        if contre == 0 and abst == 0:
            unanimite += 1
            continue
        res = "adopte" if pour > contre else ("rejete" if contre > pour else "egalite")
        majorite += res == "adopte"
        rejetees += res == "rejete"
        egalite += res == "egalite"
        points.append({"titre": espaces(x["delib_objet"]), "resultat": res,
                       "pour": pour, "contre": contre, "abstention": abst})
    points.sort(key=lambda p: (-(p["contre"] + p["abstention"]) / max(1, p["pour"] + p["contre"] + p["abstention"]), p["titre"]))
    return {
        "insee": "63113", "nom": "Clermont-Ferrand",
        "source": {"nom": "Clermont Auvergne Métropole Open Data — délibérations votées de la Ville",
                   "url": f"{base}/explore/dataset/{dataset}/"},
        "derniere_seance": {
            "date": derniere, "total": len(seance), "unanimite": unanimite, "majorite": majorite,
            "rejetees": rejetees, "egalite": egalite, "sans_resultat": len(seance) - len(avec),
            "contestees": len(points), "points": points[:6],
        },
    }


ADAPTATEURS = [toulouse, clermont]


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ecrits = 0
    for adaptateur in ADAPTATEURS:
        try:
            fiche = adaptateur()
        except (requests.RequestException, KeyError, ValueError) as e:
            # Une source en panne ne doit pas effacer les donnees deja publiees.
            print(f"[avertissement] {adaptateur.__name__} : {e}", file=sys.stderr)
            continue
        elec = date_election(fiche["insee"])
        fiche["ancien_conseil"] = bool(elec and fiche["derniere_seance"]["date"] < elec)
        fiche["a_venir"] = []   # ordres du jour a venir : aucune source ouverte branchee
        fiche["genere_le"] = maintenant
        s = fiche["derniere_seance"]
        print(f"{fiche['nom']} : séance du {s['date']} · {s['total']} points · {s['unanimite']} unanimité · "
              f"{s['majorite']} majorité · {s['rejetees']} rejetées · ancien conseil : {fiche['ancien_conseil']}")
        ecrits += ecrire_si_change(SORTIE / f"{fiche['insee']}.json", fiche)
    print(f"{ecrits} fichier(s) écrit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
