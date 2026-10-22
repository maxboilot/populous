#!/usr/bin/env python3
# Construit la liste des elus de chaque conseil municipal des 100 plus grandes
# villes (onglet « Ma ville », bloc « Conseil municipal » > « Les elus »).
#
# Une seule source, le ministere de l'Interieur, sur data.gouv.fr :
#   - « Repertoire national des elus » (fichier des conseillers municipaux) :
#     qui siege aujourd'hui, avec sexe, annee de naissance, categorie
#     socio-professionnelle, date de debut de mandat et fonction (maire, Ne
#     adjoint). Mis a jour chaque trimestre ;
#   - « Elections municipales 2026 » (fichiers « Candidats Elus ») : la nuance
#     de liste de chaque elu de mars 2026, ce qui permet de rattacher chaque
#     conseiller a sa liste.
# Les deux jeux sont rapproches par commune + nom + prenom + date de naissance
# (la date de naissance complete sert seulement au rapprochement : seule
# l'annee de naissance est conservee).
#
# Les changements depuis l'election sont deduits du repertoire lui-meme : un
# elu absent de la liste de mars 2026 et dont le mandat debute apres
# l'installation du conseil est un remplacant (date de debut de mandat), et une fonction qui debute bien apres l'installation du conseil est
# un changement de fonction. Rien n'est devine : un elu qui ne se rapproche pas
# de la liste de mars reste sans liste (l = null).
#
# Prerequis : data/conseils/<insee>.json (construire_conseils.py).
# Sortie : data/elus/<insee>.json
import collections
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys
import time
import unicodedata

SORTIE = pathlib.Path("data/elus")
CONSEILS = pathlib.Path("data/conseils")
INDEX_VILLES = pathlib.Path("data/villes/index.json")
DELAI_INSTALLATION = 7   # jours : une fonction qui debute plus tard que l'installation + 7 j est un changement

_spec = importlib.util.spec_from_file_location("construire_conseils", pathlib.Path(__file__).with_name("construire_conseils.py"))
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


def cle(commune, nom, prenom, naissance):
    def plat(s):
        s = unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z]", "", s)
    return (commune, plat(nom), plat(prenom), (naissance or "")[:10])


def fonction(libelle):
    """« 18ème adjoint au Maire » -> « 18e adjoint » ; « 1er adjoint au Maire » -> « 1er adjoint »."""
    l = (libelle or "").strip()
    if not l:
        return ""
    m = re.match(r"(\d+)(?:er|ère|ème|e)\s+adjoint", l, re.I)
    if m:
        n = int(m.group(1))
        return "1er adjoint" if n == 1 else f"{n}e adjoint"
    if re.match(r"maire d[ée]l[ée]gu[ée]", l, re.I):
        return "Maire délégué"
    if re.match(r"maire$", l, re.I):
        return "Maire"
    return l


def jour(texte):
    try:
        return dt.date.fromisoformat((texte or "")[:10])
    except ValueError:
        return None


def candidats_elus(codes):
    """(commune, nom, prenom, naissance) -> code de nuance de liste, pour les deux tours."""
    sortie = {}
    for dataset, mots in ((cc.DATASET_T1, ("candidats elus",)), (cc.DATASET_T2, ("candidats elus", "france entière"))):
        url = cc.url_ressource(dataset, *mots, interdits=("polynésie", "arrondissement"))
        for row in cc.lignes_csv(url):
            code = row.get("CODCOM", "")
            if code in codes:
                sortie[cle(code, row.get("NOMPSN"), row.get("PREPSN"), row.get("DATNAIPSN"))] = row.get("CODE_NUANCE_DE_LISTE", "")
    return sortie


def conseillers(codes):
    url = cc.url_ressource(cc.DATASET_RNE, "conseillers-municipaux")
    parcommune = collections.defaultdict(list)
    for row in cc.lignes_csv(url):
        if row["Code de la commune"] in codes:
            parcommune[row["Code de la commune"]].append(row)
    return parcommune


def date_maj_repertoire():
    meta = cc.get(f"https://www.data.gouv.fr/api/1/datasets/{cc.DATASET_RNE}/").json()
    for res in meta["resources"]:
        if "conseillers-municipaux" in res["title"].lower():
            return (res.get("last_modified") or "")[:10] or None
    return None


