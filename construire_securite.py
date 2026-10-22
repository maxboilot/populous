#!/usr/bin/env python3
# Construit les chiffres de securite des 100 plus grandes villes
# (onglet « Ma ville », rubrique « Securite »).
#
# Source unique : « Bases statistiques communale, departementale et regionale de
# la delinquance enregistree par la police et la gendarmerie nationales »,
# service statistique ministeriel de la securite interieure (SSMSI, ministere de
# l'Interieur), sur data.gouv.fr. Fichier communal, une ligne par commune, annee
# et indicateur, depuis 2016. Publie une fois par an (mise a jour de juillet).
#
# Ce que mesurent ces chiffres : les crimes et delits ENREGISTRES par la police
# et la gendarmerie, localises au lieu de commission. Ce n'est pas le nombre
# reel d'infractions : l'activite des forces de l'ordre pese sur certains
# indicateurs (stupefiants surtout) et toutes les victimes ne portent pas
# plainte. Les valeurs couvertes par le secret statistique ne sont pas
# diffusees : elles restent null (jamais une valeur inventee).
#
# Sortie : data/securite/index.json (toutes les villes, pour la comparaison)
#          data/securite/<insee>.json (series 2016-derniere annee d'une ville)
import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import sys
import time

import requests

SORTIE = pathlib.Path("data/securite")
INDEX_VILLES = pathlib.Path("data/villes/index.json")
DATASET = "621df2954fa5a3b5a023e23c"
USER_AGENT = "Populous-securite (https://github.com/maxboilot/populous)"
SOURCE_PAGE = "https://www.data.gouv.fr/fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales/"

# cle courte -> libelle exact du fichier. Le « Usage de stupefiants (AFD) » est
# un sous-ensemble de « Usage de stupefiants » (amende forfaitaire delictuelle) :
# on ne le garde pas pour ne pas compter deux fois.
INDICATEURS = {
    "viol_hors":   "Violences physiques hors cadre familial",
    "viol_fam":    "Violences physiques intrafamiliales",
    "viol_sex":    "Violences sexuelles",
    "vol_arme":    "Vols avec armes",
    "vol_violent": "Vols violents sans arme",
    "vol_simple":  "Vols sans violence contre des personnes",
    "cambriolage": "Cambriolages de logement",
    "vol_vehicule": "Vols de véhicule",
    "vol_dans":    "Vols dans les véhicules",
    "vol_access":  "Vols d'accessoires sur véhicules",
    "degrad":      "Destructions et dégradations volontaires",
    "usage":       "Usage de stupéfiants",
    "trafic":      "Trafic de stupéfiants",
    "escroquerie": "Escroqueries et fraudes aux moyens de paiement",
}
PAR_LIBELLE = {v: k for k, v in INDICATEURS.items()}


def get(url, **kw):
    for i in range(4):
        try:
            r = requests.get(url, timeout=(20, 300), headers={"User-Agent": USER_AGENT}, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == 3:
                raise
            time.sleep(3 + 4 * i)


def nombre(texte):
    t = (texte or "").strip().replace(",", ".")
    if t in ("", "NA"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


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
    codes = {v["insee"]: v for v in villes}
    meta = get(f"https://www.data.gouv.fr/api/1/datasets/{DATASET}/").json()
    res = next(r for r in meta["resources"]
               if r["title"].startswith("COM - Base statistique communale") and (r.get("format") or "").lower() == "csv.gz")
    maj = (res.get("last_modified") or "")[:10]
    print(f"fichier : {res['title'][:60]}… mis à jour le {maj}")

    # lignes[commune][indicateur][annee] = (nombre, taux, pop)
    lignes = {}
    flux = get(res["url"], stream=True)
    texte = io.TextIOWrapper(gzip.GzipFile(fileobj=flux.raw), encoding="utf-8-sig", newline="")
    lecteur = csv.DictReader(texte, delimiter=";")
    cle_commune = next(c for c in lecteur.fieldnames if c.upper().startswith("CODGEO"))
    for row in lecteur:
        code = row[cle_commune]
        if code not in codes or row["indicateur"] not in PAR_LIBELLE:
            continue
        diffuse = row["est_diffuse"] == "diff"
        lignes.setdefault(code, {}).setdefault(PAR_LIBELLE[row["indicateur"]], {})[int(row["annee"])] = (
            nombre(row["nombre"]) if diffuse else None, nombre(row["taux_pour_mille"]) if diffuse else None)
    print(f"{len(lignes)} villes lues ({time.time() - t0:.0f} s)")
    if not lignes:
        print("aucune ville trouvée : fichier inattendu", file=sys.stderr)
        return 1

    annees_dispo = sorted({a for ind in lignes.values() for serie in ind.values() for a in serie})
    annee_ref = annees_dispo[-1]
    annees = [a for a in annees_dispo if a >= annee_ref - 9]
    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ecrits = 0
    index = []
    for code, ville in codes.items():
        ind = lignes.get(code)
        if not ind:
            continue
        serie_taux = {k: [ind.get(k, {}).get(a, (None, None))[1] for a in annees] for k in INDICATEURS}
        serie_nb = {k: [ind.get(k, {}).get(a, (None, None))[0] for a in annees] for k in INDICATEURS}
        # Les taux sont arrondis a 2 decimales : assez pour les comparer, sans fausse precision.
        serie_taux = {k: [None if v is None else round(v, 2) for v in vs] for k, vs in serie_taux.items()}
        fiche = {
            "insee": code, "nom": ville["nom"], "annees": annees, "annee_ref": annee_ref,
            "taux": serie_taux, "nombre": serie_nb,
            "genere_le": maintenant,
        }
        ecrits += ecrire_si_change(SORTIE / f"{code}.json", fiche)
        index.append({"insee": code, "nom": ville["nom"], "dep": ville.get("dep"),
                      "v": {k: serie_taux[k][-1] for k in INDICATEURS}})
    fiche_index = {
        "annee_ref": annee_ref, "maj_source": maj,
        "indicateurs": {k: {"libelle": v, "unite": "logements" if k == "cambriolage" else "habitants"} for k, v in INDICATEURS.items()},
        "villes": index,
        "source": {"nom": "SSMSI, ministère de l'Intérieur — délinquance enregistrée par la police et la gendarmerie", "url": SOURCE_PAGE},
        "genere_le": maintenant,
    }
    ecrits += ecrire_si_change(SORTIE / "index.json", fiche_index)
    absentes = [v["nom"] for v in villes if v["insee"] not in lignes]
    print(f"terminé en {time.time() - t0:.0f} s ; {ecrits} fichiers écrits ; année de référence {annee_ref} ; sans données : {absentes or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
