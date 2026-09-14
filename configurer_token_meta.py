#!/usr/bin/env python3
"""Echange le token utilisateur court terme (copie depuis le Graph API
Explorer, colle dans le presse-papier) contre les identifiants longue
duree dont le pipeline de publication a besoin, et les ecrit dans .env.

Pourquoi par le presse-papier plutot qu'un argument en ligne de commande
ou un copier-coller dans le chat : un token d'acces est un secret au
meme titre qu'un mot de passe. Le lire depuis le presse-papier local
evite qu'il transite par un historique de shell, un log, ou la
conversation avec l'assistant.

Usage :
  1. Dans le Graph API Explorer (developers.facebook.com/tools/explorer),
     app "Populous Social", generer un token avec les autorisations
     pages_show_list, pages_read_engagement, pages_manage_posts,
     business_management, instagram_basic, instagram_content_publish.
  2. Cliquer "Copy Token".
  3. Lancer : python3 configurer_token_meta.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse

import reseau

GRAPH = 'https://graph.facebook.com/v21.0'
UA = 'Populous/1.0 (configurer-token-meta)'


def lire_env(chemin):
    valeurs = {}
    if os.path.exists(chemin):
        for ligne in open(chemin, encoding='utf-8'):
            ligne = ligne.strip()
            if not ligne or ligne.startswith('#') or '=' not in ligne:
                continue
            cle, _, valeur = ligne.partition('=')
            valeurs[cle.strip()] = valeur.strip()
    return valeurs


def ecrire_env(chemin, valeurs):
    lignes = [f'{cle}={valeur}' for cle, valeur in valeurs.items()]
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lignes) + '\n')


def main():
    chemin_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    env = lire_env(chemin_env)

    app_id = env.get('FB_APP_ID')
    app_secret = env.get('FB_APP_SECRET')
    if not app_id or not app_secret:
        print("FB_APP_ID / FB_APP_SECRET manquants dans .env", file=sys.stderr)
        sys.exit(1)

    token_court = subprocess.run(['pbpaste'], capture_output=True, text=True, check=True).stdout.strip()
    if not token_court or len(token_court) < 20:
        print("Presse-papier vide ou invalide : clique d'abord \"Copy Token\" dans le Graph API Explorer.", file=sys.stderr)
        sys.exit(1)
    print(f"  Token lu dans le presse-papier : {len(token_court)} caracteres, commence par \"{token_court[:8]}\", finit par \"{token_court[-6:]}\".")

    print("Echange du token court terme contre un token longue duree...")
    params = urllib.parse.urlencode({
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': token_court,
    })
    try:
        reponse = json.loads(reseau.telecharger(f'{GRAPH}/oauth/access_token?{params}', timeout=20, headers={'User-Agent': UA}))
    except urllib.error.HTTPError as e:
        corps = e.read().decode('utf-8', errors='replace')
        print(f"Echec de l'echange ({e.code}) : {corps}", file=sys.stderr)
        sys.exit(1)
    token_long = reponse['access_token']
    print(f"  Token utilisateur longue duree obtenu (se termine par ...{token_long[-6:]}).")

    print("Recuperation de la Page et du compte Instagram lies...")
    params = urllib.parse.urlencode({
        'fields': 'id,name,access_token,instagram_business_account{id,username}',
        'access_token': token_long,
    })
    reponse = json.loads(reseau.telecharger(f'{GRAPH}/me/accounts?{params}', timeout=20, headers={'User-Agent': UA}))
    pages = reponse.get('data', [])
    page = next((p for p in pages if p.get('name') == 'Media Populous'), pages[0] if pages else None)
    if not page:
        print("Aucune Page trouvee pour ce compte.", file=sys.stderr)
        sys.exit(1)

    ig = page.get('instagram_business_account') or {}
    if not ig.get('id'):
        print(f"Attention : la Page \"{page['name']}\" n'a pas de compte Instagram associe.", file=sys.stderr)

    env['FB_USER_TOKEN_LONG'] = token_long
    env['FB_PAGE_ID'] = page['id']
    env['FB_PAGE_TOKEN'] = page['access_token']
    if ig.get('id'):
        env['IG_USER_ID'] = ig['id']
    ecrire_env(chemin_env, env)

    print(f"  Page : {page['name']} ({page['id']})")
    if ig.get('id'):
        print(f"  Instagram : @{ig.get('username')} ({ig['id']})")
    print(f"Ecrit dans {chemin_env}.")
    print("\nLe token Page ne s'affiche jamais ici — verifie dans .env que FB_PAGE_TOKEN est bien renseigne.")


if __name__ == '__main__':
    main()