def main():
    t0 = time.time()
    villes = json.loads(INDEX_VILLES.read_text(encoding="utf-8"))["villes"]
    codes = {v["insee"]: v["nom"] for v in villes}
    nuances = candidats_elus(codes)
    print(f"candidats élus : {len(nuances)} ({time.time() - t0:.0f} s)")
    rne = conseillers(codes)
    maj_rne = date_maj_repertoire()
    print(f"répertoire : {sum(len(v) for v in rne.values())} conseillers, mis à jour le {maj_rne} ({time.time() - t0:.0f} s)")

    SORTIE.mkdir(parents=True, exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ecrits, sans = 0, []
    stats = collections.Counter()
    for code, nom in codes.items():
        try:
            conseil = json.loads((CONSEILS / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sans.append(nom)
            continue
        lignes = rne.get(code, [])
        if not lignes:
            sans.append(nom)
            continue
        date_scrutin = jour(conseil["date"])
        par_nuance = collections.defaultdict(list)
        for i, l in enumerate(conseil["listes"]):
            par_nuance[l["nuance"]].append(i)
        # Installation du conseil : date de debut de fonction la plus frequente.
        debuts = collections.Counter(jour(r["Date de début de la fonction"]) for r in lignes if r["Date de début de la fonction"])
        installation = debuts.most_common(1)[0][0] if debuts else None
        limite = installation + dt.timedelta(days=DELAI_INSTALLATION) if installation else None

        elus, changements, rapproches = [], [], set()
        for r in lignes:
            k = cle(code, r["Nom de l'élu"], r["Prénom de l'élu"], r["Date de naissance"])
            f = fonction(r["Libellé de la fonction"])
            debut_mandat, debut_fonction = jour(r["Date de début du mandat"]), jour(r["Date de début de la fonction"])
            liste = None
            if k in nuances:
                rapproches.add(k)
                idx = par_nuance.get(nuances[k], [])
                liste = idx[0] if len(idx) == 1 else None    # deux listes de meme nuance : on ne devine pas
                stats["rapproches"] += 1
                stats["liste_ambigue"] += len(idx) > 1
                if f and limite and debut_fonction and debut_fonction > limite:
                    changements.append({"d": debut_fonction.isoformat(), "t": "fonction",
                                        "n": cc.titre_nom(r["Prénom de l'élu"], r["Nom de l'élu"]), "f": f})
            elif debut_mandat and (installation or date_scrutin) and debut_mandat > (installation or date_scrutin):
                stats["arrivees"] += 1
                changements.append({"d": debut_mandat.isoformat(), "t": "arrivee",
                                    "n": cc.titre_nom(r["Prénom de l'élu"], r["Nom de l'élu"]), "f": f})
            else:
                stats["non_rapproches"] += 1
            naissance = jour(r["Date de naissance"])
            elus.append({
                "n": cc.titre_nom(r["Prénom de l'élu"], r["Nom de l'élu"]),
                "s": r["Code sexe"],
                "an": naissance.year if naissance else None,
                "p": r["Libellé de la catégorie socio-professionnelle"] or None,
                "l": liste,
                "u": nuances.get(k),   # nuance de la liste : sert quand deux listes en partagent une (l = null)
                "f": f,
            })
        # Maire, puis adjoints par rang, puis les autres par ordre alphabetique.
        def rang(e):
            if e["f"] == "Maire":
                return (0, 0, e["n"])
            m = re.match(r"(\d+)", e["f"])
            return (1, int(m.group(1)), e["n"]) if m else ((2, 0, e["n"]) if e["f"] else (3, 0, e["n"]))
        elus.sort(key=rang)
        changements.sort(key=lambda c: (c["d"], c["n"]), reverse=True)
        fiche = {
            "insee": code, "nom": nom, "date": conseil["date"],
            "sieges": conseil["sieges"], "ecart": len(elus) - conseil["sieges"],
            "installation": installation.isoformat() if installation else None,
            "repertoire_maj": maj_rne,
            "maj": changements[0]["d"] if changements else None,
            "changements": changements,
            "elus": elus,
            "genere_le": maintenant,
        }
        ecrits += cc.ecrire_si_change(SORTIE / f"{code}.json", fiche)
    print(f"terminé en {time.time() - t0:.0f} s ; {ecrits} fichiers écrits ; sans fiche : {sans or 'aucune'} ; {dict(stats)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
