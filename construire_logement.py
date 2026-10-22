#!/usr/bin/env python3
# Construit les chiffres du logement des 100 plus grandes villes
# (onglet « Ma ville », rubrique « Logement »).
#
# Deux sources officielles, ouvertes et mises a jour regulierement :
#
#   1. Permis de construire — « Logements autorises et commences, series
#      mensuelles communales » (Sit@del2, SDES, ministere de la Transition
#      ecologique), via l'API DiDo. Une ligne par commune et par mois. On somme
#      par annee civile COMPLETE ; l'annee en cours, partielle, est ecartee.
#      Couverture : 99 villes sur 100 (pas de donnees pour Noumea).
#
#   2. Prix de l'immobilier — « Demandes de valeurs foncieres geolocalisees »
#      (DVF, DGFiP, republie par Etalab), un fichier par commune et par annee.
#      Prix median au m2 des VENTES d'appartements et de maisons : on ne garde
#      qu'une mutation (= une vente) portant sur un seul logement, de surface
#      connue, et on ecarte les prix au m2 hors de 200 a 30 000 EUR (erreurs de
#      saisie). Paris, Lyon et Marseille sont reconstituees a partir de leurs
#      arrondissements. L'Alsace-Moselle (Strasbourg, Metz, Mulhouse, Colmar),
#      Mayotte et la Nouvelle-Caledonie ne figurent pas dans DVF : ces villes
#      n'ont pas de prix, jamais une valeur inventee. Une commune n'a de prix
#      pour une annee et un type de bien que si elle compte au moins 30 ventes.
#
#   3. Loyers — « Carte des loyers » (ANIL, a partir des annonces SeLoger et
#      leboncoin), une edition par an depuis 2022. ATTENTION : ce sont des
#      estimations EXPERIMENTALES de loyers d'ANNONCE, charges comprises, pour un
#      bien type (appartement de 52 m2, maison de 92 m2), pas les loyers
#      reellement payes. On ne garde que les communes estimees au niveau
#      communal dans CHAQUE edition (condition posee par l'ANIL pour comparer
#      les annees) ; une estimation reposant sur moins de 30 annonces ou sur un
#      modele peu fiable (R2 < 0,5) est signalee « fragile ». Paris, Lyon et
#      Marseille n'ont des loyers que par arrondissement : pas de loyer pour
#      elles. Mention obligatoire de la source : « Estimations ANIL, a partir des
#      donnees du Groupe SeLoger et de leboncoin ».
#
# Sortie : data/logement/index.json (toutes les villes, pour la comparaison)
#          data/logement/<insee>.json (series d'une ville)
import csv
import datetime as dt
import io
import json
import pathlib
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

SORTIE = pathlib.Path("data/logement")
INDEX_VILLES = pathlib.Path("data/villes/index.json")
USER_AGENT = "Populous-logement (https://github.com/maxboilot/populous)"
DIDO = "https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1"
DATASET_SITADEL = "660432ce0b8987ef5dd9465d"
DVF = "https://files.data.gouv.fr/geo-dvf/latest/csv"
ANNEES_DVF = 5            # annees de prix affichees
MIN_VENTES = 30           # en dessous, pas de prix median
PRIX_MIN, PRIX_MAX = 200, 30000
SOURCES = {
    "permis": {"nom": "Sit@del2, SDES (ministère de la Transition écologique) — logements autorisés et commencés",
               "url": "https://www.statistiques.developpement-durable.gouv.fr/catalogue?page=dataset&datasetId=660432ce0b8987ef5dd9465d"},
    "dvf": {"nom": "DVF, DGFiP — demandes de valeurs foncières", "url": "https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres-geolocalisees/"},
    "loyers": {"nom": "Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin (Carte des loyers)", "url": "https://www.data.gouv.fr/fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/"},
}

ARRONDISSEMENTS = {
    "75056": [f"751{n:02d}" for n in range(1, 21)],
    "69123": [f"6938{n}" for n in range(1, 10)],
    "13055": [f"132{n:02d}" for n in range(1, 17)],
}


def get(url, essais=4, **kw):
    for i in range(essais):
        try:
            r = requests.get(url, timeout=(20, 400), headers={"User-Agent": USER_AGENT}, **kw)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == essais - 1:
                raise
            time.sleep(3 + 4 * i)


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


