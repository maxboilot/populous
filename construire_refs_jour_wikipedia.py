#!/usr/bin/env python3
"""Construit data/refs_jour_wikipedia.json : un fait de politique
française réellement survenu à cette date, pour chacun des 366 jours de
l'année — la seule source du projet qui couvre le calendrier en entier.

Pourquoi Wikipédia ici, et pas une IA qui "chercherait" le fait du
jour : chaque page "1er janvier", "2 janvier", ... "31 décembre" de
Wikipédia en français existe déjà, entretenue par des centaines de
contributeurs, et liste les événements de ce jour, siècle par siècle,
le plus souvent avec leurs propres sources. On ne fait qu'aller lire
ce qui y est déjà écrit — jamais une phrase n'est réécrite ou résumée
par ce script, seulement nettoyée du balisage wiki. Contenu sous
licence CC BY-SA : le lien vers la page Wikipédia sert de source et
d'attribution, affiché comme "Voir la source" dans le pop-up.

Filtre : ces pages couvrent l'histoire du monde entier, tous domaines
confondus (sciences, sport, culture...), pas seulement la politique
française. On ne garde qu'un événement daté dont le texte mentionne
un repère manifestement français (le pays, un régime, une institution
ou une figure politique française) — un filtre mécanique par mots-clés,
pas un jugement porté sur le contenu. Il est nécessairement imparfait :
il peut laisser passer un faux positif ou rater un événement français
qui ne nomme aucun de ces repères explicitement.

Priorité dans construire_refs_jour.py : curation manuelle > frise de
l'Assemblée nationale > ce fichier > texte récemment voté (dernier
recours, pour les rares jours qu'aucune des sources précédentes ne
couvre).

Incrémental comme construire_expose_motifs.py : 366 pages à récupérer
un jour, ça ne se refait pas à chaque run — seuls les jours absents du
cache sont redemandés.
"""
import html
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import reseau

DATA_DIR = Path('data')
SORTIE = DATA_DIR / 'refs_jour_wikipedia.json'

API = 'https://fr.wikipedia.org/w/api.php'
UA = 'Populous/1.0 (refs-jour-wikipedia; +https://maxboilot.github.io/populous/)'
DELAI = 30
PAUSE_ENTRE_APPELS = 0.4  # politesse envers l'API, pas de limite officielle contournée

MOIS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]
JOURS_PAR_MOIS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Repères jugés manifestement français : le pays, ses régimes et
# institutions, et des figures politiques françaises assez connues
# pour qu'un jour d'histoire les nommant soit presque toujours
# pertinent pour l'app. Liste volontairement large plutôt qu'exhaustive
# — voir la limite du filtre expliquée plus haut.
REPERES_FRANCAIS = [
    'france', 'français', 'française', 'gaulois',
    'république française', 'première république', 'iiie république',
    'ive république', 've république', 'iie république', 'ancien régime',
    'révolution française', 'premier empire',
    'assemblée nationale', 'assemblée constituante', 'convention nationale',
    'directoire', 'sénat français', 'palais bourbon',
    'royaume de france', 'monarchie de juillet', 'second empire', 'vichy',
    'front populaire', 'cinquième république', 'quatrième république',
    'troisième république', 'seconde république',
    'louis xiii', 'louis xiv', 'louis xv', 'louis xvi', 'louis xvii', 'louis xviii',
    'louis-philippe', 'napoléon', 'bonaparte', 'charles x',
    'robespierre', 'danton', 'olympe de gouges', 'jean jaurès', 'clemenceau',
    'léon blum', 'pierre mendès', 'charles de gaulle', 'georges pompidou',
    'giscard d’estaing', 'giscard d\'estaing', 'françois mitterrand',
    'jacques chirac', 'nicolas sarkozy', 'françois hollande', 'emmanuel macron',
    'simone veil', 'robert schuman', 'victor hugo', 'jules ferry', 'jules grévy',
    'thiers', 'mac mahon', 'aimé césaire', 'victor schœlcher', 'victor schoelcher',
    # "consulat" volontairement absent : un consulat diplomatique existe dans
    # n'importe quel pays, et le consulat romain/byzantin déclenchait de
    # faux positifs (constaté le 14 septembre 2026) — le Consulat français
    # se rattache déjà à napoléon/bonaparte ci-dessus.
]
LONGUEUR_MAX_TEXTE = 380


def titre_jour(jour, mois_idx):
    return f'{jour}er {MOIS[mois_idx]}' if jour == 1 else f'{jour} {MOIS[mois_idx]}'


