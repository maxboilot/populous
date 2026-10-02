#!/usr/bin/env python3
"""Construit data/detail_jour.json : tous les scrutins du dernier jour de
vote, ranges par texte de loi, puis par article, puis par modification
(amendement, avec ses sous-amendements). Alimente la fenetre « Detail » de
l'app, qui explique comment une loi se vote et ce qui s'est passe ce jour-la.

Rien n'est invente : chaque ligne est un scrutin reel (numero, libelle
officiel, resultat, decompte). Le rangement vient du decoupage du libelle
(structure_scrutins.py) ; ce qui n'y est pas reconnu reste affiche tel quel
dans « autres », jamais devine.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import structure_scrutins as S

DATA_DIR = Path('data')
SCRUTINS_DIR = DATA_DIR / 'scrutins'
FENETRE = 400  # on ne relit que les scrutins proches du dernier numero vedette


def issue(sort):
    s = (sort or '').lower()
    if 'pas adopt' in s:
        return 'rejete'
    return 'adopte' if 'adopt' in s else None


def fiche(sc):
    t = sc['titre']
    tally = sc.get('tally') or {}
    pour, contre, abst = tally.get('pour', 0), tally.get('contre', 0), tally.get('abstention', 0)
    return {
        'numero': sc['numero'],
        'nature': S.nature(t),
        'article': S.article_ref(t),
        'n_amendement': S.numero_amendement(t),
        'parent': S.amendement_parent(t),
        'auteur': S.auteur(t),
        'issue': issue(sc.get('sort')),
        'pour': pour, 'contre': contre, 'abstentions': abst,
        'votants': pour + contre + abst,
        'solennel': bool(sc.get('solennel')),
        'objet': t,
        'source': sc.get('source'),
    }


def construire(scrutins, numero_vedette=None):
    """scrutins : fiches data/scrutins/*.json d'une meme date."""
    scrutins = sorted(scrutins, key=lambda sc: sc['numero'])
    lois, autres = {}, []
    for sc in scrutins:
        f = fiche(sc)
        f['vedette'] = (sc['numero'] == numero_vedette)
        cle = S.cle_loi(sc['titre'])
        if cle is None:
            autres.append(f)
            continue
        if cle not in lois:
            nature_texte, intitule, lecture = S.texte_de_loi(sc['titre'])
            lois[cle] = {'nature_texte': nature_texte, 'intitule': intitule, 'lecture': lecture,
                         'ensemble': None, 'articles': {}, 'motions': []}
        loi = lois[cle]
        if f['nature'] == 'ensemble':
            loi['ensemble'] = f
        elif f['nature'] == 'motion':
            loi['motions'].append(f)
        else:
            ref = f['article'] or '?'
            art = loi['articles'].setdefault(ref, {'ref': ref, 'article': None, 'modifications': []})
            if f['nature'] == 'article':
                art['article'] = f
            else:
                art['modifications'].append(f)

    sortie = []
    for loi in lois.values():
        articles = []
        for art in loi['articles'].values():
            modifs = art['modifications']
            par_n = {m['n_amendement']: m for m in modifs if m['nature'] == 'amendement'}
            racines = []
            for m in modifs:
                m['sous_amendements'] = []
            for m in modifs:
                if m['nature'] == 'sous-amendement' and m['parent'] in par_n:
                    par_n[m['parent']]['sous_amendements'].append(m)
                else:
                    racines.append(m)
            articles.append({'ref': art['ref'], 'article': art['article'], 'modifications': racines})
        sortie.append({**{k: loi[k] for k in ('nature_texte', 'intitule', 'lecture', 'ensemble', 'motions')},
                       'articles': articles})
    return {'lois': sortie, 'autres': autres}


def main():
    today = json.loads((DATA_DIR / 'today.json').read_text(encoding='utf-8'))
    numero = today.get('featured_numero') or today.get('last_featured_numero')
    date = today.get('last_featured_date')
    if not numero or not date:
        print('detail_jour.json : aucun scrutin vedette connu, rien a faire.')
        return
    du_jour = []
    for n in range(int(numero) - FENETRE, int(numero) + FENETRE):
        chemin = SCRUTINS_DIR / f'{n}.json'
        if chemin.exists():
            sc = json.loads(chemin.read_text(encoding='utf-8'))
            if sc.get('date') == date:
                du_jour.append(sc)
    charge = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'date': date,
        'numero_vedette': int(numero),
        **construire(du_jour, int(numero)),
    }
    (DATA_DIR / 'detail_jour.json').write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"detail_jour.json : {len(du_jour)} scrutins du {date}, {len(charge['lois'])} texte(s) de loi.")


if __name__ == '__main__':
    main()
