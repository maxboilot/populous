#!/usr/bin/env python3
"""Construit data/decisions_texte.json : les décisions de l'Assemblée nationale sur des TEXTES DE LOI (adopté / rejeté) des derniers jours,
qu'elles aient eu un scrutin public ou non.

Pourquoi : data/scrutins ne contient que les scrutins publics. Un texte adopté ou rejeté sans scrutin public (projets de loi d'approbation
d'accords internationaux, propositions de loi votées à main levée...) n'y laisse aucune trace, alors qu'il est une loi votée comme une autre.
La source officielle est l'archive « Dossiers législatifs » de l'open data de l'Assemblée (la même que construire_agenda.py) : chaque lecture
d'un texte y contient un acte « Décision » (codeActe ...-DEBATS-DEC) avec le sort, la date et, parfois, la référence du scrutin.

À savoir (constaté le 9 novembre 2026 en lisant les ~3 200 dossiers de la législature) :
- Le mot « main levée » n'apparaît jamais dans ces données : on sait seulement s'il y a une référence de scrutin (voteRefs), pas comment
  le vote s'est fait. Rien n'est donc affirmé sur le mode de vote.
- voteRefs est SOUVENT VIDE alors qu'un scrutin existe (ex. scrutin 8705 du 13 octobre) : publier_reseaux.py recoupe avec data/scrutins avant de
  considérer qu'un texte n'a pas eu de scrutin.
- Le stade se lit dans l'ordre des actes de premier niveau du dossier : ['AN1'] = Assemblée première assemblée saisie ; ['SN1', 'AN1'] = Sénat d'abord.
- On ne garde que les textes ordinaires, organiques et de ratification (pas les résolutions, pas les lois constitutionnelles dont la suite
  n'est pas couverte par nos phrases sourcées) et les sorts clairs (adopté / rejeté) : « considéré comme adopté » (49.3) est ignoré.

Aucun résumé n'est généré : le titre est celui du dossier tel que l'Assemblée le publie. Pas d'horodatage dans le fichier : il ne change que
quand une décision apparaît ou sort de la fenêtre (sinon chaque passage de l'ingestion committerait pour rien).
"""
import http.client
import json
import re
import sys
import urllib.error
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import reseau

LEGISLATURE = 17
URL_DOSSIERS = f'https://data.assemblee-nationale.fr/static/openData/repository/{LEGISLATURE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip'
URL_PUBLIQUE = f'https://www.assemblee-nationale.fr/dyn/{LEGISLATURE}/dossiers/'
SORTIE = Path('data') / 'decisions_texte.json'
UA = 'Populous/1.0 (decisions; +https://maxboilot.github.io/populous/)'
DELAI = 180
JOURS = 20                                   # fenetre gardee dans le fichier (la publication n'en utilise que 3, le reste sert aux tests et au recoupement)

# procedureParlementaire.libelle -> (nature, organique, ratification) ; None = nature lue dans le texte associe (PRJL = projet, PION = proposition)
PROCEDURES = {
    'Proposition de loi ordinaire': ('proposition', False, False),
    'Projet de loi ordinaire': ('projet', False, False),
    'Projet de ratification des traités et conventions': ('projet', False, True),
    'Projet ou proposition de loi organique': (None, True, False),
}
# code de l'acte de lecture (1er niveau) -> lecture
LECTURES = {'AN1': 'premiere', 'AN2': 'deuxieme', 'ANNLEC': 'nouvelle', 'ANLDEF': 'definitive', 'CMP': 'cmp'}


def liste(valeur):
    """L'export JSON de l'Assemblée renvoie tantôt un objet, tantôt un tableau."""
    if valeur is None:
        return []
    return valeur if isinstance(valeur, list) else [valeur]


def sous_actes(acte):
    s = acte.get('actesLegislatifs')
    return liste(s.get('acteLegislatif')) if isinstance(s, dict) else []


def decisions_de(acte_haut):
    """Les actes « Décision » de l'Assemblée sous un acte de lecture de premier niveau."""
    for a in sous_actes(acte_haut):
        code = str(a.get('codeActe', ''))
        if code.endswith('DEBATS-DEC') and (code.startswith('AN') or code.startswith('CMP-DEBATS-AN')):
            yield a
        yield from decisions_de(a)


