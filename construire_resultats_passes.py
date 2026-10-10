#!/usr/bin/env python3
"""Construit data/resultats_passes.json : premier tour de la présidentielle
2017 et 2022, pour les personnes listées dans data/candidats.json.

Exécution unique (les résultats passés ne changent plus), à relancer
seulement si la liste des candidats s'élargit.

- 2022 : ministère de l'Intérieur, résultats définitifs du 1er tour, niveau
  « France entière » (data.gouv.fr). Fichier téléchargé à l'exécution ; on peut
  fournir une copie locale avec --fichier-2022.
- 2017 : déclaration du Conseil constitutionnel du 26 avril 2017 (décision
  n° 2017-169 PDR), chiffres recopiés ci-dessous ; les pourcentages sont
  calculés sur les suffrages exprimés.
"""
import argparse, datetime, json, re, sys, urllib.request

URL_2022 = ("https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-"
            "resultats-definitifs-du-1er-tour/20220414-152200/resultats-par-niveau-fe-t1-france-entiere.txt")
PAGE_2022 = "https://www.data.gouv.fr/datasets/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/"
PAGE_2017 = "https://www.conseil-constitutionnel.fr/decision/2017/2017169PDR.htm"

EXPRIMES_2017 = 36054394
VOIX_2017 = {  # nom de famille en majuscules -> voix (décision 2017-169 PDR)
    "DUPONT-AIGNAN": 1695000, "LE PEN": 7678491, "MACRON": 8656346, "HAMON": 2291288,
    "ARTHAUD": 232384, "POUTOU": 394505, "CHEMINADE": 65586, "LASSALLE": 435301,
    "MÉLENCHON": 7059951, "ASSELINEAU": 332547, "FILLON": 7212995,
}
# clé de data/candidats.json -> nom de famille du bulletin
NOMS = {"arthaud": "ARTHAUD", "asselineau": "ASSELINEAU", "attal": "ATTAL", "bertrand": "BERTRAND",
        "dupont-aignan": "DUPONT-AIGNAN", "le_pen": "LE PEN", "lisnard": "LISNARD",
        "melenchon": "MÉLENCHON", "philippe": "PHILIPPE", "philippot": "PHILIPPOT",
        "zemmour": "ZEMMOUR", "retailleau": "RETAILLEAU", "roussel": "ROUSSEL",
        "tondelier": "TONDELIER", "villepin": "VILLEPIN"}

def lire_2022(chemin):
    if chemin:
        brut = open(chemin, "rb").read()
    else:
        brut = urllib.request.urlopen(URL_2022, timeout=60).read()
    champs = brut.decode("latin-1").splitlines()[1].split(";")
    # 18 colonnes de synthèse puis 7 colonnes par candidat
    # (panneau;sexe;nom;prénom;voix;%voix/ins;%voix/exp)
    exprimes = int(champs[14])
    res = {}
    for i in range(17, len(champs) - 6, 7):
        nom, voix, pct = champs[i + 2], int(champs[i + 4]), float(champs[i + 6].replace(",", "."))
        res[nom] = {"voix": voix, "pct": pct}
    return exprimes, res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichier-2022")
    ap.add_argument("--sortie", default="data/resultats_passes.json")
    a = ap.parse_args()
    exprimes22, res22 = lire_2022(a.fichier_2022)
    if len(res22) != 12:
        sys.exit("2022 : %d candidats lus au lieu de 12, format inattendu" % len(res22))
    if sum(v["voix"] for v in res22.values()) != exprimes22:
        sys.exit("2022 : la somme des voix ne fait pas les suffrages exprimés")
    if sum(VOIX_2017.values()) != EXPRIMES_2017:
        sys.exit("2017 : la somme des voix ne fait pas les suffrages exprimés")
    res17 = {n: {"voix": v, "pct": round(100 * v / EXPRIMES_2017, 2)} for n, v in VOIX_2017.items()}
    par_candidat = {}
    for cle, nom in NOMS.items():
        e = {}
        if nom in res17: e["2017"] = res17[nom]
        if nom in res22: e["2022"] = res22[nom]
        if e: par_candidat[cle] = e
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elections": {
            "2017": {"libelle": "Présidentielle 2017, premier tour (23 avril)", "exprimes": EXPRIMES_2017,
                     "source_titre": "Conseil constitutionnel, décision 2017-169 PDR", "source_url": PAGE_2017},
            "2022": {"libelle": "Présidentielle 2022, premier tour (10 avril)", "exprimes": exprimes22,
                     "source_titre": "Ministère de l'Intérieur, résultats définitifs (data.gouv.fr)", "source_url": PAGE_2022},
        },
        "par_candidat": par_candidat,
    }
    with open(a.sortie, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("OK :", {c: {y: v["pct"] for y, v in e.items()} for c, e in par_candidat.items()})

if __name__ == "__main__":
    main()
