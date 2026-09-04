#!/usr/bin/env python3
"""Construit data/sondages.json : les intentions de vote au premier tour de
la présidentielle 2027, par institut, avec photo de chaque candidat.

Source : la page Wikipédia « Liste de sondages sur l'élection
présidentielle française de 2027 », lue via l'API MediaWiki (lecture
publique, sans clé). Chaque sondage listé y est sourcé à sa notice
officielle déposée à la Commission des sondages — l'autorité française
qui contrôle la méthodologie des instituts. C'est la source la plus
fiable et la mieux tenue à jour qu'on puisse lire sans clé d'API privée
ni abonnement : des flux RSS d'instituts avaient été essayés d'abord,
mais ne donnent que des articles en texte libre, jamais les chiffres
eux-mêmes — voir l'ancien contenu de ce fichier dans l'historique git.

CE QUE CE SCRIPT NE FAIT PAS, ET POURQUOI :
Beaucoup de sondages testent plusieurs hypothèses de candidats (si tel
ou tel se présente à la place d'un autre). Ce script ne retient que la
PREMIÈRE hypothèse de chaque sondage (celle en tête du tableau Wikipédia)
et ignore les hypothèses alternatives listées à sa suite. Quand cette
première hypothèse remplace elle-même un candidat de la liste fixe par
quelqu'un d'autre (ex. Villepin à la place de Zemmour), ce score est
purement et simplement ignoré plutôt que mal attribué : un chiffre au
mauvais candidat coûte plus cher en crédibilité que ça ne vaut. Aucun
chiffre n'est calculé, recoupé ni interprété — chacun est recopié tel
quel depuis le tableau.

Portée actuelle : premier tour seulement, période « Second semestre
2026 » (la plus récente). Les périodes plus anciennes et le second tour
existent dans la même page et pourront être ajoutés plus tard.
"""
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = 'https://fr.wikipedia.org/w/api.php'
PAGE = "Liste de sondages sur l'élection présidentielle française de 2027"
UA = 'Populous/1.0 (+https://maxboilot.github.io/populous/; contact via github.com/maxboilot/populous)'
SORTIE = Path('data') / 'sondages.json'

MOIS = {
    'janvier': 1, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12,
}

# Couleur d'affichage par sigle de parti — usage interne à Populous,
# indépendante des couleurs de groupe parlementaire utilisées par la carte.
COULEURS_PARTI = {
    'LO': '#8B1A1A', 'LFI': '#C00D0D', 'PCF': '#B02020', 'LE': '#2F9E58',
    'PP': '#E8734A', 'RE': '#7B4591', 'HOR': '#5B8DEF', 'LR': '#2B5FAD',
    'DLF': '#3E5FC9', 'RN': '#1C2350', 'REC': '#5C2A2A', 'DIV': '#8891B0',
    'PS': '#E8547A',
}


