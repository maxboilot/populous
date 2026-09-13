#!/usr/bin/env python3
"""Construit data/refs_jour.json : la référence du jour affichée sur
l'accueil (bouton "La Ref du jour"), pour le jour du calendrier en cours
(mois-jour, indépendant de l'année).

Deux sources, jamais mélangées avec une thèse inventée — voir CLAUDE.md :

1. data/refs_jour_evenements.json — une liste écrite et vérifiée à la
   main (grands événements politiques, naissances et morts de
   personnalités), chaque date confirmée individuellement avant d'être
   ajoutée. Ce fichier n'est jamais généré automatiquement ; seul un humain
   l'édite.

2. data/historique.json — les lois réellement adoptées par l'Assemblée
   nationale, déjà construites par construire_historique.py. Pour un jour
   du calendrier qui n'a aucune entrée vérifiée dans le fichier ci-dessus,
   on complète honnêtement avec un texte réellement voté ce jour-là (titre,
   date, résultat du vote : rien n'est résumé ni interprété). Quand
   plusieurs textes tombent le même jour, on préfère celui voté en
   solennel, plus identifiable.

Le résultat ne couvre donc pas les 365 jours de l'année — seuls les jours
qui ont un fait vérifié en ont un. Les autres, l'application le dit
honnêtement (voir renderRefJour() dans index.html) plutôt que d'inventer
une référence.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path('data')
EVENEMENTS = DATA_DIR / 'refs_jour_evenements.json'
HISTORIQUE = DATA_DIR / 'historique.json'
SORTIE = DATA_DIR / 'refs_jour.json'


def cle_jour(date_iso):
    return date_iso[5:10]  # "AAAA-MM-JJ" -> "MM-JJ"


def construire_entree_texte(loi):
    tally = loi.get('tally') or {}
    pour, contre = tally.get('pour'), tally.get('contre')
    resultat = f", par {pour} voix contre {contre}" if pour is not None and contre is not None else ""
    return {
        'annee': int(loi['date'][:4]),
        'categorie': 'texte',
        'titre': loi['titre'],
        'texte': f"Ce jour-là, l'Assemblée nationale a adopté {loi.get('nature', 'ce texte')} « {loi['titre']} »{resultat}.",
        'source': loi.get('source'),
    }


def main():
    if not EVENEMENTS.exists():
        print('refs_jour_evenements.json absent, rien à faire.')
        return
    curated = json.loads(EVENEMENTS.read_text(encoding='utf-8'))
    refs = {k: list(v) for k, v in curated.get('refs', {}).items()}
    jours_couverts = set(refs.keys())

    if HISTORIQUE.exists():
        historique = json.loads(HISTORIQUE.read_text(encoding='utf-8'))
        par_jour = defaultdict(list)
        for loi in historique.get('lois', []):
            if loi.get('date'):
                par_jour[cle_jour(loi['date'])].append(loi)

        ajoutes = 0
        for jour, lois in par_jour.items():
            if jour in jours_couverts:
                continue  # un fait déjà vérifié à la main prime sur un ajout automatique
            # Le vote solennel est le plus identifiable ; à égalité, le plus récent.
            choisi = sorted(lois, key=lambda l: (not l.get('solennel'), l['date']), reverse=False)[0]
            refs[jour] = [construire_entree_texte(choisi)]
            ajoutes += 1
        print(f'{ajoutes} jour(s) complété(s) avec un texte réellement voté ce jour-là.')
    else:
        print('historique.json absent : pas de complément automatique.')

    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source_note': curated.get('source_note', ''),
        'refs': dict(sorted(refs.items())),
    }
    SORTIE.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'refs_jour.json : {len(refs)} jours couverts sur 366.')


if __name__ == '__main__':
    main()
