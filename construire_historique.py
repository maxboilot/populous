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
#
# index.json va plus loin que historique.json : la plupart des votes a
# l Assemblee se font a main levee, sans scrutin public (voir CLAUDE.md et
# construire_agenda.py). Un texte qui disparaissait simplement de "A venir"
# une fois sa date passee, sans laisser de trace ensuite, donnait
# l impression que l app avait perdu le fil. Les dossiers legislatifs
# (meme source que construire_agenda.py) portent pourtant une decision
# "adoptee"/"rejetee" meme sans scrutin - on l ajoute donc a index.json,
# marquee type=main_levee pour la distinguer d un vrai scrutin. Jamais
# fusionnee dans historique.json lui-meme : construire_groupes_themes.py
# et le tirage de la Boussole ont besoin d un vrai scrutins/<numero>.json
# derriere chaque entree, qu une decision a main levee n a pas.
import json
import unicodedata
import zipfile
from io import BytesIO

import categories
import reseau
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path('data')
SCRUTINS_DIR = DATA_DIR / 'scrutins'
SORTIE = DATA_DIR / 'historique.json'
INDEX = DATA_DIR / 'index.json'
FENETRE_JOURS = 365

LEGISLATURE = 17
URL_DOSSIERS = (
    f'https://data.assemblee-nationale.fr/static/openData/repository/'
    f'{LEGISLATURE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip'
)
UA_DOSSIERS = 'Populous/1.0 (historique; +https://maxboilot.github.io/populous/)'
DELAI_DOSSIERS = 180

# Correspondance entre le code officiel de conclusion d une lecture
# (statutConclusion.fam_code, cote Dossiers_Legislatifs) et l un des trois
# statuts que l app affiche. Construite a partir d un echantillon reel du
# jeu de donnees plutot que devinee - voir le detail des codes rencontres
# dans l historique de ce fichier. Volontairement partielle : les codes
# absents d ici (accord/desaccord de commission mixte paritaire, motion de
# procedure adoptee, rejet prealable en commission) ne decrivent pas le
# sort du texte lui-meme de la meme facon qu un adopte/rejete, et sont
# laisses de cote plutot que forces dans une case qui ne leur correspond
# pas vraiment.
FAM_ADOPTE = {'TSORTF01', 'TSORTF03', 'TSORTF06', 'TSORTF18', 'TSORTF19'}
FAM_ADOPTE_MODIFIE = {
    'TSORTF02',
    # "modifiee" seule (sans "adoptee" dans le libelle) n apparait que sur
    # les lectures en 2e assemblee saisie : la chambre modifie le texte et
    # le renvoie a l autre chambre. Dans la procedure des navettes, une
    # chambre ne peut pas "modifier" un texte sans avoir adopte sa propre
    # version a cette lecture - deduit du contexte plutot que d un libelle
    # explicite, donc a corriger si un cas contraire est repere un jour.
    'TSORTF05',
}
FAM_REJETE = {'TSORTF07', 'TSORTF24'}

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


def telecharger(url):
    return BytesIO(reseau.telecharger(url, timeout=DELAI_DOSSIERS, headers={'User-Agent': UA_DOSSIERS}))


def classer_statut(fam_code):
    if fam_code in FAM_ADOPTE:
        return 'adopte', True
    if fam_code in FAM_ADOPTE_MODIFIE:
        return 'adopte_modifie', True
    if fam_code in FAM_REJETE:
        return 'rejete', False
    return None, None


def decisions_du_dossier(node):
    """Parcourt recursivement les actesLegislatifs d un dossier, renvoie les
    Decision_Type rencontres (une par lecture conclue)."""
    trouves = []
    if isinstance(node, dict):
        if node.get('@xsi:type') == 'Decision_Type':
            trouves.append(node)
        sous = node.get('actesLegislatifs')
        if sous:
            interieur = sous.get('acteLegislatif') if isinstance(sous, dict) else sous
            trouves.extend(decisions_du_dossier(interieur))
    elif isinstance(node, list):
        for item in node:
            trouves.extend(decisions_du_dossier(item))
    return trouves


def charger_main_levee(limite):
    """Decisions de lecture sans scrutin associe (vote a main levee) - pour
    qu un texte n disparaisse pas simplement de "A venir" une fois sa date
    passee sans laisser de trace. Jamais ajoutees a historique.json lui-meme,
    voir le commentaire en tete de fichier."""
    try:
        archive = telecharger(URL_DOSSIERS)
    except Exception as e:
        print(f'  dossiers legislatifs : echec telechargement ({e})')
        return []

    entrees = []
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            if not nom.endswith('.json') or '/dossierParlementaire/' not in nom:
                continue
            try:
                brut = json.loads(z.read(nom).decode('utf-8'))
            except Exception:
                continue
            d = brut.get('dossierParlementaire', brut)
            titre_dossier = ((d.get('titreDossier') or {}).get('titre') or '').strip()
            chemin_titre = (d.get('titreDossier') or {}).get('titreChemin')
            if not titre_dossier:
                continue
            actes = (d.get('actesLegislatifs') or {}).get('acteLegislatif')
            if not actes:
                continue
            for dec in decisions_du_dossier(actes):
                if dec.get('voteRefs'):
                    continue  # deja couvert par un vrai scrutin, cf. charger()
                date = (dec.get('dateActe') or '')[:10]
                if not date or date < limite:
                    continue
                fam_code = (dec.get('statutConclusion') or {}).get('fam_code')
                statut, adopte = classer_statut(fam_code)
                if statut is None:
                    continue
                source = (
                    f'https://www.assemblee-nationale.fr/dyn/{LEGISLATURE}/dossiers/{chemin_titre}'
                    if chemin_titre else None
                )
                entrees.append({
                    'numero': None,
                    'dossier': d.get('uid'),
                    'date': date,
                    'titre': titre_dossier,
                    'adopte': adopte,
                    'statut': statut,
                    'themes': categories.classer(titre_dossier),
                    'source': source,
                    'type': 'main_levee',
                })
    return entrees


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
            'statut': 'adopte' if f.get('adopte') else 'rejete',
            'themes': categories.classer(f.get('titre') or ''),
            'sort': f.get('sort'),
            'tally': f.get('tally'),
            'source': f.get('source'),
            'type': 'scrutin',
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

    main_levee = charger_main_levee(limite)

    # index.json : le format attendu par l onglet Historique de l application.
    # Fusionne les scrutins et les decisions a main levee (voir plus haut),
    # trie du plus ancien au plus recent car l interface applique elle-meme
    # un reverse() a l affichage. La Boussole, qui a besoin d un vrai
    # scrutins/<numero>.json derriere chaque question, filtre elle-meme sur
    # type=="scrutin" avant de piocher - a ne jamais retirer cote app tant
    # que ce fichier melange les deux types d entree.
    index_scrutins = [
        {
            'numero': l['numero'],
            'date': l['date'],
            'titre': l['titre'],
            'adopte': l['adopte'],
            'statut': l['statut'],
            'source': l['source'],
            'themes': l['themes'],
            'type': 'scrutin',
        }
        for l in lois
    ]
    index = index_scrutins + main_levee
    index.sort(key=lambda x: x['date'])
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

    print('historique.json :', len(lois), 'lois depuis', limite)
    print('index.json      :', len(index), 'entrees (', len(index_scrutins), 'scrutins +',
          len(main_levee), 'a main levee)')


if __name__ == '__main__':
    main()
