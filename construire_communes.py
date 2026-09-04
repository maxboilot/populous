#!/usr/bin/env python3
"""Construit data/communes.json : la table de recherche de circonscription.

Objectif : permettre à quelqu'un de taper le nom de sa ville ou son code
postal, et de se voir proposer la ou les circonscriptions correspondantes.

Deux sources officielles, toutes deux en Licence Ouverte :

  - INSEE, table de correspondance communes / circonscriptions législatives
    (circo_composition.xlsx). C'est la seule source faisant autorité sur ce
    rattachement. Attention : une commune peut relever de PLUSIEURS
    circonscriptions — l'INSEE le signale explicitement. Les grandes villes
    sont découpées. On conserve donc une liste, jamais une valeur unique.

  - API Géo de l'État (geo.api.gouv.fr) pour les noms normalisés, les codes
    postaux et la population, cette dernière servant à classer les résultats
    par pertinence : quand on tape « Saint-Denis », on veut la grande ville
    en premier.

Le fichier produit est volontairement compact : il est chargé à la demande,
uniquement quand l'utilisateur ouvre la recherche, jamais au démarrage.
"""
import json
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
URL_INSEE = 'https://www.insee.fr/fr/statistiques/fichier/6436476/circo_composition.xlsx'
URL_GEO = ('https://geo.api.gouv.fr/communes'
           '?fields=nom,code,codesPostaux,departement,population&format=json')
SORTIE = Path('data') / 'communes.json'
UA = 'Populous/1.0 (+https://maxboilot.github.io/populous/)'


def telecharger(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def sans_accents(t):
    return unicodedata.normalize('NFD', t or '').encode('ascii', 'ignore').decode('ascii')


def cle_recherche(nom):
    """Forme normalisée pour la recherche : sans accents, sans ponctuation."""
    t = sans_accents(nom).lower()
    for c in ("'", '-', '.'):
        t = t.replace(c, ' ')
    return ' '.join(t.split())


def lire_feuille(z, chemin, chaines):
    for row in ET.fromstring(z.read(chemin)).iter(NS + 'row'):
        vals = []
        for c in row.iter(NS + 'c'):
            v = c.find(NS + 'v')
            texte = ''
            if v is not None and v.text is not None:
                texte = chaines[int(v.text)] if c.get('t') == 's' else v.text
            vals.append(texte)
        yield vals


def circos_par_commune():
    """code INSEE de commune -> liste de cles de circonscription (ex. 69|3)."""
    z = zipfile.ZipFile(BytesIO(telecharger(URL_INSEE)))
    chaines = [''.join(t.text or '' for t in si.iter(NS + 't'))
               for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(NS + 'si')]

    table = {}
    # sheet2 : communes de metropole et DOM. sheet4 : collectivites d outre-mer.
    for feuille in ('xl/worksheets/sheet2.xml', 'xl/worksheets/sheet4.xml'):
        try:
            lignes = lire_feuille(z, feuille, chaines)
        except KeyError:
            continue
        entete = None
        for vals in lignes:
            if entete is None:
                entete = vals
                continue
            if len(vals) < 7:
                continue
            code_commune = vals[4].strip()
            circo = vals[6].strip()
            if not code_commune or not circo or len(circo) < 4:
                continue
            # '01004' -> departement '01', circonscription 4
            dep, num = circo[:-3], circo[-3:]
            try:
                cle = dep + '|' + str(int(num))
            except ValueError:
                continue
            table.setdefault(code_commune, [])
            if cle not in table[code_commune]:
                table[code_commune].append(cle)
    return table


def main():
    print('telechargement de la table INSEE...')
    circos = circos_par_commune()
    print('communes rattachees a au moins une circonscription :', len(circos))
    multi = sum(1 for v in circos.values() if len(v) > 1)
    print('communes couvrant plusieurs circonscriptions :', multi)

    print('telechargement de l API Geo...')
    geo = json.loads(telecharger(URL_GEO).decode('utf-8'))
    print('communes de l API Geo :', len(geo))

    lignes = []
    sans_circo = 0
    for c in geo:
        code = c.get('code') or ''
        cles = circos.get(code)
        if not cles:
            sans_circo += 1
            continue
        lignes.append([
            c.get('nom') or '',
            cle_recherche(c.get('nom')),
            c.get('codesPostaux') or [],
            cles,
            c.get('population') or 0,
        ])

    # Les plus peuplees d abord : a saisie egale, on propose le lieu le plus
    # probable en tete.
    lignes.sort(key=lambda x: -x[4])
    print('communes sans circonscription connue (ignorees) :', sans_circo)

    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(lignes, ensure_ascii=False, separators=(',', ':')),
                      encoding='utf-8')
    print('communes.json :', len(lignes), 'communes,',
          round(SORTIE.stat().st_size / 1024), 'Ko')


if __name__ == '__main__':
    raise SystemExit(main())
