#!/usr/bin/env python3
# Construit les donnees de l'onglet « Ma ville » : finances et fiscalite des
# 100 plus grandes villes de France.
#
# Sources (toutes ouvertes, interrogees via l'API de l'OFGL, l'Observatoire
# des finances et de la gestion publique locales) :
#   - Comptes des communes 2018-2025 (dataset ofgl-base-communes), issus de la
#     DGFiP : depenses, recettes, dette, epargne, impots locaux...
#   - Fiscalite directe locale (dataset base-fiscale-simplifiee) : taux de
#     taxe fonciere vote par la commune.
#
# Sorties :
#   data/villes/index.json     une ligne par ville, dernieres valeurs (comparaison)
#   data/villes/<insee>.json   historique complet d'une ville (ecran de detail)
#
# Regle de la maison : aucune valeur inventee. Une valeur absente de la source
# reste null, jamais zero.
#
# Le classement par population vient de geo.api.gouv.fr (population legale).
# Paris, Lyon et Marseille sont traitees comme des communes entieres.
import datetime as dt
import json
import pathlib
import sys
import time

import requests

NB_VILLES = 100
ANNEE_MIN = 2018
SORTIE = pathlib.Path("data/villes")
OFGL = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"
USER_AGENT = "Populous-villes (https://github.com/maxboilot/populous)"

# Agregat OFGL -> cle courte. Tous exprimes en euros PAR HABITANT, sauf
# "dep_total" (euros) pour afficher le budget total.
AGREGATS = {
    "Dépenses totales": "dep",
    "Recettes totales": "rec",
    "Frais de personnel": "pers",
    "Achats et charges externes": "achats",
    "Dépenses d'intervention": "interv",
    "Dépenses d'équipement": "equip",
    "Annuité de la dette": "annuite",
    "Encours de dette": "dette",
    "Impôts locaux": "imp",
    "Autres impôts et taxes": "autimp",
    "Concours de l'Etat": "etat",
    "Ventes de biens et services": "ventes",
    "Subventions reçues et participations": "subrec",
    "Emprunts hors GAD": "emprunts",
    "Epargne brute": "epargne",
}


