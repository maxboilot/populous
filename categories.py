#!/usr/bin/env python3
"""Classement thématique des textes législatifs.

Méthode assumée : un dictionnaire de mots-clés appliqué au titre officiel.
Volontairement rustique : déterministe, reproductible, lisible par un humain,
corrigeable en une ligne. Aucune interprétation n'est produite à la volée sur
un texte de loi réel.

CONVENTION IMPORTANTE
    'mot'   → mot entier (pluriels et féminins courants -s -e -es -x tolérés)
    'mot*'  → préfixe, suivi de n'importe quelles lettres

Cette distinction n'est pas cosmétique. Une recherche de simple sous-chaîne
produit des absurdités en français : « visa » capture « visant à », qui ouvre
la moitié des titres de loi ; « port » capture « portant » ; « eau » capture
« nouveau » ; « arme » capture « gendarme ». Un premier essai classait ainsi
61 lois sur 113 en Immigration.

Un texte peut relever de plusieurs thèmes : une loi sur les soins aux détenus
concerne la santé comme la justice. On ne force donc pas un choix unique, et
on préfère n'attribuer aucun thème plutôt qu'un thème douteux.
"""
import re
import unicodedata

# Ordre d'affichage dans l'interface. Le libellé est ce que voit le lecteur.
THEMES = [
    ('sante', 'Santé'),
    ('education', 'Éducation'),
    ('justice', 'Justice'),
    ('securite', 'Sécurité'),
    ('economie', 'Économie et fiscalité'),
    ('travail', 'Travail et emploi'),
    ('social', 'Solidarités et famille'),
    ('environnement', 'Environnement et énergie'),
    ('agriculture', 'Agriculture et alimentation'),
    ('logement', 'Logement et urbanisme'),
    ('transports', 'Transports'),
    ('numerique', 'Numérique'),
    ('defense', 'Défense et affaires étrangères'),
    ('institutions', 'Institutions et collectivités'),
    ('immigration', 'Immigration'),
    ('culture', 'Culture, sport et médias'),
]