# ------------------------------------------------------------------ permis
def permis(codes):
    """code -> {annee: (autorises, commences)} pour les annees civiles completes."""
    meta = get(f"{DIDO}/datasets/{DATASET_SITADEL}").json()
    rid = meta["datafiles"][0]["rid"]
    r = get(f"{DIDO}/datafiles/{rid}/json", params={
        "CODE_INSEE": "in:" + ",".join(codes), "TYPE_LGT": "eq:Tous Logements", "ANNEE": "gte:2016"})
    lignes = r.json()
    mois = {}
    for x in lignes:
        mois.setdefault(x["CODE_INSEE"], {}).setdefault(int(x["ANNEE"]), {})[x["MOIS"]] = (x["LOG_AUT"] or 0, x["LOG_COM"] or 0)
    sortie = {}
    for code, par_an in mois.items():
        # une annee est complete quand les 12 mois sont presents dans la serie
        sortie[code] = {a: (sum(v[0] for v in m.values()), sum(v[1] for v in m.values()))
                        for a, m in par_an.items() if len(m) == 12}
    dernier = max((int(x["ANNEE"]), x["MOIS"]) for x in lignes) if lignes else None
    return sortie, dernier


# --------------------------------------------------------------------- DVF
def departement(code):
    return code[:3] if code.startswith(("97", "98")) else code[:2]


def prix_commune(code, annee):
    """Liste des (type, prix au m2) des ventes retenues pour une commune et une annee, + derniere date."""
    r = get(f"{DVF}/{annee}/communes/{departement(code)}/{code}.csv", stream=True)
    if r is None:
        return None
    r.encoding = "utf-8"
    lecteur = csv.DictReader(r.iter_lines(decode_unicode=True))
    par_mutation = {}
    derniere = ""
    for row in lecteur:
        if row["nature_mutation"] != "Vente":
            continue
        derniere = max(derniere, row["date_mutation"])
        if row["type_local"] in ("Appartement", "Maison"):
            m = par_mutation.setdefault(row["id_mutation"], {"valeur": row["valeur_fonciere"], "locaux": set()})
            m["locaux"].add((row["type_local"], row["surface_reelle_bati"]))
    ventes = []
    for m in par_mutation.values():
        if len(m["locaux"]) != 1:
            continue                       # vente de plusieurs logements : prix au m2 non attribuable
        type_local, surface = next(iter(m["locaux"]))
        try:
            valeur, surf = float(m["valeur"]), float(surface)
        except ValueError:
            continue
        if surf < 9 or valeur <= 0:
            continue
        p = valeur / surf
        if PRIX_MIN <= p <= PRIX_MAX:
            ventes.append((type_local, p))
    return ventes, derniere


def prix_ville(insee, annees):
    """{annee: {'Appartement': (prix_median, n), 'Maison': (...)}} + derniere date de vente vue, ou None."""
    communes = ARRONDISSEMENTS.get(insee, [insee])
    sortie, derniere = {}, ""
    for a in annees:
        ventes, trouve = [], False
        for c in communes:
            res = prix_commune(c, a)
            if res is None:
                continue
            trouve = True
            ventes += res[0]
            derniere = max(derniere, res[1])
        if not trouve:
            continue
        sortie[a] = {}
        for t in ("Appartement", "Maison"):
            v = [p for tt, p in ventes if tt == t]
            sortie[a][t] = (round(statistics.median(v)), len(v)) if len(v) >= MIN_VENTES else (None, len(v))
    return (sortie, derniere) if sortie else None


# ------------------------------------------------------------------ loyers
LOYER_PREMIERE_ANNEE = 2022
R2_MIN, OBS_MIN = 0.5, 30


def nombre_fr(texte):
    try:
        return float(str(texte).strip().replace(",", "."))
    except ValueError:
        return None


