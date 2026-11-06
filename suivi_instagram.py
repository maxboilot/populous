#!/usr/bin/env python3
"""Suivi d'@populous_officiel : un instantane par jour (abonnes + performance de chaque post), conserve dans data/suivi_instagram.json,
et un bilan lisible. LECTURE SEULE : aucune publication, aucun envoi. Les chiffres viennent de l'API Instagram (Meta).

Usage :
  python3 suivi_instagram.py              # enregistre l'instantane du jour
  python3 suivi_instagram.py --bilan      # bilan des 7 derniers jours (sans appeler l'API)
Identifiants : .env en local (FB_PAGE_TOKEN, IG_USER_ID) ou variables d'environnement (GitHub Actions)."""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

DOSSIER = Path(__file__).parent
FICHIER = DOSSIER / 'data' / 'suivi_instagram.json'
GRAPH = 'https://graph.facebook.com/v21.0'
METRIQUES = {   # par type de media ; une metrique refusee par l'API est simplement ignoree
    'CAROUSEL_ALBUM': 'reach,saved,shares,total_interactions',
    'VIDEO': 'reach,saved,shares,total_interactions,plays',
    'REELS': 'reach,saved,shares,total_interactions,plays',
    'IMAGE': 'reach,saved,shares,total_interactions',
}


def lire_env():
    chemin = DOSSIER / '.env'
    valeurs = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding='utf-8').splitlines():
            if '=' in ligne and not ligne.startswith('#'):
                cle, _, val = ligne.partition('=')
                valeurs[cle.strip()] = val.strip()
    for cle in ('FB_PAGE_TOKEN', 'IG_USER_ID'):
        valeurs.setdefault(cle, os.environ.get(cle, ''))
    if not valeurs['FB_PAGE_TOKEN'] or not valeurs['IG_USER_ID']:
        sys.exit("FB_PAGE_TOKEN et IG_USER_ID sont necessaires (.env ou variables d'environnement).")
    return valeurs


def _get(requests, chemin, token, **params):
    r = requests.get(f'{GRAPH}/{chemin}', params={**params, 'access_token': token}, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def instantane():
    import requests
    env = lire_env(); token, ig = env['FB_PAGE_TOKEN'], env['IG_USER_ID']
    compte = _get(requests, ig, token, fields='username,followers_count,follows_count,media_count')
    if compte is None:
        sys.exit("Instagram : lecture du compte impossible (jeton expire ?).")
    medias = (_get(requests, f'{ig}/media', token, fields='id,timestamp,media_type,media_product_type,like_count,comments_count,permalink,caption', limit=30) or {}).get('data', [])
    posts = []
    for m in medias:
        genre = 'REELS' if m.get('media_product_type') == 'REELS' else m['media_type']
        ins = {}
        for metrique in METRIQUES.get(genre, 'reach').split(','):          # une par une : si l'une est refusee, les autres restent
            d = _get(requests, f"{m['id']}/insights", token, metric=metrique)
            if d and d.get('data'):
                ins[metrique] = d['data'][0]['values'][0]['value']
        posts.append({'id': m['id'], 'date': m['timestamp'][:10], 'type': genre, 'jaime': m.get('like_count'), 'commentaires': m.get('comments_count'),
                      'portee': ins.get('reach'), 'enregistrements': ins.get('saved'), 'partages': ins.get('shares'), 'lectures': ins.get('plays'),
                      'debut_legende': (m.get('caption') or '').split('\n')[0][:70], 'lien': m.get('permalink')})
    return {'abonnes': compte['followers_count'], 'abonnements': compte['follows_count'], 'publications': compte['media_count'], 'posts': posts}


def enregistrer():
    histo = json.loads(FICHIER.read_text(encoding='utf-8')) if FICHIER.exists() else {}
    jour = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    histo[jour] = instantane()
    FICHIER.write_text(json.dumps(histo, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    s = histo[jour]
    print(f"{jour} : {s['abonnes']} abonnés, {s['publications']} publications, {len(s['posts'])} posts relevés -> {FICHIER.name}")


def bilan():
    if not FICHIER.exists():
        sys.exit("Aucun instantané : lancer d'abord `python3 suivi_instagram.py`.")
    histo = json.loads(FICHIER.read_text(encoding='utf-8')); jours = sorted(histo)
    fin = jours[-1]; debut = next((j for j in jours if j >= (datetime.date.fromisoformat(fin) - datetime.timedelta(days=7)).isoformat()), jours[0])
    a, b = histo[debut], histo[fin]
    print(f"Bilan {debut} -> {fin}")
    print(f"Abonnés : {a['abonnes']} -> {b['abonnes']} ({b['abonnes'] - a['abonnes']:+d})  |  abonnements : {b['abonnements']}")
    recents = [p for p in b['posts'] if p['date'] >= debut]
    print(f"Publications sur la période : {len(recents)}")
    par_type = {}
    for p in recents:
        par_type.setdefault(p['type'], []).append(p)
    for t, ps in sorted(par_type.items()):
        moy = lambda k: (sum((p.get(k) or 0) for p in ps) / len(ps))
        print(f"  {t:<15} {len(ps):>2} posts · portée moy. {moy('portee'):.0f} · j'aime moy. {moy('jaime'):.1f} · comm. moy. {moy('commentaires'):.1f} · enreg. moy. {moy('enregistrements'):.1f} · partages moy. {moy('partages'):.1f}")
    print("Meilleurs posts (portée, sinon j'aime + commentaires) :")
    for p in sorted(recents, key=lambda p: (p.get('portee') or 0, (p.get('jaime') or 0) + (p.get('commentaires') or 0)), reverse=True)[:5]:
        print(f"  {p['date']} {p['type']:<15} portée {p.get('portee')} · j'aime {p.get('jaime')} · comm. {p.get('commentaires')} · {p['debut_legende']}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bilan', action='store_true', help="bilan des 7 derniers jours (lit data/suivi_instagram.json)")
    a = ap.parse_args()
    bilan() if a.bilan else enregistrer()