def get_json(url, params, essais=4):
    for i in range(essais):
        try:
            r = requests.get(url, params=params, timeout=90, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == essais - 1:
                raise
            time.sleep(2 + i * 3)


def ecrire_si_change(chemin, objet):
    """N'ecrit le fichier que si le contenu a change, hors horodatage
    `genere_le` : sinon chaque passage du pipeline committerait 101 fichiers
    identiques."""
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


def plus_grandes_villes():
    communes = get_json(
        "https://geo.api.gouv.fr/communes",
        {"fields": "nom,code,population,departement", "type": "commune-actuelle"},
    )
    communes = [c for c in communes if c.get("population")]
    communes.sort(key=lambda c: -c["population"])
    return communes[:NB_VILLES]


def finances_ville(insee):
    """Serie annuelle des agregats pour le budget principal d'une commune."""
    liste = ", ".join('"%s"' % a for a in AGREGATS)
    # L'API plafonne a 100 lignes par appel : 15 agregats x 8 annees = 120
    # lignes, donc on pagine (sans cela, les deux annees les plus recentes
    # etaient tronquees en silence).
    lignes, decalage = [], 0
    while True:
        page = get_json(
            f"{OFGL}/ofgl-base-communes/records",
            {
                "limit": 100, "offset": decalage,
                "order_by": "exer, agregat",
                "where": f'insee="{insee}" and type_de_budget="Budget principal" and agregat in ({liste})',
                "select": "exer,agregat,euros_par_habitant,montant,ptot",
            },
        ).get("results", [])
        lignes += page
        if len(page) < 100:
            break
        decalage += 100
    par_annee = {}
    for ligne in lignes:
        annee = int(str(ligne["exer"])[:4])
        cle = AGREGATS[ligne["agregat"]]
        entree = par_annee.setdefault(annee, {})
        if ligne["euros_par_habitant"] is not None:
            entree[cle] = round(ligne["euros_par_habitant"], 1)
        if cle == "dep" and ligne["montant"] is not None:
            entree["dep_total"] = round(ligne["montant"])
    return par_annee


def taxe_fonciere_ville(insee):
    """Taux de taxe fonciere (bati) vote par la commune, par annee."""
    donnees = get_json(
        f"{OFGL}/base-fiscale-simplifiee/records",
        {
            "limit": 40,
            "where": f'idcom="{insee}" and dispositif_fiscal="TFPB" and destinataire="Commune"',
            "select": "exer,taux_vote,produit",
        },
    )
    sortie = {}
    for ligne in donnees.get("results", []):
        if ligne["taux_vote"] is None:
            continue
        annee = int(str(ligne["exer"])[:4])
        sortie[annee] = {"taux": round(ligne["taux_vote"], 2),
                         "produit": round(ligne["produit"]) if ligne["produit"] is not None else None}
    return sortie


def derniere_annee_complete(finances):
    """Derniere annee pour laquelle 90 % des villes ont des depenses totales :
    l'annee en cours de publication est souvent partielle."""
    for annee in range(dt.date.today().year, ANNEE_MIN - 1, -1):
        presentes = sum(1 for f in finances.values() if f.get(annee, {}).get("dep") is not None)
        if presentes >= 0.9 * len(finances):
            return annee
    raise RuntimeError("aucune annee complete")


def main():
    t0 = time.time()
    villes = plus_grandes_villes()
    print(f"{len(villes)} villes, plus grande : {villes[0]['nom']}")
    finances, fiscal = {}, {}
    for i, v in enumerate(villes):
        finances[v["code"]] = finances_ville(v["code"])
        fiscal[v["code"]] = taxe_fonciere_ville(v["code"])
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(villes)} ({time.time() - t0:.0f} s)")
    derniere = derniere_annee_complete(finances)
    annees = list(range(ANNEE_MIN, derniere + 1))
    # Selon la documentation de l'OFGL, les comptes d'une annee Y sont
    # provisoires jusqu'a la publication des balances definitives, fin
    # decembre de Y+1 (constate pour 2025 : 97 communes encore absentes). Les
    # chiffres affiches et les comparaisons s'appuient sur la derniere annee
    # DEFINITIVE ; l'annee provisoire reste dans l'historique, signalee.
    provisoire = derniere if dt.date.today() < dt.date(derniere + 1, 12, 31) else None
    reference = derniere - 1 if provisoire else derniere
    print("derniere annee complete :", derniere, "| provisoire :", provisoire, "| reference :", reference)

    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = []
    cles = list(AGREGATS.values())
    for v in villes:
        code = v["code"]
        serie = {k: [finances[code].get(a, {}).get(k) for a in annees] for k in cles}
        serie["dep_total"] = [finances[code].get(a, {}).get("dep_total") for a in annees]
        tf = {"annees": [a for a in sorted(fiscal[code])],
              "taux": [fiscal[code][a]["taux"] for a in sorted(fiscal[code])],
              "produit": [fiscal[code][a]["produit"] for a in sorted(fiscal[code])]}
        dep_code = v["departement"]["code"]
        fiche = {
            "insee": code, "nom": v["nom"], "pop": v["population"], "dep": dep_code,
            "dep_nom": v["departement"]["nom"],
            "annee_ref": reference, "annee_provisoire": provisoire,
            "annees": annees, "serie": serie, "tf": tf,
            "sources": {
                "finances": "https://data.ofgl.fr/explore/dataset/ofgl-base-communes/",
                "fiscalite": "https://data.ofgl.fr/explore/dataset/base-fiscale-simplifiee/",
            },
            "genere_le": maintenant,
        }
        ecrire_si_change(SORTIE / f"{code}.json", fiche)
        i_ref = annees.index(reference)
        courant = {k: serie[k][i_ref] for k in cles}
        courant["tf"] = (dict(zip(tf["annees"], tf["taux"])).get(reference))
        index.append({"insee": code, "nom": v["nom"], "pop": v["population"], "dep": dep_code, "v": courant})
    ecrire_si_change(SORTIE / "index.json", {"annee_ref": reference, "annee_provisoire": provisoire,
                                             "genere_le": maintenant, "villes": index})
    manquantes = [v["nom"] for v in villes if finances[v["code"]].get(reference, {}).get("dep") is None]
    print(f"termine en {time.time() - t0:.0f} s ; sans donnees {reference} : {manquantes or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
