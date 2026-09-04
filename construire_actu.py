#!/usr/bin/env python3
"""Construit data/actu.json : le fil d'actualité de la Présidentielle 2027.

Source : les flux RSS publics de rédactions dont le métier est
l'information généraliste, pas des comptes de réseaux sociaux — un flux
Instagram n'est pas un format qu'on peut interroger sans clé d'API
propriétaire, et rien ne garantit sa fiabilité éditoriale.

Trois flux retenus, croisant volontairement des lignes différentes
(service public, droite, gauche) plutôt qu'une seule rédaction :
  - France Info (France Télévisions, service public)
  - Le Figaro
  - Libération

Le Monde a été écarté : son flux RSS porte une mention explicite
réservant son usage à un cadre « strictement personnel, non
professionnel et non collectif » — incompatible avec un site public.

Aucun résumé n'est généré : le titre et l'extrait sont ceux fournis par
la rédaction elle-même dans son propre flux, seulement nettoyés des
balises HTML. Même principe que historique.json — voir CLAUDE.md.

Filtre de pertinence : un mot-clé appliqué au titre et à l'extrait,
même convention que categories.py ('mot' = mot entier, 'mot*' = préfixe).
Un flux « Politique » généraliste parle surtout d'autre chose que de la
présidentielle ; mieux vaut laisser passer un peu moins que publier hors
sujet.
"""
import html
import json
import re
import unicodedata
import urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

SORTIE = Path('data') / 'actu.json'
UA = 'Populous/1.0 (+https://maxboilot.github.io/populous/)'
MAX_ARTICLES = 40

FLUX = [
    ('France Info', 'https://www.francetvinfo.fr/politique.rss'),
    ('Le Figaro', 'https://www.lefigaro.fr/rss/figaro_politique.xml'),
    ('Libération', 'https://www.liberation.fr/arc/outboundfeeds/rss-all/category/politique/'),
]

MOTS_CLES = [
    'presidentielle*', 'elysee', 'primaire presidentielle',
    'campagne presidentielle', 'election presidentielle',
]
# Signal plus faible, retenu seulement combiné à l'année : "candidat" ou
# "election" seuls parlent aussi bien des municipales ou des législatives.
MOTS_CLES_AVEC_ANNEE = ['candidat*', 'election*', 'sondage*']
ANNEE = '2027'


def sans_accents(texte):
    return unicodedata.normalize('NFD', texte or '').encode('ascii', 'ignore').decode('ascii')


def normaliser(texte):
    t = sans_accents(texte).lower()
    for c in ('’', "'", '-'):
        t = t.replace(c, ' ')
    return t


def _motif(mot):
    prefixe = mot.endswith('*')
    noyau = normaliser(mot[:-1] if prefixe else mot)
    noyau = re.escape(noyau).replace('\\ ', ' ')
    if prefixe:
        return re.compile('(?<![a-z])' + noyau + '[a-z]*')
    return re.compile('(?<![a-z])' + noyau + '(s|e|es|x)?(?![a-z])')


MOTIFS = [_motif(m) for m in MOTS_CLES]
MOTIFS_AVEC_ANNEE = [_motif(m) for m in MOTS_CLES_AVEC_ANNEE]


def pertinent(titre, extrait):
    t = normaliser((titre or '') + ' ' + (extrait or ''))
    if any(m.search(t) for m in MOTIFS):
        return True
    if ANNEE in t and any(m.search(t) for m in MOTIFS_AVEC_ANNEE):
        return True
    return False


def nettoyer_html(texte):
    """Retire les balises et décode les entités, sans reformuler le texte."""
    if not texte:
        return ''
    t = re.sub(r'<[^>]+>', ' ', texte)
    t = html.unescape(t)
    return ' '.join(t.split())


def telecharger(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml, text/xml'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def texte(el, tag):
    child = el.find(tag)
    return child.text if child is not None and child.text else ''


def image_de(item):
    ns_media = '{http://search.yahoo.com/mrss/}'
    m = item.find(ns_media + 'content')
    if m is not None and m.get('url'):
        return m.get('url')
    enc = item.find('enclosure')
    if enc is not None and (enc.get('type') or '').startswith('image') and enc.get('url'):
        return enc.get('url')
    return None


def lire_flux(source, url):
    articles = []
    try:
        brut = telecharger(url)
    except Exception as e:
        print(f'  {source} : echec telechargement ({e})')
        return articles

    try:
        racine = ET.fromstring(brut)
    except ET.ParseError as e:
        print(f'  {source} : flux illisible ({e})')
        return articles

    for item in racine.iter('item'):
        titre = nettoyer_html(texte(item, 'title'))
        lien = texte(item, 'link').strip()
        extrait = nettoyer_html(texte(item, 'description'))
        date_brute = texte(item, 'pubDate')
        if not titre or not lien:
            continue
        if not pertinent(titre, extrait):
            continue
        try:
            date = parsedate_to_datetime(date_brute)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        articles.append({
            'titre': titre,
            'lien': lien,
            'source': source,
            'date': date.isoformat(),
            'extrait': extrait,
            'image': image_de(item),
        })
    return articles


def main():
    tous = []
    vus = set()
    for source, url in FLUX:
        print(f'Lecture {source}...')
        for a in lire_flux(source, url):
            if a['lien'] in vus:
                continue
            vus.add(a['lien'])
            tous.append(a)

    tous.sort(key=lambda a: a['date'], reverse=True)
    tous = tous[:MAX_ARTICLES]

    from datetime import datetime
    sortie = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'articles': tous,
    }
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=None, separators=(',', ':')), encoding='utf-8')
    print(f'actu.json : {len(tous)} articles retenus sur {len(vus)} lus, {round(SORTIE.stat().st_size/1024,1)} Ko')


if __name__ == '__main__':
    raise SystemExit(main())
