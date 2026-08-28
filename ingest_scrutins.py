#!/usr/bin/env python3
"""
ingest_scrutins.py — pipeline quotidien de la « Carte de l'attention »
========================================================================

CE QUE FAIT CE SCRIPT :
1. Télécharge l'archive JSON officielle des scrutins (Licence Ouverte,
   data.assemblee-nationale.fr) et ne retient que les scrutins nouveaux
   depuis la dernière exécution (état conservé dans state.json).
2. Repère le ou les votes solennels du jour, s'il y en a.
3. Reconstruit, pour chaque scrutin retenu, la position de chaque
   circonscription (pour / contre / abstention / absent) en la
   joignant au fichier des 577 élus via le PA-id officiel.
4. Télécharge et parse l'agenda de la séance publique (feuille verte).
5. Écrit des fichiers JSON compacts, prêts à être servis à l'app :
     data/scrutins/<numero>.json   — un scrutin, détaillé
     data/today.json               — pointeur vers le scrutin vedette du jour
     data/agenda.json              — les 4 prochaines semaines de séance

CE QUE CE SCRIPT NE FAIT PAS :
- Il ne transforme pas un vote en dix thèses de quiz : cette étape
  reste éditoriale et doit être relue par une personne avant publication.
- Il ne s'exécute pas dans une conversation Claude. Il est fait pour
  tourner sur ton propre serveur, via cron ou une tâche planifiée
  (exemple de workflow GitHub Actions fourni à côté de ce fichier).

PRÉREQUIS :
    pip install requests

CONFIGURATION : voir le bloc CONFIG ci-dessous.

⚠ Ce script n'a pas pu être exécuté ni testé contre le site réel de
l'Assemblée depuis cet environnement (accès réseau restreint côté
Claude). Le schéma JSON est vérifié — il reproduit fidèlement les
champs documentés et confirmés sur un scrutin réel (n°4595, XVIIe
législature) — mais teste une première exécution manuelle avant de
l'automatiser, et surveille les logs les premiers jours.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

# ============================================================
# CONFIG — à adapter à ton hébergement
# ============================================================
LEGISLATURE = 17
BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
SCRUTINS_ZIP_URL = f"{BASE}/{LEGISLATURE}/loi/scrutins/Scrutins.json.zip"
AGENDA_CSV_URL = (
    "http://data.assemblee-nationale.fr/static/openData/repository/"
    f"{LEGISLATURE}/vp/seances/seances_publique_excel.csv"
)

DATA_DIR = Path("data")
SCRUTINS_DIR = DATA_DIR / "scrutins"
STATE_FILE = DATA_DIR / "state.json"
ELUS_FILE = Path("elus.json")  # le fichier des 577 élus, avec le champ "u" (PA-id)

USER_AGENT = "CarteDeLAttention/0.1 (contact: TON_EMAIL@exemple.fr)"
TIMEOUT = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("ingest")


# ============================================================
# Étape 0 — état (pour ne traiter que les scrutins nouveaux)
# ============================================================
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen_uids": [], "last_numero": 0}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# Étape 1 — roster des élus (pour joindre acteurRef → circonscription)
# ============================================================
def load_roster() -> dict[str, dict]:
    """PA-id → { k: clé de circonscription "DEP|CIRCO", n: nom, g: groupe }"""
    if not ELUS_FILE.exists():
        raise SystemExit(
            f"{ELUS_FILE} introuvable. Ce fichier doit contenir le champ "
            "\"u\" (PA-id officiel) pour chaque élu — voir la note de mise à jour."
        )
    data = json.loads(ELUS_FILE.read_text(encoding="utf-8"))
    roster = {}
    for e in data["elus"]:
        if "u" not in e:
            continue
        roster[e["u"]] = {"k": e["k"], "n": e["n"], "g": e["g"], "dep": e["dep"], "ci": e["ci"]}
    log.info("roster chargé : %d élus avec PA-id", len(roster))
    return roster


# ============================================================
# Étape 2 — téléchargement + parsing de l'archive des scrutins
# ============================================================
def fetch_scrutins_zip() -> zipfile.ZipFile:
    log.info("téléchargement de %s", SCRUTINS_ZIP_URL)
    resp = requests.get(
        SCRUTINS_ZIP_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    log.info("archive reçue : %.1f Mo", len(resp.content) / 1_000_000)
    return zipfile.ZipFile(io.BytesIO(resp.content))


def as_list(x):
    """Le XML→JSON de l'AN encode 0/1/N éléments différemment : normalise en liste."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


