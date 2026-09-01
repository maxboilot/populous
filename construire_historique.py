#!/usr/bin/env python3
# Construit data/historique.json : la liste des lois votees dans leur ensemble
# sur les douze derniers mois.
#
# L archive compte plus de 5000 scrutins par an, dont l immense majorite sont
# des amendements. Seuls les votes portant sur un texte entier constituent une
# loi au sens ou un lecteur l entend. On ne retient donc que ceux-la.
#
# Aucun resume n est genere : on expose le titre officiel debarrasse de son
# jargon, plus le lien vers la page de l Assemblee. Rien n est invente.
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path('data')
SCRUTINS_DIR = DATA_DIR / 'scrutins'
SORTIE = DATA_DIR / 'historique.json'
FENETRE_JOURS = 365

APOS = chr(39)
PAR_OUV = chr(40)
PAR_FER = chr(41)

# Ordre important : les variantes longues doivent etre testees avant les
# courtes, sinon la courte capture la longue.
NATURES = [
    ('ensemble de la proposition de loi constitutionnelle', 'proposition de loi constitutionnelle'),
    ('ensemble de la proposition de loi organique', 'proposition de loi organique'),
    ('ensemble du projet de loi constitutionnelle', 'projet de loi constitutionnelle'),
    ('ensemble du projet de loi organique', 'projet de loi organique'),
    ('ensemble de la proposition de resolution', 'proposition de resolution'),
    ('ensemble de la proposition de loi', 'proposition de loi'),
    ('ensemble du projet de loi', 'projet de loi'),
]

# Connecteurs retires en tete du sujet pour obtenir un titre lisible.
CONNECTEURS = [
    'visant a ', 'tendant a ', 'ayant pour objet ',
    'relative aux ', 'relatifs aux ', 'relatif aux ',
    'relative au ', 'relatif au ', 'relative a ', 'relatifs a ', 'relatif a ',
    'en faveur des ', 'en faveur de ', 'en matiere de ',
    'portant ', 'autorisant ', 'ratifiant ', 'modifiant ', 'instaurant ',
    'creant ', 'pour ', 'sur ',
]


def sans_accents(texte):
    return unicodedata.normalize('NFD', texte).encode('ascii', 'ignore').decode('ascii')


def decoupe(titre):
    # Renvoie (nature, lecture, titre_court) a partir du titre officiel.
    brut = (titre or '').strip()
    repere = sans_accents(brut).lower()

    nature = None
    reste = brut
    for motif, libelle in NATURES:
        pos = repere.find(motif)
        if pos != -1:
            nature = libelle
            reste = brut[pos + len(motif):]
            break

    # Le stade de lecture est entre parentheses, en fin de titre.
    lecture = None
    r = reste.strip()
    if r.endswith('.'):
        r = r[:-1].rstrip()
    if r.endswith(PAR_FER):
        ouv = r.rfind(PAR_OUV)
        if ouv != -1:
            lecture = r[ouv + 1:-1].strip()
            r = r[:ouv]
    reste = r.strip().strip('.').strip()

    # On retire le connecteur de tete pour ne garder que le sujet.
    sans = sans_accents(reste).lower()
    for c in CONNECTEURS:
        if sans.startswith(c):
            reste = reste[len(c):]
            break

    reste = reste.strip()
    if reste:
        reste = reste[0].upper() + reste[1:]
    return nature, lecture, reste


def charger():
    limite = (datetime.now(timezone.utc) - timedelta(days=FENETRE_JOURS)).strftime('%Y-%m-%d')
    lois = []
    for chemin in SCRUTINS_DIR.glob('*.json'):
        try:
            f = json.loads(chemin.read_text(encoding='utf-8'))
        except Exception:
            continue
        date = f.get('date') or ''
        if date < limite:
            continue
        repere = sans_accents(f.get('titre') or '').lower()
        if not repere.startswith('l' + APOS + 'ensemble'):
            continue
        nature, lecture, court = decoupe(f.get('titre'))
        lois.append({
            'numero': f.get('numero'),
            'date': date,
            'titre': court,
            'titre_officiel': (f.get('titre') or '').strip(),
            'nature': nature,
            'lecture': lecture,
            'solennel': bool(f.get('solennel')),
            'adopte': bool(f.get('adopte')),
            'sort': f.get('sort'),
            'tally': f.get('tally'),
            'source': f.get('source'),
        })
    lois.sort(key=lambda x: (x['date'], x['numero'] or 0), reverse=True)
    return limite, lois


def main():
    limite, lois = charger()
    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'depuis': limite,
        'nombre': len(lois),
        'lois': lois,
    }
    SORTIE.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print('historique.json :', len(lois), 'lois depuis', limite)


if __name__ == '__main__':
    main()