def edition_loyers(annee):
    """(url appartement, url maison, page du jeu de donnees) de l'edition d'une annee, ou None."""
    r = get("https://www.data.gouv.fr/api/1/datasets/", params={
        "q": f"Carte des loyers indicateurs de loyers d'annonce par commune en {annee}", "page_size": 10})
    for d in r.json().get("data", []):
        if f"par commune en {annee}" not in d["title"]:
            continue
        appart = maison = None
        for res in d["resources"]:
            t = res["title"].lower()
            if (res.get("format") or "").lower() != "csv" or "loyer" not in t:
                continue
            if "maison" in t:
                maison = res["url"]
            elif "appartement" in t and "pièces" not in t and "pieces" not in t:
                appart = res["url"]
        if appart and maison:
            return appart, maison, d["page"]
    return None


def lire_loyers(url, codes):
    """code commune -> {loyer, bas, haut, commune (bool), obs, r2} pour les villes voulues."""
    contenu = get(url).content
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = contenu.decode("latin-1")
    sortie = {}
    for row in csv.DictReader(io.StringIO(texte), delimiter=";"):
        code = row.get("INSEE_C", "")
        if code in codes:
            sortie[code] = {
                "loyer": nombre_fr(row.get("loypredm2")), "bas": nombre_fr(row.get("lwr.IPm2")), "haut": nombre_fr(row.get("upr.IPm2")),
                "commune": row.get("TYPPRED") == "commune", "obs": nombre_fr(row.get("nbobs_com")), "r2": nombre_fr(row.get("R2_adj")),
            }
    return sortie


def loyers(codes):
    """{'annees': [...], 'appartement': {annee: {code: ...}}, 'maison': {...}, 'page': url} ou None."""
    annees, par_type, page = [], {"appartement": {}, "maison": {}}, None
    for annee in range(LOYER_PREMIERE_ANNEE, dt.date.today().year + 1):
        ed = edition_loyers(annee)
        if not ed:
            continue
        annees.append(annee)
        par_type["appartement"][annee] = lire_loyers(ed[0], codes)
        par_type["maison"][annee] = lire_loyers(ed[1], codes)
        page = ed[2]
    return ({"annees": annees, **par_type, "page": page} if annees else None)


def fiche_loyers(code, lo, type_bien):
    """Serie 2022-... d'une ville pour un type de bien, ou None si pas de loyer communal dans la derniere edition."""
    annees = lo["annees"]
    dernier = lo[type_bien][annees[-1]].get(code)
    if not dernier or not dernier["commune"] or dernier["loyer"] is None:
        return None
    serie = []
    for a in annees:
        x = lo[type_bien][a].get(code)
        # une edition ou la commune n'est pas estimee au niveau communal n'est pas comparable : on la laisse vide
        serie.append(round(x["loyer"], 1) if x and x["commune"] and x["loyer"] is not None else None)
    fragile = (dernier["r2"] is not None and dernier["r2"] < R2_MIN) or (dernier["obs"] is not None and dernier["obs"] < OBS_MIN)
    return {"serie": serie, "bas": round(dernier["bas"], 1) if dernier["bas"] is not None else None,
            "haut": round(dernier["haut"], 1) if dernier["haut"] is not None else None,
            "obs": int(dernier["obs"]) if dernier["obs"] is not None else None, "fragile": bool(fragile)}