def sort_normalise(statut):
    """True (adopté, y compris avec modifications), False (rejeté), None (autre : à ignorer)."""
    s = (statut or '').strip().lower()
    if s.startswith('rejet'):
        return False
    if s.startswith('adopt') or s.startswith('modifi'):
        return True
    return None


def reference_scrutin(vote_refs):
    """Numéro du scrutin cité par la décision (VTANR5L17V8696 -> 8696), ou None."""
    for v in liste(vote_refs.get('voteRef') if isinstance(vote_refs, dict) else vote_refs):
        ref = v if isinstance(v, str) else (v or {}).get('voteRef')
        m = re.search(r'V(\d+)$', ref or '')
        if m:
            return int(m.group(1))
    return None


def decisions_du_dossier(d, depuis):
    """Les décisions retenues d'un dossier (dict `dossierParlementaire`), à partir de la date `depuis` (AAAA-MM-JJ)."""
    procedure = (d.get('procedureParlementaire') or {}).get('libelle')
    if procedure not in PROCEDURES:
        return []
    nature, organique, ratification = PROCEDURES[procedure]
    hauts = liste((d.get('actesLegislatifs') or {}).get('acteLegislatif'))
    premiere_assemblee = bool(hauts) and str(hauts[0].get('codeActe', '')).startswith('AN')
    titre = ((d.get('titreDossier') or {}).get('titre') or '').strip()
    sortie = []
    for haut in hauts:
        lecture = LECTURES.get(str(haut.get('codeActe', '')))
        if not lecture:
            continue
        for a in decisions_de(haut):
            date = (a.get('dateActe') or '')[:10]
            statut = a.get('statutConclusion')
            libelle = (statut.get('libelle') if isinstance(statut, dict) else statut) or ''
            adopte = sort_normalise(libelle)
            if not date or date < depuis or adopte is None or not titre:
                continue
            n = nature
            if n is None:                                  # loi organique : projet ou proposition ? -> prefixe du texte associe
                refs = [str(t.get('refTexteAssocie', '')) for t in liste((a.get('textesAssocies') or {}).get('texteAssocie'))]
                n = 'projet' if any(r.startswith('PRJL') for r in refs) else 'proposition'
            sortie.append({
                'id': a.get('uid') or f"{d['uid']}:{date}", 'dossier': d['uid'], 'titre': titre, 'nature': n, 'organique': organique, 'ratification': ratification,
                'date': date, 'lecture': lecture, 'statut': libelle, 'adopte': adopte, 'sans_modification': 'sans modification' in libelle.lower(),
                'premiere_assemblee': premiere_assemblee, 'vote_ref': reference_scrutin(a.get('voteRefs')), 'url': URL_PUBLIQUE + d['uid'],
            })
    return sortie


def construire(archive, depuis):
    """Toutes les décisions retenues de l'archive (BytesIO du zip), à partir de `depuis`, triées de la plus récente à la plus ancienne."""
    sortie = []
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            if '/dossierParlementaire/' not in '/' + nom or not nom.endswith('.json'):
                continue
            d = json.loads(z.read(nom))['dossierParlementaire']
            if str(d.get('legislature')) == str(LEGISLATURE):
                sortie += decisions_du_dossier(d, depuis)
    return sorted(sortie, key=lambda x: (x['date'], x['id']), reverse=True)


def main():
    depuis = (datetime.now(timezone.utc) - timedelta(days=JOURS)).strftime('%Y-%m-%d')
    try:
        decisions = construire(BytesIO(reseau.telecharger(URL_DOSSIERS, timeout=DELAI, headers={'User-Agent': UA})), depuis)
    except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as e:
        # L'open data de l'Assemblée est parfois indisponible : on garde le fichier de la veille plutôt que de faire planter l'ingestion.
        if SORTIE.exists():
            print(f'ATTENTION : decisions non mises a jour ({e}) ; decisions_texte.json precedent conserve.')
            return 0
        raise
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps({'decisions': decisions}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'decisions_texte.json : {len(decisions)} decisions depuis le {depuis} ({sum(1 for x in decisions if not x["vote_ref"])} sans reference de scrutin)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
