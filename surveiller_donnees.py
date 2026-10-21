#!/usr/bin/env python3
# Filet de securite sur les donnees : detecte les pipelines qui ne tournent
# plus et les scrutins publies par l'Assemblee mais pas encore ingeres.
#
# Pourquoi ce script existe : GitHub peut retarder voire sauter une execution
# planifiee (constate le 9 septembre 2026), et l'open data de l'Assemblee
# publie ses scrutins avec du retard sur son propre site (scrutin 8705, 12
# octobre 2026). Dans les deux cas l'app continue d'afficher des donnees
# anciennes sans qu'aucun message d'erreur ne s'affiche nulle part.
#
# Deux familles de controles :
#   1. Pipelines : le dernier run REUSSI de chaque workflow de donnees date-t-il
#      de moins que sa limite ? Le dernier run a-t-il echoue ? On regarde les
#      runs, pas les fichiers de donnees : verif_changement_utile.py evite de
#      committer quand rien n'a change, donc un fichier ancien ne prouve rien.
#   2. Retard de l'open data : le site de l'Assemblee a-t-il des scrutins
#      au-dela de data/state.json ? S'il en a ET que state.json n'a pas bouge
#      depuis plus de RETARD_SCRUTINS_HEURES, on alerte.
#
# Livraison de l'alerte : une issue GitHub "[Alerte donnees]" (GitHub envoie
# un e-mail au proprietaire du depot). Une seule issue ouverte a la fois :
# mise a jour si la liste des problemes change, fermee quand tout va bien.
#
# Usage :
#   python3 surveiller_donnees.py --dry-run   # affiche le bilan, n'ecrit rien
#   GITHUB_TOKEN=... GITHUB_REPOSITORY=... python3 surveiller_donnees.py
import argparse
import datetime as dt
import json
import os
import re
import sys

import requests

DEPOT = os.environ.get("GITHUB_REPOSITORY", "maxboilot/populous")
API = "https://api.github.com"
USER_AGENT = "Populous-surveillance-donnees (https://github.com/maxboilot/populous)"
TITRE_ISSUE = "[Alerte données] Les données de l'app ne sont plus à jour"
LABEL = "alerte-donnees"

# Workflow -> (libelle, heures maximum depuis le dernier run reussi).
# Limites calees sur les ecarts REELS entre runs planifies reussis, mesures
# le 21 octobre 2026 sur les 60 derniers runs de chaque workflow : GitHub
# espace beaucoup plus les crons que ce que le fichier demande (le cron
# "toutes les heures" de l'actu tourne en pratique toutes les 5 h environ ;
# premiere version de ce script : fausse alerte avec une limite de 4 h).
#   workflow           ecart median / pire ecart observe
#   ingest_scrutins    2,6 h / 6,5 h
#   actu_presidentielle 4,9 h / 10,6 h
#   sondages           4,0 h / 92,8 h (un trou de presque 4 jours a deja eu lieu)
#   refs_jour          24,0 h / 24,9 h
#   temps_parole       hebdomadaire (lundi)
#   villes             mensuel (le 2) : limite de 45 jours
#   votes_conseils     hebdomadaire (mercredi) : limite de 14 jours
PIPELINES = {
    "ingest_scrutins.yml": ("Ingestion des scrutins", 10),
    "actu_presidentielle.yml": ("Actualité présidentielle", 16),
    "sondages.yml": ("Sondages", 48),
    "refs_jour.yml": ("Référence du jour", 36),
    "temps_parole.yml": ("Temps de parole (hebdomadaire)", 204),   # 8,5 jours
    "villes.yml": ("Données des villes (mensuel)", 1080),           # 45 jours : mensuel + marge
    "votes_conseils.yml": ("Votes des conseils (hebdomadaire)", 336), # 14 jours
}

# Nombre d'heures sans nouveau scrutin ingere, alors que le site de
# l'Assemblee en publie, avant d'alerter. En dessous, c'est le delai normal de
# l'open data.
RETARD_SCRUTINS_HEURES = 30
SONDE_MAX = 80  # nombre de numeros a sonder au-dela du dernier connu


def entetes():
    h = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    jeton = os.environ.get("GITHUB_TOKEN")
    if jeton:
        h["Authorization"] = f"Bearer {jeton}"
    return h