@dataclass
class Scrutin:
    uid: str
    numero: int
    date: str
    titre: str
    objet: str
    type_libelle: str
    sort_libelle: str
    nb_pour: int
    nb_contre: int
    nb_abstentions: int
    nb_non_votants: int
    positions: dict[str, str] = field(default_factory=dict)  # PA-id -> pour/contre/abstention

    @property
    def is_solennel(self) -> bool:
        return "solennel" in (self.type_libelle or "").lower()

    @property
    def adopte(self) -> bool:
        return "adopt" in (self.sort_libelle or "").lower()


def parse_scrutin(raw: dict) -> Scrutin | None:
    s = raw.get("scrutin") or {}
    uid = s.get("uid")
    numero = s.get("numero")
    if not uid or not numero:
        return None

    type_vote = s.get("typeVote") or {}
    sort_ = s.get("sort") or {}
    objet = s.get("objet") or {}
    syn = s.get("syntheseVote") or {}
    decompte = syn.get("decompte") or {}

    sc = Scrutin(
        uid=uid,
        numero=int(numero),
        date=s.get("dateScrutin") or "",
        titre=s.get("titre") or "",
        objet=(objet.get("libelle") if isinstance(objet, dict) else None) or s.get("titre") or "",
        type_libelle=type_vote.get("libelleTypeVote") or "",
        sort_libelle=sort_.get("libelle") or "",
        nb_pour=int(decompte.get("pour") or 0),
        nb_contre=int(decompte.get("contre") or 0),
        nb_abstentions=int(decompte.get("abstentions") or 0),
        nb_non_votants=int(decompte.get("nonVotants") or 0),
    )

    # ventilationVotes.organe[].groupes.groupe[].vote.decompteNominatif.{pours,contres,...}.votant[]
    for organe in as_list((s.get("ventilationVotes") or {}).get("organe")):
        for grp in as_list((organe.get("groupes") or {}).get("groupe")):
            vote = grp.get("vote") or {}
            decompte_nom = vote.get("decompteNominatif") or {}
            for key, position in (
                ("pours", "pour"),
                ("contres", "contre"),
                ("abstentions", "abstention"),
                ("nonVotants", "non_votant"),
            ):
                bloc = decompte_nom.get(key)
                if not bloc:
                    continue
                for votant in as_list(bloc.get("votant")):
                    if not isinstance(votant, dict):
                        continue
                    pa_id = votant.get("acteurRef")
                    if pa_id:
                        sc.positions[pa_id] = position

    return sc


def iter_new_scrutins(zf: zipfile.ZipFile, seen_uids: set[str]):
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        try:
            raw = json.loads(zf.read(name))
        except json.JSONDecodeError:
            log.warning("JSON illisible : %s", name)
            continue
        sc = parse_scrutin(raw)
        if sc is None or sc.uid in seen_uids:
            continue
        yield sc


# ============================================================
# Étape 3 — écriture des fichiers consommés par l'app
# ============================================================
def position_for_circo(sc: Scrutin, roster: dict[str, dict]) -> dict[str, str]:
    """clé de circonscription "DEP|CIRCO" -> position. Absent de partout = absent."""
    out: dict[str, str] = {}
    for pa_id, elu in roster.items():
        pos = sc.positions.get(pa_id)
        out[elu["k"]] = pos if pos else "absent"
    return out


def write_scrutin(sc: Scrutin, roster: dict[str, dict]) -> Path:
    SCRUTINS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "uid": sc.uid,
        "numero": sc.numero,
        "date": sc.date,
        "titre": sc.titre,
        "objet": sc.objet,
        "type": sc.type_libelle,
        "solennel": sc.is_solennel,
        "sort": sc.sort_libelle,
        "adopte": sc.adopte,
        "tally": {
            "pour": sc.nb_pour,
            "contre": sc.nb_contre,
            "abstention": sc.nb_abstentions,
            "absent": sc.nb_non_votants,
        },
        "par_circonscription": position_for_circo(sc, roster),
        "source": f"https://www.assemblee-nationale.fr/dyn/{LEGISLATURE}/scrutins/{sc.numero}",
    }
    path = SCRUTINS_DIR / f"{sc.numero}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def backfill_last_featured(state: dict) -> None:
    # Amorce la mémoire longue tant qu'elle est vide.
    #
    # write_today_pointer ne mémorise le dernier vote vedette que les jours
    # où un nouveau scrutin arrive. Le correctif ayant été déployé pendant la
    # trêve estivale, ce cas ne s'est jamais présenté : rien n'a été mémorisé
    # et la carte vedette de l'accueil est restée vide. On repart donc de
    # l'archive déjà présente sur disque plutôt que d'attendre la rentrée.
    if state.get('last_featured_numero') is not None:
        return
    numeros = []
    for chemin in SCRUTINS_DIR.glob('*.json'):
        try:
            numeros.append(int(chemin.stem))
        except ValueError:
            continue
    if not numeros:
        return
    dernier = max(numeros)
    fiche = json.loads((SCRUTINS_DIR / f'{dernier}.json').read_text(encoding='utf-8'))
    state['last_featured_numero'] = fiche.get('numero', dernier)
    state['last_featured_date'] = fiche.get('date')
    state['last_featured_titre'] = fiche.get('titre')


