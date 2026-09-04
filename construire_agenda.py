#!/usr/bin/env python3
"""Construit data/agenda.json : les textes inscrits à l'ordre du jour à venir.

Trois choses à savoir avant de toucher à ce fichier.

1. L'Assemblée réserve ses créneaux longtemps à l'avance mais ne publie leur
   contenu qu'à l'approche, une fois l'ordre du jour arrêté par la Conférence
   des présidents. Pendant les suspensions de séance, ce script produit donc
   légitimement une liste vide. Ce n'est pas une panne.

2. Le libellé d'un point d'ordre du jour est générique : « Discussion »,
   « Examen du texte ». Il n'a de sens qu'associé au titre du dossier
   législatif qu'il vise. On résout donc la référence vers le vrai titre.

3. On ne retient que les points rattachés à un dossier législatif. Les
   nominations de rapporteur et autres points internes n'ont pas leur place
   dans un onglet destiné au grand public.

Aucun résumé n'est généré : on affiche le titre officiel du dossier tel que
l'Assemblée le publie.
"""
import json
import ssl
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import categories

LEGISLATURE = 17
BASE = 'https://data.assemblee-nationale.fr/static/openData/repository'
URL_AGENDA = f'{BASE}/{LEGISLATURE}/vp/reunions/Agenda.json.zip'
URL_DOSSIERS = f'{BASE}/{LEGISLATURE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip'

SORTIE = Path('data') / 'agenda.json'
UA = 'Populous/1.0 (agenda; +https://maxboilot.github.io/populous/)'
DELAI = 120

# Les réunions annulées ne doivent pas apparaître. Les éventuelles sont
# signalées comme telles plutôt que présentées comme certaines.
ETATS_EXCLUS = {'Annulé', 'Annule'}

# Points de fonctionnement interne : ils portent une référence de dossier mais
# n'intéressent pas le grand public. On exclut par préfixe plutôt que par liste
# blanche, pour qu'un type d'examen nouveau apparaisse au lieu d'être perdu.
PREFIXES_EXCLUS = ('Nomination', 'Audition', "Rapport d'information")

# Au-delà de cette longueur, l'objet est déjà une phrase complète qui contient
# son propre sujet : y accoler le titre du dossier ferait doublon.
OBJET_AUTOSUFFISANT = 60


def telecharger(url):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=DELAI, context=ctx) as r:
        return BytesIO(r.read())


def liste(valeur):
    """L'export JSON de l'Assemblée renvoie tantôt un objet, tantôt un tableau."""
    if valeur is None:
        return []
    return valeur if isinstance(valeur, list) else [valeur]


def points_odj(reunion):
    odj = reunion.get('ODJ') or {}
    return liste((odj.get('pointsODJ') or {}).get('pointODJ'))


def references(point):
    refs = []
    for bloc in liste(point.get('dossiersLegislatifsRefs')):
        if isinstance(bloc, dict):
            for valeur in bloc.values():
                for v in liste(valeur):
                    if isinstance(v, str) and v.startswith('DLR'):
                        refs.append(v)
        elif isinstance(bloc, str) and bloc.startswith('DLR'):
            refs.append(bloc)
    return refs


def collecter(archive, depuis):
    """Parcourt l'archive des réunions et retient les points à venir."""
    retenus = []
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            if not nom.endswith('.json') or '/reunion/' not in nom:
                continue
            try:
                brut = json.loads(z.read(nom).decode('utf-8'))
            except Exception:
                continue
            r = brut.get('reunion', brut)
            debut = r.get('timeStampDebut') or ''
            if debut[:10] < depuis:
                continue
            etat = (r.get('cycleDeVie') or {}).get('etat')
            if etat in ETATS_EXCLUS:
                continue
            for point in points_odj(r):
                refs = references(point)
                if not refs:
                    continue
                type_point = (point.get('typePointODJ') or '').strip()
                if type_point.startswith(PREFIXES_EXCLUS):
                    continue
                retenus.append({
                    'date': debut[:10],
                    'heure': debut[11:16] if len(debut) >= 16 else None,
                    'objet': (point.get('objet') or '').strip(),
                    'refs': refs,
                    'incertain': etat not in ('Confirmé', 'Confirme'),
                })
    return retenus


def titres(archive, refs_voulues):
    """Résout les références de dossiers vers leur titre officiel."""
    trouves = {}
    with zipfile.ZipFile(archive) as z:
        index = {}
        for nom in z.namelist():
            if nom.endswith('.json') and '/dossierParlementaire/' in nom:
                index[Path(nom).stem] = nom
        for ref in refs_voulues:
            nom = index.get(ref)
            if not nom:
                continue
            try:
                brut = json.loads(z.read(nom).decode('utf-8'))
            except Exception:
                continue
            d = brut.get('dossierParlementaire', brut)
            titre = ((d.get('titreDossier') or {}).get('titre') or '').strip()
            if titre:
                trouves[ref] = titre
    return trouves


def intitule(objet, titre):
    """Assemble l'objet du point et le titre du dossier sans redondance.

    L'objet est tantôt un simple mot-clé (« Discussion »), tantôt une phrase
    complète qui énonce déjà le texte visé. Dans le second cas, accoler le
    titre produirait une répétition illisible.
    """
    objet = (objet or '').strip()
    titre = (titre or '').strip()
    if not objet:
        return titre
    if not titre:
        return objet
    if len(objet) > OBJET_AUTOSUFFISANT:
        return objet
    # Le titre est déjà énoncé dans l'objet : on ne le répète pas.
    if titre[:40].lower() in objet.lower():
        return objet
    return f'{objet} — {titre}'


def construire(depuis):
    retenus = collecter(telecharger(URL_AGENDA), depuis)
    print(f'points a venir rattaches a un dossier : {len(retenus)}')

    voulues = {r for p in retenus for r in p['refs']}
    resolus = titres(telecharger(URL_DOSSIERS), voulues) if voulues else {}
    print(f'dossiers resolus : {len(resolus)} / {len(voulues)}')

    lignes = []
    deja = set()
    for p in retenus:
        for ref in p['refs']:
            titre = resolus.get(ref)
            if not titre:
                continue
            cle = (p['date'], ref)
            if cle in deja:
                continue
            deja.add(cle)
            texte = intitule(p['objet'], titre)
            if p['incertain']:
                texte += ' (séance éventuelle)'
            lignes.append({
                'date': p['date'],
                'heure': p['heure'],
                'ordre_du_jour': texte,
                'themes': categories.classer(titre),
                'dossier': ref,
            })

    lignes.sort(key=lambda x: (x['date'], x['heure'] or '', x['ordre_du_jour']))
    return lignes


def main():
    depuis = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lignes = construire(depuis)
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(lignes, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'agenda.json : {len(lignes)} entrees a partir du {depuis}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