def api(chemin, **params):
    r = requests.get(f"{API}{chemin}", headers=entetes(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_date(texte):
    return dt.datetime.fromisoformat(texte.replace("Z", "+00:00"))


def heures_depuis(date):
    return (dt.datetime.now(dt.timezone.utc) - date).total_seconds() / 3600


def controler_pipelines():
    """Renvoie une liste de problemes (texte) pour les workflows de donnees."""
    problemes = []
    for fichier, (libelle, limite) in PIPELINES.items():
        try:
            reussis = api(
                f"/repos/{DEPOT}/actions/workflows/{fichier}/runs",
                status="success", branch="main", per_page=1,
            ).get("workflow_runs", [])
            recents = api(
                f"/repos/{DEPOT}/actions/workflows/{fichier}/runs",
                status="completed", branch="main", per_page=1,
            ).get("workflow_runs", [])
        except requests.RequestException as e:
            # Ne pas alerter pour une panne de l'API GitHub elle-meme.
            print(f"[info] {fichier} : API GitHub indisponible ({e})", file=sys.stderr)
            continue
        if not reussis:
            problemes.append(f"**{libelle}** : aucun run réussi retrouvé (`{fichier}`).")
            continue
        age = heures_depuis(parse_date(reussis[0]["created_at"]))
        if age > limite:
            problemes.append(
                f"**{libelle}** : dernier run réussi il y a {age:.0f} h "
                f"(limite {limite} h) — [`{fichier}`]"
                f"(https://github.com/{DEPOT}/actions/workflows/{fichier})."
            )
        if recents and recents[0]["conclusion"] == "failure":
            problemes.append(
                f"**{libelle}** : le dernier run a échoué — "
                f"[voir le run]({recents[0]['html_url']})."
            )
    return problemes


def dernier_numero_connu():
    with open("data/state.json", encoding="utf-8") as f:
        return int(json.load(f)["last_numero"])


def scrutin_existe_sur_le_site(numero):
    """Vrai si la page du scrutin existe. Une page inconnue renvoie quand meme
    HTTP 200 (coquille generique), donc on lit le <title>."""
    r = requests.get(
        f"https://www.assemblee-nationale.fr/dyn/17/scrutins/{numero}",
        headers={"User-Agent": "Mozilla/5.0 (Populous freshness check)"}, timeout=30,
    )
    m = re.search(r"<title>([^<]*)", r.text)
    return bool(m) and f"Analyse du scrutin n°{numero}" in m.group(1)


def controler_retard_open_data():
    """Renvoie (problemes, infos). Un retard n'est un probleme que s'il dure."""
    problemes, infos = [], []
    dernier = dernier_numero_connu()
    try:
        trouve = dernier
        for n in range(dernier + 1, dernier + 1 + SONDE_MAX):
            if not scrutin_existe_sur_le_site(n):
                break
            trouve = n
    except requests.RequestException as e:
        infos.append(f"Site de l'Assemblée injoignable pour le contrôle de retard ({e}).")
        return problemes, infos
    ecart = trouve - dernier
    if ecart == 0:
        return problemes, infos
    try:
        commits = api(f"/repos/{DEPOT}/commits", path="data/state.json", per_page=1)
        derniere = parse_date(commits[0]["commit"]["committer"]["date"])
        age = heures_depuis(derniere)
    except (requests.RequestException, IndexError, KeyError) as e:
        infos.append(f"Âge de data/state.json indéterminé ({e}).")
        return problemes, infos
    texte = (
        f"{ecart} scrutin(s) publié(s) sur assemblee-nationale.fr "
        f"(jusqu'au n°{trouve}) mais pas encore dans l'open data : l'app est à "
        f"jour jusqu'au n°{dernier}, dernière ingestion il y a {age:.0f} h."
    )
    if age > RETARD_SCRUTINS_HEURES:
        problemes.append(
            f"**Retard de l'open data** : {texte} "
            f"(seuil {RETARD_SCRUTINS_HEURES} h). Le site de l'Assemblée a de l'avance "
            "sur ses données ouvertes ; vérifier si `Scrutins.json.zip` est à jour "
            "avant de supposer une panne de notre côté."
        )
    else:
        infos.append(f"Retard normal de l'open data : {texte}")
    return problemes, infos


def issue_ouverte():
    """L'issue d'alerte actuellement ouverte, ou None."""
    for issue in api(f"/repos/{DEPOT}/issues", state="open", labels=LABEL, per_page=10):
        if "pull_request" not in issue:
            return issue
    return None


def assurer_label():
    r = requests.post(
        f"{API}/repos/{DEPOT}/labels", headers=entetes(), timeout=30,
        json={"name": LABEL, "color": "d93f0b", "description": "Données de l'app périmées ou en retard"},
    )
    if r.status_code not in (201, 422):  # 422 : existe deja
        r.raise_for_status()


def corps(problemes):
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lignes = "\n".join(f"- {p}" for p in problemes)
    # La mention @ garantit l'e-mail meme si le proprietaire ne "surveille"
    # pas le depot : une issue ouverte par un bot ne notifie sinon que les
    # abonnes du depot.
    return (
        f"@{DEPOT.split('/')[0]} Contrôle du {maintenant} :\n\n{lignes}\n\n"
        "_Cette issue se ferme toute seule quand tout est revenu à la normale. "
        "Générée par `surveiller_donnees.py` (workflow « Surveillance des données »)._"
    )


def publier(problemes):
    """Ouvre, met a jour ou ferme l'issue d'alerte selon le bilan."""
    existante = issue_ouverte()
    if problemes:
        texte = corps(problemes)
        if existante is None:
            assurer_label()
            r = requests.post(
                f"{API}/repos/{DEPOT}/issues", headers=entetes(), timeout=30,
                json={"title": TITRE_ISSUE, "body": texte, "labels": [LABEL]},
            )
            r.raise_for_status()
            print(f"Issue ouverte : {r.json()['html_url']}")
        else:
            # On ne remet a jour que si la liste des problemes a change, pour
            # ne pas inonder la boite mail a chaque contrôle.
            def noyau(t):
                # Les durees ("il y a 9 h", "12 h") changent a chaque
                # controle : on les neutralise pour ne comparer que QUELS
                # problemes existent, pas depuis combien d'heures.
                t = re.sub(r"^@\S+ Contrôle du [^\n]*\n", "", t).split("_Cette issue")[0]
                return re.sub(r"\d+", "#", t).strip()
            if noyau(existante["body"] or "") != noyau(texte):
                r = requests.patch(
                    f"{API}/repos/{DEPOT}/issues/{existante['number']}",
                    headers=entetes(), timeout=30, json={"body": texte},
                )
                r.raise_for_status()
                requests.post(
                    f"{API}/repos/{DEPOT}/issues/{existante['number']}/comments",
                    headers=entetes(), timeout=30,
                    json={"body": f"@{DEPOT.split('/')[0]} Le bilan a changé :\n\n"
                                  + "\n".join(f"- {p}" for p in problemes)},
                ).raise_for_status()
                print(f"Issue #{existante['number']} mise à jour.")
            else:
                print(f"Issue #{existante['number']} déjà à jour, rien à envoyer.")
    elif existante is not None:
        n = existante["number"]
        requests.post(
            f"{API}/repos/{DEPOT}/issues/{n}/comments", headers=entetes(), timeout=30,
            json={"body": f"@{DEPOT.split('/')[0]} Tout est revenu à la normale : issue fermée automatiquement."},
        ).raise_for_status()
        requests.patch(
            f"{API}/repos/{DEPOT}/issues/{n}", headers=entetes(), timeout=30,
            json={"state": "closed", "state_reason": "completed"},
        ).raise_for_status()
        print(f"Issue #{n} fermée : tout est normal.")
    else:
        print("Tout est normal, aucune issue ouverte.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="affiche le bilan sans toucher aux issues")
    args = parser.parse_args()

    problemes = controler_pipelines()
    retard, infos = controler_retard_open_data()
    problemes += retard

    print("=== Bilan ===")
    for p in problemes:
        print("PROBLEME :", p)
    for i in infos:
        print("INFO :", i)
    if not problemes:
        print("Aucun problème détecté.")

    if args.dry_run:
        return 0
    if not os.environ.get("GITHUB_TOKEN"):
        print("GITHUB_TOKEN absent : impossible de publier l'alerte.", file=sys.stderr)
        return 1
    publier(problemes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
