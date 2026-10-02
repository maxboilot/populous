#!/usr/bin/env python3
"""Construit data/texte_loi.json : le texte réel du scrutin en vedette du
jour, tel qu'adopté, article par article.

Pourquoi ce fichier existe : le panneau "Ce que ça change pour toi" a
besoin d'un contenu réel à croiser avec le profil de chaque personne, pas
d'un titre de loi ni d'une phrase inventée sur son effet. Voir CLAUDE.md —
aucune thèse d'impact n'est jamais générée ici ; ce script se contente de
récupérer le texte officiellement publié par l'Assemblée nationale et de
le découper proprement.

Le croisement avec le profil (données personnelles, jamais envoyées nulle
part) se fait entièrement côté client, dans le navigateur — voir
openImpactPanel() dans index.html. Ce script ne fait qu'exposer le texte
brut réel ; il n'invente ni ne résume rien.

Comment on retrouve le bon texte : Dossiers_Legislatifs.json.zip (même
source que construire_historique.py et construire_agenda.py) contient,
pour chaque décision de vote sur l'ensemble d'un texte, une référence
voteRefs.voteRef du type "VTANR5L17V<numero>" — le numéro de scrutin tel
qu'on le connaît déjà — directement associée à la référence du texte
"BTA" (Bulletin du Texte Adopté) de cette lecture précise. Pas de
correspondance par date ou par titre, donc pas d'ambiguïté possible
entre deux lectures d'un même dossier.
"""
import html
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

import reseau
import structure_scrutins as S

DATA_DIR = Path('data')
SORTIE = DATA_DIR / 'texte_loi.json'
TODAY = DATA_DIR / 'today.json'
SCRUTINS_DIR = DATA_DIR / 'scrutins'

LEGISLATURE = 17
URL_DOSSIERS = (
    f'https://data.assemblee-nationale.fr/static/openData/repository/'
    f'{LEGISLATURE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip'
)
URL_TEXTE = 'https://www.assemblee-nationale.fr/dyn/opendata/{ref}.html'
UA = 'Populous/1.0 (texte-loi; +https://maxboilot.github.io/populous/)'
DELAI = 180

# En dessous de cette longueur, une "ligne" est presque toujours un
# fragment de mise en forme (numéro de page, puce isolée) plutôt qu'un
# vrai morceau de texte de loi citable.
LONGUEUR_MIN_PARAGRAPHE = 25


def telecharger(url, timeout=DELAI):
    return reseau.telecharger(url, timeout=timeout, headers={'User-Agent': UA})


def _ref_texte(decision):
    # BTA (« Bulletin du Texte Adopté ») est la référence qui a une vraie
    # page /dyn/opendata/<ref>.html exploitable ; TAP existe dans les mêmes
    # données mais ne pointe vers aucun document consultable — vérifié en
    # conditions réelles (404 systématique), pas une supposition.
    textes = (decision.get('textesAssocies') or {}).get('texteAssocie')
    if isinstance(textes, dict):
        textes = [textes]
    for t in (textes or []):
        if t.get('typeTexte') == 'BTA':
            return t.get('refTexteAssocie')
    return None


def _cherche(node, voteref_cherche):
    if isinstance(node, dict):
        if node.get('@xsi:type') == 'Decision_Type':
            vr = (node.get('voteRefs') or {}).get('voteRef')
            if vr == voteref_cherche:
                return _ref_texte(node)
        sous = node.get('actesLegislatifs')
        if sous:
            interieur = sous.get('acteLegislatif') if isinstance(sous, dict) else sous
            trouve = _cherche(interieur, voteref_cherche)
            if trouve is not None:
                return trouve
    elif isinstance(node, list):
        for item in node:
            trouve = _cherche(item, voteref_cherche)
            if trouve is not None:
                return trouve
    return None