class _ExtracteurEvenements(HTMLParser):
    """Ne garde que les <li> de premier niveau (un par événement) : les
    <ul> imbriqués (années à plusieurs événements) sont ignorés plutôt
    que mal démêlés — un événement daté de moins vaut mieux qu'un
    texte à moitié mélangé entre deux faits différents."""
    def __init__(self):
        super().__init__()
        self.profondeur_ul = 0
        self.dans_li_racine = False
        self.evenements = []
        self.courant = []

    def handle_starttag(self, tag, attrs):
        if tag == 'ul':
            self.profondeur_ul += 1
        elif tag == 'li' and self.profondeur_ul == 1 and not self.dans_li_racine:
            self.dans_li_racine = True
            self.courant = []
        elif tag == 'sup':
            self._ignorer_ref = True

    def handle_endtag(self, tag):
        if tag == 'ul':
            self.profondeur_ul = max(0, self.profondeur_ul - 1)
        elif tag == 'li' and self.dans_li_racine and self.profondeur_ul == 1:
            self.dans_li_racine = False
            self.evenements.append(''.join(self.courant).strip())
        elif tag == 'sup':
            self._ignorer_ref = False

    def handle_data(self, data):
        if self.dans_li_racine and self.profondeur_ul == 1 and not getattr(self, '_ignorer_ref', False):
            self.courant.append(data)


ANNEE_RE = re.compile(r'^\(?\s*(-?\d{1,4})\s*(?:av\. J\.-C\.)?\s*\)?\s*:\s*(.+)$', re.S)


def extraire_evenements(section_html):
    p = _ExtracteurEvenements()
    p.feed(section_html)
    resultats = []
    for brut in p.evenements:
        texte = html.unescape(re.sub(r'\s+', ' ', brut)).strip()
        m = ANNEE_RE.match(texte)
        if not m:
            continue
        annee_txt, reste = m.groups()
        try:
            annee = int(annee_txt)
        except ValueError:
            continue
        if not reste or len(reste) < 15:
            continue
        resultats.append((annee, reste.strip()))
    return resultats


def pertinent(texte):
    bas = texte.lower()
    return any(rep in bas for rep in REPERES_FRANCAIS)


def tronquer(texte, longueur=LONGUEUR_MAX_TEXTE):
    if len(texte) <= longueur:
        return texte
    coupe = texte[:longueur]
    dernier_espace = coupe.rfind(' ')
    return (coupe[:dernier_espace] if dernier_espace > 100 else coupe).rstrip('.,;: ') + '…'


def recuperer_jour(jour_page):
    titre_encode = urllib.parse.quote(jour_page.replace(' ', '_'))
    params = f'action=parse&page={titre_encode}&prop=text&section=1&redirects=1&format=json'
    brut = reseau.telecharger(f'{API}?{params}', timeout=DELAI, headers={'User-Agent': UA})
    data = json.loads(brut)
    if 'error' in data:
        return []
    return extraire_evenements(data['parse']['text']['*'])


def main():
    cache = {}
    if SORTIE.exists():
        try:
            cache = json.loads(SORTIE.read_text(encoding='utf-8')).get('refs', {})
        except Exception:
            cache = {}

    a_faire = []
    for mi in range(12):
        for j in range(1, JOURS_PAR_MOIS[mi] + 1):
            cle = f'{mi+1:02d}-{j:02d}'
            if cle not in cache:
                a_faire.append((cle, titre_jour(j, mi)))

    if not a_faire:
        print('refs_jour_wikipedia.json : rien de nouveau, 366/366 déjà en cache.')
        return
    print(f'{len(a_faire)} jour(s) à récupérer sur Wikipédia.')

    traites, retenus = 0, 0
    for cle, page in a_faire:
        try:
            evenements = recuperer_jour(page)
        except Exception as e:
            print(f'  {page} : échec ({e})')
            continue
        source_url = f'https://fr.wikipedia.org/wiki/{urllib.parse.quote(page.replace(" ", "_"))}'
        pertinents = [
            {'annee': annee, 'categorie': 'evenement', 'titre': None, 'texte': tronquer(texte), 'source': source_url}
            for annee, texte in evenements if pertinent(texte)
        ]
        if pertinents:
            pertinents.sort(key=lambda e: e['annee'])
            cache[cle] = pertinents[:3]  # au plus 3, pour ne pas noyer le pop-up
            retenus += 1
        traites += 1
        if traites % 40 == 0:
            print(f'  {traites}/{len(a_faire)} jours traités, {retenus} avec un fait retenu')
        time.sleep(PAUSE_ENTRE_APPELS)

    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source': 'https://fr.wikipedia.org/ (pages du jour, section "Événements", CC BY-SA)',
        'refs': dict(sorted(cache.items())),
    }
    SORTIE.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'refs_jour_wikipedia.json : {retenus}/{traites} nouveaux jours avec un fait retenu, {len(cache)} au total.')


if __name__ == '__main__':
    main()
