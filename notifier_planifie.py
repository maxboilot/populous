#!/usr/bin/env python3
"""Notifications push planifiees (en plus de celle, evenementielle, du
nouveau scrutin — cf. ingest_scrutins.yml). Calcule le titre/texte a
partir des donnees deja curatees du depot, puis delegue l'envoi a
notifier_push.py (APNs). Ne fait rien, sans erreur, quand il n'y a rien
a annoncer ce jour-la.

Types (--type) :
  fait     : le fait du jour (data/refs_jour.json), quotidien.
  semaine  : les prochains points a l'ordre du jour de l'Assemblee
             (data/agenda.json), le lundi.
  solennel : la veille d'un vote solennel (agenda.json, scrutin_annonce).

Usage :
    python notifier_planifie.py --type fait [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

DOSSIER = Path(__file__).parent
MAX_TEXTE = 150  # au-dela, iOS coupe de toute facon l'apercu


def _court(texte, limite=MAX_TEXTE):
    texte = ' '.join(texte.split())
    if len(texte) <= limite:
        return texte
    return texte[:limite].rsplit(' ', 1)[0].rstrip('.,;:— ') + '…'


def _lire(nom):
    return json.loads((DOSSIER / 'data' / nom).read_text(encoding='utf-8'))


def _sujet(item):
    return item['ordre_du_jour'].split('—', 1)[-1].strip()


def notif_fait():
    refs = _lire('refs_jour.json')['refs'].get(datetime.date.today().strftime('%m-%d')) or []
    if not refs:
        return None
    ref = refs[0]
    corps = f"{ref['annee']} : {ref['titre']}" if ref.get('titre') else f"{ref['annee']} : {ref['texte']}"
    return "Découvre le fait du jour", _court(corps)


def notif_semaine():
    aujourdhui = datetime.date.today()
    limite = (aujourdhui + datetime.timedelta(days=7)).isoformat()
    items = sorted(
        (a for a in _lire('agenda.json') if aujourdhui.isoformat() <= a['date'] <= limite),
        key=lambda a: (a['date'], a['heure']),
    )
    if not items:
        return None
    n = len(items)
    debut = f"{n} point{'s' if n > 1 else ''} à l'ordre du jour, dont : "
    return "Cette semaine à l'Assemblée", _court(debut + _sujet(items[0]))


def notif_solennel():
    demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    items = [a for a in _lire('agenda.json') if a['date'] == demain and a.get('scrutin_annonce')]
    if not items:
        return None
    return "Vote solennel demain", _court(_sujet(items[0]))


TYPES = {'fait': notif_fait, 'semaine': notif_semaine, 'solennel': notif_solennel}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--type', required=True, choices=sorted(TYPES))
    p.add_argument('--dry-run', action='store_true', help="Affiche la notification sans l'envoyer.")
    args = p.parse_args()

    contenu = TYPES[args.type]()
    if not contenu:
        print(f"Rien a notifier pour --type {args.type} aujourd'hui.")
        return
    titre, texte = contenu
    print(f'{titre} | {texte}')
    if args.dry_run:
        return
    sys.exit(subprocess.run(['python3', str(DOSSIER / 'notifier_push.py'), '--titre', titre, '--texte', texte]).returncode)


if __name__ == '__main__':
    main()