MOTS = {
    'sante': [
        'sante', 'soin', 'soignant*', 'hopital', 'hopitaux', 'hospital*',
        'medic*', 'medecin*', 'infirmier*', 'patient', 'maladie', 'cancer',
        'psychiatr*', 'pharmac*', 'vaccin*', 'epidem*', 'sanitaire',
        'handicap*', 'autisme', 'fin de vie', 'aide a mourir', 'euthanasie',
        'addiction', 'tabac', 'stupefiant*', 'toxicoman*', 'don du sang',
        'endometriose', 'contamination',
    ],
    'education': [
        'education', 'ecole', 'scolaire', 'college', 'lycee', 'enseign*',
        'universit*', 'etudiant', 'eleve', 'apprentissage', 'creche',
        'baccalaureat', 'illettrisme',
    ],
    'justice': [
        'justice', 'penal*', 'judiciaire', 'magistrat', 'tribunal', 'prison',
        'detenu', 'peine', 'delit', 'crime', 'crimin*', 'procedur*',
        'avocat', 'greffe', 'victime', 'prescription', 'responsabilite civile',
        'expert judiciaire', 'recouvrement des avoirs', 'garde a vue', 'succession', 'condamn*',
        'juridiction*',
    ],
    'securite': [
        'securite', 'police', 'policier', 'gendarm*', 'terroris*', 'violence',
        'delinquan*', 'narcotrafic', 'trafic', 'armement', 'pompier',
        'secours', 'surveillance', 'harcelement', 'agression',
        'protection des mineurs',
    ],
    'economie': [
        'fiscal*', 'impot', 'taxe', 'budget*', 'financ*', 'economi*', 'comptable',
        'entrepris*', 'commerc*', 'industri*', 'banque', 'credit',
        'consommateur', 'concurrence', 'douan*', 'tva', 'inflation',
        'pouvoir d achat', 'artisan', 'double imposition', 'marche public',
        'marches publics', 'monnaie',
    ],
    'travail': [
        'travail', 'travailleur', 'emploi', 'salari*', 'salaire', 'chomage',
        'syndic*', 'retraite', 'pension', 'apprenti', 'fonction publique',
        'agent public', 'temps de travail', 'penibilite', 'representativite',
        'profession*',
    ],
    'social': [
        'solidarite', 'famille', 'familial*', 'enfant', 'enfance', 'parent',
        'aidant', 'pauvrete', 'precarite', 'allocation', 'prestation sociale',
        'minima', 'personne agee', 'aine', 'egalite', 'discrimination',
        'femme', 'protection sociale', 'natalite', 'mineur', 'conjugal*', 'homosexualite',
    ],
    'environnement': [
        'environnement*', 'climat*', 'ecolog*', 'pollution', 'biodiversite',
        'energie', 'energetique', 'nucleaire', 'renouvelable', 'eau',
        'dechet', 'plastique', 'carbone', 'foret', 'littoral', 'montagne',
        'animal', 'animaux', 'cadmium', 'pesticide', 'thermique',
    ],
    'agriculture': [
        'agricultur*', 'agriculteur', 'agricultrice', 'agricole', 'peche',
        'aliment*', 'elevage', 'viticol*', 'rural', 'ferme', 'veterinaire',
    ],
    'logement': [
        'logement', 'habitat', 'urbanisme', 'construction', 'immobilier',
        'locataire', 'locatif*', 'loyer', 'bailleur', 'copropriete', 'hebergement',
        'sans abri', 'squat',
    ],
    'transports': [
        'transport', 'ferroviaire', 'sncf', 'route', 'routier', 'automobile',
        'aerien', 'aeroport', 'maritime', 'velo', 'mobilite',
        'permis de conduire', 'circulation', 'voyageur',
    ],
    'numerique': [
        'numerique', 'internet', 'reseaux sociaux', 'donnees personnelles',
        'intelligence artificielle', 'cyber*', 'plateforme en ligne',
        'telecom*', 'informatique', 'algorithme', 'ecran',
    ],
    'defense': [
        'defense', 'armee', 'militaire', 'ancien combattant', 'veteran',
        'affaires etrangeres', 'traite', 'convention entre le gouvernement',
        'accord entre', 'union europeenne', 'otan', 'diplomat*', 'ukraine',
        'cooperation internationale', 'approbation de la convention',
    ],
    'institutions': [
        'constitution*', 'election', 'electoral*', 'referendum',
        'collectivite', 'commune', 'maire', 'departement', 'decentralisation',
        'outre mer', 'corse', 'martinique', 'guadeloupe', 'guyane', 'mayotte',
        'nouvelle caledonie', 'polynesie', 'parlement*', 'senat',
        'assemblee nationale', 'habilitation', 'ordonnance', 'elu local', 'candidat',
    ],
    'immigration': [
        'immigr*', 'asile', 'refugie', 'sejour', 'naturalisation',
        'frontiere', 'expulsion', 'visa', 'regularisation',
    ],
    'culture': [
        'culture', 'culturel*', 'patrimoine', 'musee', 'audiovisuel',
        'media', 'presse', 'journalis*', 'cinema', 'livre', 'artiste',
        'spectacle', 'sport', 'sportif', 'sportive', 'olympique', 'langue',
    ],
}

LIBELLES = dict(THEMES)


def sans_accents(texte):
    return unicodedata.normalize('NFD', texte or '').encode('ascii', 'ignore').decode('ascii')


def normaliser(texte):
    t = sans_accents(texte).lower()
    for c in ('\u2019', "'", '-'):
        t = t.replace(c, ' ')
    return t


def _motif(mot):
    """Compile un mot-clé en expression régulière selon la convention ci-dessus."""
    prefixe = mot.endswith('*')
    noyau = normaliser(mot[:-1] if prefixe else mot)
    noyau = re.escape(noyau).replace('\\ ', ' ')
    if prefixe:
        return re.compile('(?<![a-z])' + noyau + '[a-z]*')
    return re.compile('(?<![a-z])' + noyau + '(s|e|es|x)?(?![a-z])')


MOTIFS = {code: [_motif(m) for m in mots] for code, mots in MOTS.items()}


def classer(titre):
    """Renvoie la liste des codes de thème correspondant au titre.

    Liste vide si aucun mot-clé ne correspond : mieux vaut un texte non classé
    qu'un texte mal classé.
    """
    t = normaliser(titre)
    trouves = []
    for code, _ in THEMES:
        for motif in MOTIFS[code]:
            if motif.search(t):
                trouves.append(code)
                break
    return trouves