def requete(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def sans_accents(t):
    return unicodedata.normalize('NFD', t or '').encode('ascii', 'ignore').decode('ascii').lower()


def depth0_split_first(s, sep='|'):
    """Coupe s au premier séparateur hors d'un [[...]] ou {{...}} — un
    wikilien ou un modèle peut contenir '|' sans que ce soit une frontière
    de cellule/attribut."""
    depth, i, n = 0, 0, len(s)
    while i < n:
        if s[i:i + 2] in ('[[', '{{'):
            depth += 1
            i += 2
            continue
        if s[i:i + 2] in (']]', '}}'):
            depth -= 1
            i += 2
            continue
        if depth == 0 and s[i] == sep:
            return s[:i], s[i + 1:]
        i += 1
    return s, None


def cell_content(line):
    line = line.strip()
    if line[:1] in ('!', '|'):
        line = line[1:]
    attrs, content = depth0_split_first(line, '|')
    return (content if content is not None else attrs).strip()


def strip_refs(s):
    return re.sub(r'<ref[^>]*?(/>|>.*?</ref>)', '', s, flags=re.S)


def wikilinks(s):
    return re.findall(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', s)


def first_wikilink_label(s):
    m = wikilinks(s)
    if not m:
        return None
    target, label = m[0]
    return (label or target).strip()


def parse_rows(table_wikitext):
    lines = table_wikitext.split('\n')
    rows, cur = [], []
    for line in lines[1:]:
        if line.startswith('|-'):
            if cur:
                rows.append(cur)
            cur = []
        elif line.strip():
            cur.append(line)
    if cur:
        rows.append(cur)
    return rows


def parse_candidats(rows):
    """Lignes 0 (photos) et 1 (nom+parti) de l'en-tête -> liste de candidats,
    dans l'ordre des colonnes (hors 'Autre', ajoutée à part)."""
    img_row, nom_row = rows[0], rows[1]
    # Les 3 premières cellules de img_row sont Sondeur/Date/Échantillon.
    img_cells = img_row[3:]
    candidats = []
    for img_line, nom_line in zip(img_cells, nom_row):
        img_content = cell_content(img_line)
        m = re.search(r'Fichier:\s*([^|\]]+)', img_content)
        # MediaWiki traite espace et underscore comme équivalents dans un nom
        # de fichier ; l'API renvoie toujours la forme avec espaces, donc on
        # normalise ici pour que la clé corresponde plus tard.
        fichier = m.group(1).strip().replace('_', ' ') if m else None

        nom_content = strip_refs(cell_content(nom_line))
        parts = nom_content.split('<br>')
        nom = first_wikilink_label(parts[0])
        parti = first_wikilink_label(parts[1]) if len(parts) > 1 else None
        if not nom:
            continue
        cle = sans_accents(nom).replace(' ', '_').replace("'", '')
        candidats.append({'cle': cle, 'nom': nom, 'parti': parti, 'fichier': fichier})
    return candidats


DATE_RE = re.compile(
    r'(?:(\d{1,2})\s*[- ]\s*)?(\d{1,2})\s+([a-zéû]+)', re.I)


def parse_date(texte, annee):
    t = sans_accents(texte).replace('aout', 'aout')
    m = DATE_RE.search(t)
    if not m:
        return None
    jour_fin = int(m.group(2))
    mois = MOIS.get(m.group(3))
    if not mois:
        return None
    try:
        return datetime(annee, mois, jour_fin, tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return None


def valeur_candidat(cell_line):
    """Renvoie (valeur_float_ou_None, substitue_bool)."""
    content = cell_content(cell_line)
    if '<br>' in content:
        # "2<br><small>'''[[Quelqu'un]]'''</small>" signale un candidat
        # substitué pour cette hypothèse : le score n'est attribué ni à lui
        # (absent de la liste fixe) ni au titulaire habituel de la colonne
        # (ce n'est pas lui qui a été mesuré ici) — on l'ignore purement.
        return None, True
    content = content.strip()
    if content in ('—', '-', ''):
        return None, False
    m = re.search(r"[\d]+(?:,\d+)?", content)
    if not m:
        return None, False
    return float(m.group(0).replace(',', '.')), False


def parse_sondages(rows, annee):
    sondages = []
    i = 2  # 0=photos, 1=noms, 2=barre de couleur
    while i < len(rows):
        row = rows[i]
        if len(row) == 15:
            sondeur_content = cell_content(row[0])
            link = wikilinks_url(sondeur_content)
            url, institut = link if link else (None, sondeur_content)
            date_iso = parse_date(cell_content(row[1]), annee)
            ech_content = cell_content(row[2])
            m = re.search(r'[\d ]+', ech_content.replace('{{formatnum:', '').replace('}}', ''))
            echantillon = int(re.sub(r'\D', '', m.group(0))) if m else None

            sondages.append({
                'institut': (institut or '').strip(),
                'source': url,
                'date': date_iso,
                'echantillon': echantillon,
                'cellules': row[3:],  # résolu en scores après coup (besoin des candidats)
            })
        i += 1
    return sondages


def wikilinks_url(content):
    """Cellule type '[https://url Texte]' -> (url, texte)."""
    m = re.search(r'\[(https?://\S+)\s+([^\]]+)\]', content)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def resoudre_images(fichiers):
    """Fichier:XXX.jpg (déjà présent dans la page) -> URL d'affichage réelle,
    via l'API Commons/Wikipédia en un seul aller-retour groupé."""
    fichiers = [f for f in dict.fromkeys(fichiers) if f]
    urls = {}
    for i in range(0, len(fichiers), 40):
        lot = fichiers[i:i + 40]
        titres = '|'.join('File:' + f for f in lot)
        url = (API + '?action=query&titles=' + urllib.parse.quote(titres) +
               '&prop=imageinfo&iiprop=url&iiurlwidth=200&iilimit=1&format=json')
        try:
            data = requete(url)
        except Exception as e:
            print(f'  echec resolution images ({e})')
            continue
        for page in data.get('query', {}).get('pages', {}).values():
            # L'API du wiki francophone normalise "File:" en "Fichier:" : on
            # retire le prefixe d'espace de noms quel qu'il soit, plutot que
            # de supposer sa langue.
            titre = page.get('title', '').split(':', 1)[-1]
            info = page.get('imageinfo')
            if info:
                urls[titre] = info[0].get('thumburl') or info[0].get('url')
    return urls


def main():
    print('Lecture de la page Wikipedia...')
    url = (API + '?action=query&prop=revisions&titles=' + urllib.parse.quote(PAGE) +
           '&rvslots=main&rvprop=content&format=json')
    data = requete(url)
    pages = data['query']['pages']
    page = list(pages.values())[0]
    if 'missing' in page:
        raise SystemExit('Page Wikipedia introuvable — le titre a peut-etre change.')
    wikitext = page['revisions'][0]['slots']['main']['*']

    entete = '==== Second semestre 2026 ===='
    debut = wikitext.index(entete)
    fin = wikitext.index('====', debut + len(entete))
    section = wikitext[debut:fin]
    tbl_debut = section.index('{|')
    tbl_fin = section.index('|}', tbl_debut)
    table = section[tbl_debut:tbl_fin]

    rows = parse_rows(table)
    candidats = parse_candidats(rows)
    print(f'{len(candidats)} candidats identifies.')

    bruts = parse_sondages(rows, annee=2026)
    print(f'{len(bruts)} sondages identifies (premiere hypothese de chacun).')

    fichiers = [c['fichier'] for c in candidats]
    images = resoudre_images(fichiers)
    for c in candidats:
        c['photo'] = images.get(c['fichier'])
        c['couleur'] = COULEURS_PARTI.get(c['parti'], '#8891B0')
        del c['fichier']

    sondages = []
    for s in bruts:
        cellules = s.pop('cellules')
        scores = {}
        for idx, cand in enumerate(candidats):
            if idx >= len(cellules):
                break
            val, substitue = valeur_candidat(cellules[idx])
            if val is not None:
                scores[cand['cle']] = val
        # "Autre" est la 12e cellule, hors liste de candidats nommés.
        if s['institut'] and scores:
            s['scores'] = scores
            sondages.append(s)

    sondages.sort(key=lambda s: s['date'] or '', reverse=True)

    sortie = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'https://fr.wikipedia.org/wiki/' + urllib.parse.quote(PAGE.replace(' ', '_')),
        'candidats': candidats,
        'sondages': sondages,
    }
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'sondages.json : {len(sondages)} sondages, {len(candidats)} candidats, '
          f'{round(SORTIE.stat().st_size/1024,1)} Ko')


if __name__ == '__main__':
    raise SystemExit(main())
