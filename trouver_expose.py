#!/usr/bin/env python3
"""Aide a la redaction du 2e visuel d'un post « Vote d'hier » : retrouve le
texte de loi d'un scrutin et affiche les paragraphes de son EXPOSE DES
MOTIFS (le texte des auteurs de la loi), numerotes, pour qu'un humain en
choisisse un extrait mot pour mot (--resume de publier_reseaux.py).

Ce script ne produit rien de publiable : jamais de resume ecrit par nous
(cf. CLAUDE.md). Usage : python3 trouver_expose.py 8436
"""
import json
import re
import sys
import zipfile
from io import BytesIO

import construire_expose_motifs as cem
import structure_scrutins as S
import reseau

LECTURE = re.compile(r'\s*\((?:première|nouvelle|deuxième|seconde|lecture|texte)[^)]*\)', re.I)


def intitule_loi(titre_officiel):
    m = re.search(r'(?:proposition|projet) de loi\s+(.+)$', titre_officiel, flags=re.I)
    return LECTURE.sub('', m.group(1)).strip().rstrip('. ') if m else None


norm = S.intitule_normalise


def main(numero):
    vote = json.load(open(f'data/scrutins/{numero}.json', encoding='utf-8'))
    intitule = intitule_loi(vote['titre'])
    if not intitule:
        sys.exit(f"Impossible d'isoler l'intitule de la loi dans : {vote['titre']}")
    cible = norm(intitule)
    archive = reseau.telecharger(cem.URL_DOSSIERS, timeout=cem.DELAI, headers={'User-Agent': cem.UA})
    trouves = []
    with zipfile.ZipFile(BytesIO(archive)) as z:
        for nom in z.namelist():
            if '/dossierParlementaire/' not in nom or not nom.endswith('.json'):
                continue
            dp = json.loads(z.read(nom)).get('dossierParlementaire', {})
            titre = ((dp.get('titreDossier') or {}).get('titre')) or ''
            if len(norm(titre)) > 20 and (cible == norm(titre) or cible in norm(titre) or norm(titre) in cible):
                actes = (dp.get('actesLegislatifs') or {}).get('acteLegislatif')
                nums, depot = set(), []
                cem._walk_dossier(actes, nums, depot)
                if depot:
                    trouves.append((titre, depot[0]))
    if not trouves:
        sys.exit(f"Aucun dossier trouve pour « {intitule} ».")
    for titre, ref in trouves:
        print(f'\n=== {titre}\n    texte depose : {ref}  ({cem.URL_TEXTE.format(ref=ref)})')
        h = reseau.telecharger(cem.URL_TEXTE.format(ref=ref), timeout=cem.DELAI, headers={'User-Agent': cem.UA}).decode('utf-8')
        txt = re.sub(r'<style.*?</style>|<script.*?</script>', '', h, flags=re.S)
        txt = re.sub(r'</(p|h\d|li|div)>', '\n', txt)
        txt = re.sub(r'<[^>]+>', '', txt)
        import html
        lignes = [re.sub(r'\s+', ' ', l).strip() for l in html.unescape(txt).replace('\xa0', ' ').split('\n')]
        lignes = [l for l in lignes if l]
        debut = next((i for i, l in enumerate(lignes) if l.upper().replace('É', 'E').startswith('EXPOSE DES MOTIFS')), None)
        if debut is None:
            print('    (pas d\'expose des motifs trouve)')
            continue
        fin = next((i for i, l in enumerate(lignes[debut + 1:], debut + 1) if re.match(r'^(PROPOSITION DE LOI|PROJET DE LOI|Article (1er|premier|\d))', l, re.I)), len(lignes))
        for n, l in enumerate((l for l in lignes[debut + 1:fin] if len(l) > 40), 1):
            print(f'[{n}] {l}\n')


if __name__ == '__main__':
    main(int(sys.argv[1]))