def trouver_reference_texte(numero):
    """Parcourt tous les dossiers législatifs à la recherche de la
    décision qui porte ce scrutin précis, renvoie la référence de son
    texte adopté (ou None si la décision n'a pas encore de texte associé
    publié)."""
    archive = telecharger(URL_DOSSIERS)
    voteref_cherche = f'VTANR5L{LEGISLATURE}V{numero}'
    with zipfile.ZipFile(BytesIO(archive)) as z:
        for nom in z.namelist():
            if not nom.endswith('.json') or '/dossierParlementaire/' not in nom:
                continue
            try:
                d = json.loads(z.read(nom))
            except Exception:
                continue
            dp = d.get('dossierParlementaire', d)
            actes = (dp.get('actesLegislatifs') or {}).get('acteLegislatif')
            if not actes:
                continue
            ref = _cherche(actes, voteref_cherche)
            if ref:
                return ref
    return None


def extraire_articles(html_brut):
    """Découpe le texte adopté (export HTML issu de Word, très fragmenté)
    en paragraphes propres, chacun rattaché au dernier "Article N"
    rencontré. Ignore l'en-tête (titre, dates, "Voir les numéros...") :
    on ne garde que ce qui suit le premier article."""
    texte = re.sub(r'<style.*?</style>', '', html_brut, flags=re.S)
    texte = re.sub(r'<script.*?</script>', '', texte, flags=re.S)
    texte = re.sub(r'</(p|h1|h2|h3|h4|h5|h6|li|div)>', '\n', texte)
    texte = re.sub(r'<br\s*/?>', '\n', texte)
    texte = re.sub(r'<[^>]+>', '', texte)
    texte = html.unescape(texte).replace('\xa0', ' ')
    lignes = [re.sub(r'\s+', ' ', l).strip() for l in texte.split('\n')]
    lignes = [l for l in lignes if l]

    articles = []
    article_courant = None
    dans_le_texte = False
    for ligne in lignes:
        if re.match(r'^Article\s+(\d+\w*|premier)\b', ligne, re.I):
            article_courant = ligne
            dans_le_texte = True
            continue
        if not dans_le_texte:
            continue
        if len(ligne) < LONGUEUR_MIN_PARAGRAPHE:
            continue
        articles.append({'article': article_courant, 'texte': ligne})
    return articles


REF_TEXTE_RE = re.compile(r'\b((?:PION|PRJL)ANR5L17(BTC|B)\d+)\b')


def trouver_texte_examine(intitule):
    """Pour un vote d'ARTICLE : le texte que les deputes examinent en seance.
    C'est le texte de la commission (BTC) quand il existe, sinon le texte
    depose. Renvoie (reference, 'commission' | 'depot') ou (None, None).

    Le texte definitif n'existe qu'apres le vote sur l'ensemble : tant qu'il
    n'est pas publie, on montre l'article tel que presente aux deputes, et
    l'app le dit (cf. openImpactPanel)."""
    cible = S.intitule_normalise(intitule)
    archive = telecharger(URL_DOSSIERS)
    with zipfile.ZipFile(BytesIO(archive)) as z:
        for nom in z.namelist():
            if '/dossierParlementaire/' not in nom or not nom.endswith('.json'):
                continue
            brut = z.read(nom).decode('utf-8')
            try:
                dp = json.loads(brut).get('dossierParlementaire', {})
            except Exception:
                continue
            titre = ((dp.get('titreDossier') or {}).get('titre')) or ''
            n = S.intitule_normalise(titre)
            if len(n) < 20 or not (n == cible or n in cible or cible in n):
                continue
            refs = {m.group(2): m.group(1) for m in REF_TEXTE_RE.finditer(brut)}
            if 'BTC' in refs:
                return refs['BTC'], 'commission'
            if 'B' in refs:
                return refs['B'], 'depot'
    return None, None


def paragraphes_de_l_article(articles, ref_article):
    """Garde les paragraphes de l'article demande (« Article 5 »), jamais
    ceux de « Article 5 bis » ni d'un autre article."""
    # « article premier » (libelle du scrutin) s'ecrit « Article 1er » dans le texte.
    synonymes = {'premier': ('premier', '1er', '1'), '1er': ('premier', '1er', '1')}
    voulus = {f'article {r}'.lower() for r in synonymes.get(ref_article.lower(), (ref_article,))}
    return [a for a in articles if re.sub(r'\s+', ' ', (a['article'] or '')).strip().lower() in voulus]


