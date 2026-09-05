#!/usr/bin/env python3
"""Construit data/groupes_themes.json : le bilan de vote de chaque groupe
parlementaire, thème par thème, pour l'onglet Jeu de la Présidentielle 2027.

CE QUE CE SCRIPT NE FAIT PAS, ET POURQUOI :
Il n'écrit aucune phrase sur ce qu'un parti "défend" ou "pense" d'un thème.
Une telle phrase serait une thèse générée automatiquement et attribuée à
un parti réel — précisément ce que CLAUDE.md interdit sans relecture
humaine. Ce script calcule uniquement un bilan chiffré et vérifiable :
sur les textes d'un thème donné, déjà votés et déjà classés par
categories.py, comment un groupe a-t-il réellement voté ? Chaque chiffre
est traçable jusqu'au scrutin qui l'a produit.

Source : uniquement des fichiers déjà présents en local — data/historique.json
(quels scrutins, quels thèmes) et data/scrutins/<numero>.json (le vote de
chaque circonscription), croisés à elus.json (quel groupe pour quelle
circonscription). Aucun réseau, aucune nouvelle collecte : c'est un calcul
sur des données déjà ingérées, comme le tri qu'applique déjà
construire_historique.py.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

import categories

DATA_DIR = Path('data')
SORTIE = DATA_DIR / 'groupes_themes.json'


def charger_groupes_et_circos():
    elus = json.loads(Path('elus.json').read_text(encoding='utf-8'))
    groupes = [{'s': g['s'], 'n': g['n'], 'c': g['c'], 'sg': g['sg']} for g in elus['groupes']]
    # elus.json fait cohabiter deux graphies du meme sigle de groupe cote
    # elus[] et cote groupes[] ("EcoS" vs "ECOS", "Dem" vs "DEM"), et un
    # sigle carrement different pour un meme groupe ("UDR" vs "UDDPLR").
    # Sans cette normalisation, ces groupes n'apparaissent jamais dans
    # aucun bilan - constate en verifiant la couverture par groupe.
    par_minuscule = {g['s'].lower(): g['s'] for g in groupes}
    par_minuscule.setdefault('udr', 'UDDPLR')
    circo_vers_groupe = {e['k']: par_minuscule.get(e['g'].lower(), e['g']) for e in elus['elus']}
    return groupes, circo_vers_groupe


def main():
    groupes, circo_vers_groupe = charger_groupes_et_circos()
    historique = json.loads((DATA_DIR / 'historique.json').read_text(encoding='utf-8'))
    lois = historique['lois']

    # groupe -> theme -> {pour, contre, textes: [...]}
    bilan = {g['s']: {code: {'pour': 0, 'contre': 0, 'textes': []} for code, _ in categories.THEMES}
              for g in groupes}

    manquants = 0
    for loi in lois:
        themes = loi.get('themes') or []
        if not themes:
            continue
        chemin = DATA_DIR / 'scrutins' / f"{loi['numero']}.json"
        if not chemin.exists():
            manquants += 1
            continue
        scrutin = json.loads(chemin.read_text(encoding='utf-8'))
        par_circo = scrutin.get('par_circonscription') or {}

        # Position majoritaire de chaque groupe sur CE scrutin, pour ne
        # lister le texte qu'une fois par groupe (pas 71 fois pour LFI-NFP).
        compte_par_groupe = {}
        for cle, position in par_circo.items():
            g = circo_vers_groupe.get(cle)
            if not g or position not in ('pour', 'contre'):
                continue
            c = compte_par_groupe.setdefault(g, {'pour': 0, 'contre': 0})
            c[position] += 1

        for g, c in compte_par_groupe.items():
            if g not in bilan:
                continue
            position_groupe = 'pour' if c['pour'] >= c['contre'] else 'contre'
            for theme in themes:
                if theme not in bilan[g]:
                    continue
                bilan[g][theme]['pour'] += c['pour']
                bilan[g][theme]['contre'] += c['contre']
                bilan[g][theme]['textes'].append({
                    'numero': loi['numero'], 'titre': loi['titre'], 'date': loi['date'],
                    'adopte': loi['adopte'], 'position': position_groupe,
                })

    donnees = {}
    for g in groupes:
        donnees[g['s']] = {}
        for code, _ in categories.THEMES:
            b = bilan[g['s']][code]
            exprimes = b['pour'] + b['contre']
            if exprimes == 0:
                continue
            b['textes'].sort(key=lambda t: t['date'], reverse=True)
            donnees[g['s']][code] = {
                'taux': round(b['pour'] / exprimes * 100),
                'n_textes': len(b['textes']),
                'textes': b['textes'],
            }

    sortie = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'groupes': groupes,
        'themes': [{'code': code, 'libelle': lib} for code, lib in categories.THEMES],
        'donnees': donnees,
    }
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    couverts = sum(1 for g in donnees.values() for t in g.values())
    print(f'groupes_themes.json : {len(groupes)} groupes x {len(categories.THEMES)} themes, '
          f'{couverts} cases couvertes, {manquants} scrutins sans fichier local, '
          f'{round(SORTIE.stat().st_size/1024,1)} Ko')


if __name__ == '__main__':
    raise SystemExit(main())