def write_today_pointer(featured: Scrutin | None, all_new: list[Scrutin], state: dict) -> None:
    """
    Le scrutin vedette du jour : priorité au vote solennel le plus récent.
    S'il n'y en a pas, on pointe vers le scrutin le plus suivi (le plus de
    votants), sans jamais cacher les autres — ils restent listés à côté.

    On garde aussi, en mémoire longue (dans state.json), le dernier scrutin
    vedette connu — pour qu'un jour sans séance (recess, week-end) affiche
    encore le dernier vote réel plutôt qu'un écran vide.
    """
    if featured is not None:
        state["last_featured_numero"] = featured.numero
        state["last_featured_date"] = featured.date
        state["last_featured_titre"] = featured.titre
    else:
        backfill_last_featured(state)

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "featured_numero": featured.numero if featured else None,
        "featured_is_solennel": featured.is_solennel if featured else False,
        "autres_scrutins_du_jour": [
            sc.numero for sc in all_new if not featured or sc.numero != featured.numero
        ],
        "aucun_vote_aujourdhui": featured is None and not all_new,
        "last_featured_numero": state.get("last_featured_numero"),
        "last_featured_date": state.get("last_featured_date"),
    }
    (DATA_DIR / "today.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def pick_featured(new_scrutins: list[Scrutin]) -> Scrutin | None:
    if not new_scrutins:
        return None
    solennels = [sc for sc in new_scrutins if sc.is_solennel]
    if solennels:
        return max(solennels, key=lambda sc: sc.numero)
    # à défaut, le plus suivi : proxy simple de "combien ce vote a compté"
    return max(new_scrutins, key=lambda sc: sc.nb_pour + sc.nb_contre + sc.nb_abstentions)


# ============================================================
# Étape 4 — agenda (feuille verte)
# ============================================================
def fetch_agenda() -> list[dict]:
    log.info("téléchargement de l'agenda : %s", AGENDA_CSV_URL)
    resp = requests.get(AGENDA_CSV_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()

    # Le fichier n'est pas en UTF-8 (accents mal encodés observés en UTF-8) —
    # on essaie plusieurs encodages plutôt que de planter dessus.
    text = None
    for enc in ("utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            candidate = resp.content.decode(enc)
            if "�" not in candidate:
                text = candidate
                break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = resp.content.decode("iso-8859-1", errors="replace")
        log.warning("agenda : encodage incertain, décodage en mode dégradé")

    rows = []
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    for row in reader:
        rows.append({
            "date": row.get("Date", "").strip(),
            "heure": row.get("Heure", "").strip(),
            "ordre_du_jour": (row.get("Ordre(s) du jour") or "").strip(),
        })
    log.info("agenda : %d séances", len(rows))
    return rows


def write_agenda(rows: list[dict]) -> None:
    (DATA_DIR / "agenda.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ============================================================
# Orchestration
# ============================================================
def main() -> int:
    state = load_state()
    seen: set[str] = set(state.get("seen_uids", []))
    roster = load_roster()

    try:
        zf = fetch_scrutins_zip()
    except requests.RequestException as e:
        log.error("échec du téléchargement des scrutins : %s", e)
        return 1

    new_scrutins = sorted(iter_new_scrutins(zf, seen), key=lambda sc: sc.numero)
    log.info("scrutins nouveaux depuis la dernière exécution : %d", len(new_scrutins))

    for sc in new_scrutins:
        path = write_scrutin(sc, roster)
        log.info(
            "  n°%s%s — %s — %s",
            sc.numero, " [SOLENNEL]" if sc.is_solennel else "",
            sc.sort_libelle, path.name,
        )

    featured = pick_featured(new_scrutins)
    write_today_pointer(featured, new_scrutins, state)

    try:
        agenda = fetch_agenda()
        write_agenda(agenda)
    except requests.RequestException as e:
        log.error("échec du téléchargement de l'agenda (non bloquant) : %s", e)

    seen.update(sc.uid for sc in new_scrutins)
    state["seen_uids"] = sorted(seen)
    if new_scrutins:
        state["last_numero"] = max(state.get("last_numero", 0), new_scrutins[-1].numero)
    save_state(state)

    log.info("terminé. featured=%s", featured.numero if featured else "aucun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