def ecrire(payload):
    SORTIE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def publier_article(numero, sc):
    """Scrutin vedette = un article adopte : on publie cet article tel que
    presente aux deputes (texte de la commission), avec sa portee, pour que
    l'app ne le fasse jamais passer pour le texte definitif."""
    ref_article = S.article_ref(sc['titre'])
    loi = S.texte_de_loi(sc['titre'])
    ref = origine = None
    if ref_article and loi:
        try:
            ref, origine = trouver_texte_examine(loi[1])
        except Exception as e:
            print(f'  recherche du texte examine : echec ({e})')
    if not ref:
        ecrire({'numero': numero, 'statut': 'non_publie'})
        print(f'texte_loi.json : scrutin {numero} (article), texte examine introuvable.')
        return
    try:
        articles = paragraphes_de_l_article(extraire_articles(telecharger(URL_TEXTE.format(ref=ref)).decode('utf-8')), ref_article)
    except Exception as e:
        print(f'  telechargement du texte examine : echec ({e})')
        articles = []
    if not articles:
        ecrire({'numero': numero, 'statut': 'non_publie'})
        print(f"texte_loi.json : scrutin {numero}, article {ref_article} introuvable dans {ref}.")
        return
    ecrire({
        'numero': numero,
        'statut': 'publie',
        'portee': 'article',
        'article_ref': ref_article,
        'source_texte': origine,
        'source': URL_TEXTE.format(ref=ref),
        'articles': articles,
    })
    print(f'texte_loi.json : scrutin {numero}, article {ref_article} ({origine}), {len(articles)} paragraphes.')


def main():
    if not TODAY.exists():
        print('today.json absent, rien à faire.')
        return
    today = json.loads(TODAY.read_text(encoding='utf-8'))
    numero = today.get('featured_numero')
    if numero is None:
        numero = today.get('last_featured_numero')
    if numero is None:
        ecrire({'numero': None, 'statut': 'aucun'})
        print('texte_loi.json : aucun scrutin en vedette pour le moment.')
        return

    chemin_scrutin = SCRUTINS_DIR / f'{numero}.json'
    if not chemin_scrutin.exists():
        ecrire({'numero': numero, 'statut': 'non_publie'})
        print(f'texte_loi.json : fichier scrutin {numero} introuvable.')
        return
    sc = json.loads(chemin_scrutin.read_text(encoding='utf-8'))

    if not sc.get('adopte'):
        ecrire({'numero': numero, 'statut': 'rejete'})
        print(f'texte_loi.json : scrutin {numero} rejeté, rien à publier.')
        return

    if S.nature(sc['titre']) == 'article':
        publier_article(numero, sc)
        return

    try:
        ref = trouver_reference_texte(numero)
    except Exception as e:
        print(f'  recherche du texte adopté : échec ({e})')
        ref = None

    if not ref:
        ecrire({'numero': numero, 'statut': 'non_publie'})
        print(f'texte_loi.json : scrutin {numero} adopté, texte pas encore publié.')
        return

    try:
        html_brut = telecharger(URL_TEXTE.format(ref=ref)).decode('utf-8')
        articles = extraire_articles(html_brut)
    except Exception as e:
        print(f'  téléchargement du texte adopté : échec ({e})')
        ecrire({'numero': numero, 'statut': 'non_publie'})
        return

    if not articles:
        ecrire({'numero': numero, 'statut': 'non_publie'})
        print(f'texte_loi.json : scrutin {numero}, texte récupéré mais vide après extraction.')
        return

    ecrire({
        'numero': numero,
        'statut': 'publie',
        'source': URL_TEXTE.format(ref=ref),
        'articles': articles,
    })
    print(f'texte_loi.json : scrutin {numero}, {len(articles)} paragraphes extraits.')


if __name__ == '__main__':
    main()
