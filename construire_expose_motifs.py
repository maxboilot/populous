#!/usr/bin/env python3
"""Construit data/expose_motifs.json : un court résumé, réellement écrit
par les auteurs de chaque texte, pour les scrutins que tire la Boussole.

Pourquoi ce fichier existe : le titre officiel d'un scrutin n'est pas
toujours clair (voir renderBoussoleQuestion() dans index.html), et on ne
peut pas se permettre d'écrire nous-mêmes une explication du contenu
d'un texte qu'on ne connaît pas avec certitude — voir CLAUDE.md.

La bonne source existe déjà, on ne l'avait simplement pas exploitée :
chaque proposition ou projet de loi est déposé avec un "Exposé des
motifs" rédigé par ses propres auteurs, qui explique en langage clair
pourquoi le texte existe. Ce n'est jamais nous qui résumons — on cite
ce document officiel, tronqué pour rester un résumé plutôt que
recopié en entier.

Contrairement à construire_texte_loi.py (le seul scrutin en vedette du
jour), ce script couvre tout le bassin de tirage de la Boussole — donc
potentiellement des centaines de textes au fil du temps. Pour que ça
reste supportable, il est strictement incrémental : à chaque run, on ne
va chercher que les scrutins pas encore en cache, jamais tout le monde.
Un seul passage sur Dossiers_Legislatifs.json.zip par run, quel que soit
le nombre de scrutins manquants.
"""
import html
import json
import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import reseau

DATA_DIR = Path('data')
INDEX = DATA_DIR / 'index.json'
SORTIE = DATA_DIR / 'expose_motifs.json'

LEGISLATURE = 17
URL_DOSSIERS = (
    f'https://data.assemblee-nationale.fr/static/openData/repository/'
    f'{LEGISLATURE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip'
)
URL_TEXTE = 'https://www.assemblee-nationale.fr/dyn/opendata/{ref}.html'
UA = 'Populous/1.0 (expose-motifs; +https://maxboilot.github.io/populous/)'
DELAI = 180

VOTEREF_RE = re.compile(r'VTANR5L\d+V(\d+)$')
LONGUEUR_MAX_RESUME = 480


def _walk_dossier(node, numeros, depot_ref):
    """Parcourt un dossier une seule fois : collecte tous les numéros de
    scrutin qu'il contient (via voteRefs) et la référence de son texte
    déposé initial (celui qui porte l'exposé des motifs)."""
    if isinstance(node, dict):
        if node.get('@xsi:type') == 'DepotInitiative_Type' and not depot_ref:
            ref = node.get('texteAssocie')
            if ref:
                depot_ref.append(ref)
        if node.get('@xsi:type') == 'Decision_Type':
            vr = (node.get('voteRefs') or {}).get('voteRef')
            m = VOTEREF_RE.match(vr) if vr else None
            if m:
                numeros.add(int(m.group(1)))
        sous = node.get('actesLegislatifs')
        if sous:
            interieur = sous.get('acteLegislatif') if isinstance(sous, dict) else sous
            _walk_dossier(interieur, numeros, depot_ref)
    elif isinstance(node, list):
        for item in node:
            _walk_dossier(item, numeros, depot_ref)


def construire_mapping_depot(numeros_voulus):
    """Un seul passage sur l'archive : s'arrête dès que tous les numéros
    demandés ont trouvé leur dossier, pas besoin d'aller plus loin."""
    archive = reseau.telecharger(URL_DOSSIERS, timeout=DELAI, headers={'User-Agent': UA})
    mapping = {}
    restants = set(numeros_voulus)
    with zipfile.ZipFile(BytesIO(archive)) as z:
        for nom in z.namelist():
            if not restants:
                break
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
            numeros_du_dossier, depot_ref = set(), []
            _walk_dossier(actes, numeros_du_dossier, depot_ref)
            concernes = numeros_du_dossier & restants
            if concernes and depot_ref:
                for n in concernes:
                    mapping[n] = depot_ref[0]
                restants -= concernes
    return mapping


