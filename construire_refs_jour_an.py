#!/usr/bin/env python3
"""Construit data/refs_jour_an.json : des événements réellement datés
(jour précis), extraits mécaniquement de la frise "Histoire et
patrimoine" de l'Assemblée nationale — la meilleure source
institutionnelle pour l'histoire politique et parlementaire française,
de l'Ancien Régime à la Ve République.

Pourquoi un script séparé de refs_jour_evenements.json : ce fichier-ci
est entièrement automatique (aucune ligne écrite à la main) — mais ce
n'est pas une thèse générée, voir CLAUDE.md. Rien n'est interprété ni
résumé : le titre et le texte sont ceux publiés par l'Assemblée
nationale elle-même, seulement nettoyés du HTML. La seule tâche de ce
script est d'aller chercher un contenu déjà écrit et déjà vérifié par
une source officielle, exactement comme construire_expose_motifs.py le
fait pour les exposés des motifs.

Priorité dans construire_refs_jour.py : un fait choisi à la main dans
refs_jour_evenements.json prime toujours sur un fait trouvé ici.

Couverture : cette frise est un choix éditorial de temps forts, pas un
almanach exhaustif — elle ne couvre donc qu'une partie des 366 jours
(une quarantaine de dates precises, à ce jour). C'est très bien : mieux
vaut peu de jours honnêtement sourcés que d'en inventer pour les
jours restants.
"""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import reseau

DATA_DIR = Path('data')
SORTIE = DATA_DIR / 'refs_jour_an.json'

BASE = 'https://www.assemblee-nationale.fr/dyn/histoire-et-patrimoine'
PERIODES = [
    'ancien-regime', 'revolution-francaise', 'consulat-et-premier-empire',
    'restauration', 'monarchie-de-juillet', 'deuxieme-republique',
    'second-empire', 'troisieme-republique', 'deuxieme-guerre-mondiale',
    'quatrieme-republique', 'cinquieme-republique',
]
UA = 'Populous/1.0 (refs-jour-an; +https://maxboilot.github.io/populous/)'
DELAI = 60

MOIS = {
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5,
    'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8, 'septembre': 9,
    'octobre': 10, 'novembre': 11, 'decembre': 12, 'décembre': 12,
}

BLOC_RE = re.compile(
    r'<div class="histoire-periode" id="date-[a-z0-9]+">(.*?)'
    r'(?=<div class="histoire-periode" id="date-|<div class="histoire-periode-nav|$)',
    re.S,
)
DATE_RE = re.compile(r'<span class="histoire-periode__date[^"]*"><span class="ezstring-field">([^<]+)</span></span>')
TITRE_RE = re.compile(r'<h3 class="histoire-periode__title"><span class="ezstring-field">(.*?)</span></h3>', re.S)
DESC_RE = re.compile(r'<div class="ezrichtext-field">(.*?)</div>\s*</div>', re.S)
LIEN_RE = re.compile(r'<a href="(/dyn/histoire-et-patrimoine/[^"#]+)#date"')
# Une date peut couvrir 2 jours ("9 et 10 novembre 1799") : seul le premier
# jour sert à indexer — l'événement reste rattaché à cette seule entrée.
JOUR_MOIS_ANNEE_RE = re.compile(r'(\d{1,2})(?:\s*(?:er)?\s*(?:et|-)\s*\d{1,2})?\s+([a-zéû]+)\s+(\d{4})', re.I)
LONGUEUR_MAX_TEXTE = 420


def nettoyer_html(fragment):
    texte = re.sub(r'<[^>]+>', ' ', fragment)
    texte = html.unescape(texte).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', texte).strip()


def tronquer(texte, longueur=LONGUEUR_MAX_TEXTE):
    if len(texte) <= longueur:
        return texte
    coupe = texte[:longueur]
    dernier_espace = coupe.rfind(' ')
    return (coupe[:dernier_espace] if dernier_espace > 100 else coupe).rstrip('.,;: ') + '…'


def extraire_evenements(page_html, slug):
    evenements = []
    for bloc_m in BLOC_RE.finditer(page_html):
        bloc = bloc_m.group(1)
        date_m = DATE_RE.search(bloc)
        titre_m = TITRE_RE.search(bloc)
        if not (date_m and titre_m):
            continue
        date_txt = date_m.group(1).strip()
        jm = JOUR_MOIS_ANNEE_RE.search(date_txt)
        if not jm:
            continue  # date pas assez précise (juste une année ou un mois) : inutilisable ici
        jour, mois_txt, annee = jm.groups()
        mois = MOIS.get(mois_txt.lower()) or MOIS.get(mois_txt.lower().replace('û', 'u').replace('é', 'e'))
        if not mois:
            continue
        desc_m = DESC_RE.search(bloc)
        lien_m = LIEN_RE.search(bloc)
        evenements.append({
            'jour': f'{mois:02d}-{int(jour):02d}',
            'annee': int(annee),
            'categorie': 'evenement',
            'titre': nettoyer_html(titre_m.group(1)),
            'texte': tronquer(nettoyer_html(desc_m.group(1))) if desc_m else '',
            'source': f'{BASE}/{lien_m.group(1).rsplit("/", 1)[-1]}' if lien_m else f'{BASE}/{slug}',
        })
    return evenements


def main():
    refs = {}
    total = 0
    for slug in PERIODES:
        try:
            page = reseau.telecharger(f'{BASE}/{slug}', timeout=DELAI, headers={'User-Agent': UA}).decode('utf-8')
        except Exception as e:
            print(f'  {slug} : échec ({e})')
            continue
        evenements = extraire_evenements(page, slug)
        for ev in evenements:
            jour = ev.pop('jour')
            refs.setdefault(jour, []).append(ev)
        total += len(evenements)
        print(f'  {slug} : {len(evenements)} événement(s) daté(s) précisément')

    for jour in refs:
        refs[jour].sort(key=lambda e: e['annee'])

    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source': BASE,
        'refs': dict(sorted(refs.items())),
    }
    SORTIE.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'refs_jour_an.json : {total} événements, {len(refs)} jours distincts.')


if __name__ == '__main__':
    main()
