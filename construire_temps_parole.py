#!/usr/bin/env python3
"""Construit data/temps_parole.json : temps de parole à la télévision et à la
radio des personnes listées dans data/candidats.json, d'après les relevés
mensuels de l'Arcom (open data, Licence Ouverte 2.0).

Source : jeu de données « Temps de parole des partis et personnalités
politiques » de l'Arcom sur data.gouv.fr. Un fichier CSV par mois (personnalités
politiques), tous services confondus (chaînes généralistes, chaînes
d'information, radios) et tous types d'émission (JT, magazines, programmes).

Les relevés distinguent le temps de parole d'une personne en tant que membre du
gouvernement (lignes « Ministre », « Premier Ministre », comptées à part par
l'Arcom) de son temps de parole attribué à son parti. On suit cette règle :
`secondes` ne contient que le temps attribué à un parti ou à une étiquette,
`secondes_gouvernement` le reste.

L'Arcom ne publie un mois que plusieurs mois après sa diffusion : on affiche
donc le cumul des 12 derniers mois PUBLIÉS, avec la période exacte. Le script
est idempotent : sans nouveau mois publié, il réécrit le même contenu.
"""
import csv, datetime, io, json, re, ssl, subprocess, sys, unicodedata, urllib.error, urllib.request

DATASET = "temps-de-parole-des-partis-et-personnalites-politiques-elections-municipales-2026"
API = "https://www.data.gouv.fr/api/1/datasets/%s/" % DATASET
PAGE = "https://www.data.gouv.fr/datasets/%s" % DATASET
UA = "Populous/1.0 (+https://maxboilot.github.io/populous/)"
NB_MOIS = 12
MOIS = {"jan": 1, "janv": 1, "fev": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juil": 7,
        "aout": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12}


def sans_accents(t):
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode("ascii")


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except (ssl.SSLError, urllib.error.URLError) as e:
        if "CERTIFICATE" not in str(e).upper():
            raise
        # Python du Mac sans certificats racine : même requête via curl.
        return subprocess.run(["curl", "-sSL", "-m", "60", "-A", UA, url], check=True, capture_output=True).stdout


def est_gouvernement(appartenance):
    return re.search(r"ministre|gouvernement|secretaire d'etat", sans_accents(appartenance).lower()) is not None


def cle_nom(t):
    return re.sub(r"\s+", " ", sans_accents(t).upper()).strip()


def mois_du_fichier(titre, cree):
    """(année, mois) d'un fichier mensuel « personnalités », ou None."""
    t = sans_accents(titre).lower()
    if "personnalit" not in t:
        return None
    m = re.search(r"municipales_2026_([a-z]+)_?(\d{2})?_", t) or re.search(r"_([a-z]+)_(\d{2})_personnalit", t)
    if not m or m.group(1) not in MOIS:
        return None
    mois = MOIS[m.group(1)]
    if m.group(2):
        return 2000 + int(m.group(2)), mois
    # pas d'année dans le titre : le mois est publié après coup, donc un mois
    # postérieur au mois de publication appartient à l'année précédente
    d = datetime.datetime.fromisoformat(cree[:10])
    return (d.year - 1 if mois > d.month else d.year), mois


def secondes(c):
    m = re.fullmatch(r"(\d+):(\d{2}):(\d{2})", c.strip())
    if m:
        return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
    if c.strip() in ("", "-"):
        return 0
    sys.exit("Valeur inattendue dans un relevé Arcom : %r" % c)


def lire_mois(octets):
    lignes = list(csv.reader(io.StringIO(octets.decode("utf-8-sig")), delimiter=";"))
    if len(lignes) < 4 or lignes[0][1] != "Appartenance" or lignes[1][0] != "Type de service" or lignes[2][0] != "Type d'émission":
        sys.exit("Format du fichier Arcom inattendu (en-têtes)")
    res = {}  # nom -> [secondes hors gouvernement, secondes en tant que membre du gouvernement]
    for l in lignes[3:]:
        if len(l) < 3 or not l[0].strip():
            continue
        t = res.setdefault(cle_nom(l[0]), [0, 0])
        t[1 if est_gouvernement(l[1]) else 0] += sum(secondes(c) for c in l[2:])
    return res


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else "data/temps_parole.json"
    cands = json.load(open("data/candidats.json", encoding="utf-8"))["candidats"]
    ds = json.loads(telecharger(API))
    fichiers = {}
    for r in ds["resources"]:
        k = mois_du_fichier(r["title"], r.get("created_at") or r.get("last_modified") or "")
        if k and (r.get("format") or "").lower() == "csv":
            fichiers[k] = r["url"]
    if not fichiers:
        sys.exit("Aucun fichier mensuel trouvé dans le jeu de données Arcom")
    retenus = sorted(fichiers)[-NB_MOIS:]
    mois_data = {k: lire_mois(telecharger(fichiers[k])) for k in retenus}
    par_candidat = {}
    for c in cands:
        nom = cle_nom("%s %s" % (c["nom"], c["prenom"]))
        vus = [mois_data[k][nom] for k in retenus if nom in mois_data[k]]
        par_candidat[c["cle"]] = (
            {"secondes": sum(v[0] for v in vus), "secondes_gouvernement": sum(v[1] for v in vus),
             "mois_avec_releve": len(vus)} if vus else None)
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_titre": "Arcom, relevés des temps de parole (open data)",
        "source_url": PAGE,
        "debut": "%d-%02d" % retenus[0], "fin": "%d-%02d" % retenus[-1], "nb_mois": len(retenus),
        "par_candidat": par_candidat,
    }
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Période %s → %s (%d mois)" % (out["debut"], out["fin"], len(retenus)))
    for c in cands:
        v = par_candidat[c["cle"]]
        print("  %-15s %s" % (c["cle"], "aucune ligne dans les relevés" if v is None else
              "%d h %02d hors gouvernement, %d h %02d comme membre du gouvernement (%d mois avec relevé)" % (
                  v["secondes"] // 3600, v["secondes"] % 3600 // 60,
                  v["secondes_gouvernement"] // 3600, v["secondes_gouvernement"] % 3600 // 60, v["mois_avec_releve"])))


if __name__ == "__main__":
    main()