def extraire_expose(html_brut):
    """Isole le texte entre le titre "EXPOSÉ DES MOTIFS" et le début du
    texte de loi lui-même, tronqué pour rester un résumé — jamais recopié
    en entier."""
    texte = re.sub(r'<style.*?</style>', '', html_brut, flags=re.S)
    texte = re.sub(r'<script.*?</script>', '', texte, flags=re.S)
    texte = re.sub(r'</(p|h1|h2|h3|h4|h5|h6|li|div)>', '\n', texte)
    texte = re.sub(r'<br\s*/?>', '\n', texte)
    texte = re.sub(r'<[^>]+>', '', texte)
    texte = html.unescape(texte).replace('\xa0', ' ')
    lignes = [re.sub(r'\s+', ' ', l).strip() for l in texte.split('\n')]
    lignes = [l for l in lignes if l]

    debut = None
    for i, l in enumerate(lignes):
        if l.upper().replace('É', 'E').startswith('EXPOSE DES MOTIFS'):
            debut = i
            break
    if debut is None:
        return None

    arret = re.compile(
        r'^(PROPOSITION DE LOI|PROJET DE LOI|proposition de loi|projet de loi|'
        r'Article (1er|premier|\d))', re.I)
    paragraphes = []
    for ligne in lignes[debut + 1:]:
        if ligne.rstrip(',') in ('Mesdames', 'Mesdames, Messieurs', 'Monsieur le Président'):
            continue
        if arret.match(ligne):
            break
        if len(ligne) < 20:
            continue
        paragraphes.append(ligne)
        if sum(len(p) for p in paragraphes) > LONGUEUR_MAX_RESUME:
            break
    if not paragraphes:
        return None

    resume = ' '.join(paragraphes)
    if len(resume) > LONGUEUR_MAX_RESUME:
        coupe = resume[:LONGUEUR_MAX_RESUME]
        dernier_espace = coupe.rfind(' ')
        resume = (coupe[:dernier_espace] if dernier_espace > 100 else coupe).rstrip('.,;: ') + '…'
    return resume


def main():
    if not INDEX.exists():
        print('index.json absent, rien à faire.')
        return
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    pool = {r['numero'] for r in index if r.get('type') == 'scrutin' and r.get('numero') is not None}

    cache = {}
    if SORTIE.exists():
        try:
            cache = {int(k): v for k, v in json.loads(SORTIE.read_text(encoding='utf-8')).get('expose', {}).items()}
        except Exception:
            cache = {}

    manquants = pool - set(cache.keys())
    if not manquants:
        print(f'expose_motifs.json : rien de nouveau, {len(cache)} déjà en cache.')
        return
    print(f'{len(manquants)} nouveaux textes à documenter sur {len(pool)} au total.')

    try:
        mapping = construire_mapping_depot(manquants)
    except Exception as e:
        print(f'  recherche des dépôts initiaux : échec ({e})')
        mapping = {}

    # Limite connue et acceptée : un texte d'abord déposé au Sénat (un
    # "projet de loi" qui y commence sa navette) porte une référence de
    # dépôt de la forme "PRJLSN..." — hébergée sur senat.fr, pas sur
    # assemblee-nationale.fr. Ces cas échouent proprement en 404 plutôt
    # que d'être fabriqués ou faussement rattachés ; environ un tiers du
    # bassin de la Boussole est concerné (constaté le 12 septembre 2026).
    # Intégrer les données du Sénat serait un chantier séparé.
    trouves = 0
    for numero in sorted(manquants):
        ref = mapping.get(numero)
        if not ref:
            continue
        try:
            html_brut = reseau.telecharger(
                URL_TEXTE.format(ref=ref), timeout=DELAI, headers={'User-Agent': UA}
            ).decode('utf-8')
            resume = extraire_expose(html_brut)
        except Exception as e:
            print(f'  scrutin {numero} : échec ({e})')
            continue
        if resume:
            cache[numero] = resume
            trouves += 1

    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'expose': {str(k): v for k, v in cache.items()},
    }
    SORTIE.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'expose_motifs.json : {trouves}/{len(manquants)} nouveaux résumés ajoutés, {len(cache)} au total.')


if __name__ == '__main__':
    main()