def main():
    t0 = time.time()
    villes = json.loads(INDEX_VILLES.read_text(encoding="utf-8"))["villes"]
    par_code = {v["insee"]: v for v in villes}
    codes = list(par_code)

    aut, dernier = permis(codes)
    print(f"permis : {len(aut)} villes, dernière ligne {dernier} ({time.time() - t0:.0f} s)")
    if not aut:
        print("aucun permis lu : source indisponible", file=sys.stderr)
        return 1
    annees_permis = sorted({a for d in aut.values() for a in d})
    an_ref = annees_permis[-1]
    annees_permis = [a for a in annees_permis if a >= an_ref - 9]

    lo = loyers(set(codes))
    print(f"loyers : éditions {lo['annees'] if lo else 'aucune'} ({time.time() - t0:.0f} s)")
    if lo and lo["page"]:
        SOURCES["loyers"]["url"] = lo["page"]

    annee_dvf = dt.date.today().year          # on essaie l'annee en cours, puis on recule
    annees_dvf = list(range(annee_dvf - ANNEES_DVF, annee_dvf + 1))
    with ThreadPoolExecutor(4) as ex:
        dvf = dict(zip(codes, ex.map(lambda c: prix_ville(c, annees_dvf), codes)))
    annees_prix = sorted({a for r in dvf.values() if r for a in r[0]})
    print(f"DVF : {sum(1 for r in dvf.values() if r)} villes, années {annees_prix} ({time.time() - t0:.0f} s)")
    # l'annee de reference des prix = la plus recente ou au moins la moitie des villes ont des ventes
    annee_prix_ref = None
    for a in reversed(annees_prix):
        if sum(1 for r in dvf.values() if r and a in r[0] and r[0][a]["Appartement"][1] > 0) >= 40:
            annee_prix_ref = a
            break
    annees_prix = [a for a in annees_prix if annee_prix_ref and a <= annee_prix_ref][-ANNEES_DVF:]

    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ecrits, index = 0, []
    for code, ville in par_code.items():
        pop = ville.get("pop")
        p = aut.get(code)
        fiche = {"insee": code, "nom": ville["nom"], "pop": pop, "genere_le": maintenant}
        vi = {"autorise": None, "commence": None, "prix_appart": None, "prix_maison": None, "loyer_appart": None, "loyer_maison": None}
        if p and pop:
            fiche["permis"] = {
                "annees": annees_permis,
                "autorises": [p[a][0] if a in p else None for a in annees_permis],
                "commences": [p[a][1] if a in p else None for a in annees_permis],
                "taux_autorises": [round(p[a][0] / pop * 1000, 2) if a in p else None for a in annees_permis],
                "taux_commences": [round(p[a][1] / pop * 1000, 2) if a in p else None for a in annees_permis],
            }
            vi["autorise"], vi["commence"] = fiche["permis"]["taux_autorises"][-1], fiche["permis"]["taux_commences"][-1]
        r = dvf.get(code)
        if r and annees_prix:
            par_an = r[0]
            fiche["prix"] = {
                "annees": annees_prix,
                "appartement": [par_an.get(a, {}).get("Appartement", (None, 0))[0] for a in annees_prix],
                "ventes_appartement": [par_an.get(a, {}).get("Appartement", (None, 0))[1] for a in annees_prix],
                "maison": [par_an.get(a, {}).get("Maison", (None, 0))[0] for a in annees_prix],
                "ventes_maison": [par_an.get(a, {}).get("Maison", (None, 0))[1] for a in annees_prix],
                "jusqu_a": r[1] or None,
            }
            vi["prix_appart"], vi["prix_maison"] = fiche["prix"]["appartement"][-1], fiche["prix"]["maison"][-1]
        if lo:
            la, lm = fiche_loyers(code, lo, "appartement"), fiche_loyers(code, lo, "maison")
            if la or lm:
                fiche["loyers"] = {"annees": lo["annees"], "annee_ref": lo["annees"][-1]}
                if la:
                    fiche["loyers"]["appartement"] = la
                    vi["loyer_appart"] = la["serie"][-1]
                if lm:
                    fiche["loyers"]["maison"] = lm
                    vi["loyer_maison"] = lm["serie"][-1]
        if "permis" not in fiche and "prix" not in fiche and "loyers" not in fiche:
            continue
        ecrits += ecrire_si_change(SORTIE / f"{code}.json", fiche)
        index.append({"insee": code, "nom": ville["nom"], "dep": ville.get("dep"), "v": vi})
    fiche_index = {
        "annee_permis": annees_permis[-1], "annee_prix": annees_prix[-1] if annees_prix else None,
        "annee_loyers": lo["annees"][-1] if lo else None,
        "villes": index, "sources": SOURCES, "genere_le": maintenant,
    }
    ecrits += ecrire_si_change(SORTIE / "index.json", fiche_index)
    sans_prix = [v["nom"] for v in villes if not dvf.get(v["insee"])]
    sans_loyer = [v["nom"] for v in villes if not any(x["insee"] == v["insee"] and x["v"].get("loyer_appart") is not None for x in index)]
    sans_permis = [v["nom"] for v in villes if v["insee"] not in aut]
    print(f"terminé en {time.time() - t0:.0f} s ; {ecrits} fichiers écrits ; sans permis : {sans_permis or 'aucune'} ; sans prix : {sans_prix or 'aucune'} ; sans loyer appartement : {sans_loyer or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
