#!/usr/bin/env python3
"""Envoie une notification push aux telephones abonnes : iPhone via Apple
directement (APNs) — pas de SDK Firebase cote app iOS, cf. CLAUDE.md et
l'historique de conversation (le SDK Firebase bloquait la compilation
iOS) — et Android via l'API HTTP v1 de Firebase Cloud Messaging (FCM).
Firestore ne sert ici que de carnet d'adresses (la liste des jetons
enregistres par index.html au lancement de l'app, avec leur champ
`plateforme`, cf. initNotificationsPush) ; l'app elle-meme n'y lit
jamais rien.

Prerequis (secrets GitHub Actions) :
  APNS_KEY_ID          identifiant de la cle .p8 (Apple Developer > Certificates,
                        Identifiers & Profiles > Keys)
  APNS_TEAM_ID          identifiant d'equipe Apple Developer
  APNS_AUTH_KEY         contenu du fichier .p8 (la cle privee elle-meme)
  FIREBASE_PROJECT_ID   populous-66469
  FIREBASE_SERVICE_ACCOUNT  contenu JSON du compte de service Firebase
                        (Parametres du projet > Comptes de service >
                        Generer une nouvelle cle privee) — donne acces
                        en LECTURE a Firestore, jamais expose a l'app.

Aucun de ces secrets n'existe encore au moment ou ce script est ecrit :
le compte Apple Developer (payant) n'est pas encore cree. Le script est
pret, mais n'a pas pu etre teste contre le vrai serveur APNs — a
verifier avec un premier envoi manuel (--dry-run leve, puis un run reel)
une fois les secrets renseignes.

Usage :
    python notifier_push.py --titre "..." --texte "..." [--url https://...]
    python notifier_push.py --titre "..." --texte "..." --dry-run   # n'envoie rien, affiche juste qui recevrait quoi
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx
import jwt  # PyJWT

DOSSIER = Path(__file__).parent

# aps-environment de App.entitlements : 'development' tant que l'app
# n'est distribuee qu'en debug/simulateur. A passer a 'production' (et
# changer APNS_HOST ci-dessous) une fois de vraies builds TestFlight/App
# Store en circulation, signees avec un profil de distribution.
APNS_HOSTS = {
    'production': 'https://api.push.apple.com',
    'sandbox': 'https://api.sandbox.push.apple.com',
}
# Un jeton appartient a UN environnement : les builds App Store/TestFlight
# (entitlement production) et les builds Xcode sur iPhone (App/AppDebug.
# entitlements, development) n'ont pas les memes. On essaie donc la
# production d'abord, puis le bac a sable si Apple repond BadDeviceToken.
# APNS_HOST force un seul hote si besoin.
APNS_HOST_FORCE = os.environ.get('APNS_HOST')
APNS_BUNDLE_ID = 'com.populous.app'


def jeton_apns(key_id, team_id, cle_privee_pem):
    """JWT provider APNs (ES256), valable jusqu'a 1h — cf. doc Apple."""
    maintenant = int(time.time())
    return jwt.encode(
        {'iss': team_id, 'iat': maintenant},
        cle_privee_pem,
        algorithm='ES256',
        headers={'kid': key_id},
    )


SCOPE_FIRESTORE = 'https://www.googleapis.com/auth/datastore'
SCOPE_FCM = 'https://www.googleapis.com/auth/firebase.messaging'


def jeton_acces_google(compte_service, scope=SCOPE_FIRESTORE):
    """Echange le compte de service Firebase contre un jeton d'acces
    OAuth2 (Firestore par defaut, FCM avec SCOPE_FCM), via le flux
    JWT-bearer standard de Google — pas de dependance au SDK google-cloud."""
    maintenant = int(time.time())
    assertion = jwt.encode(
        {
            'iss': compte_service['client_email'],
            'scope': scope,
            'aud': 'https://oauth2.googleapis.com/token',
            'iat': maintenant,
            'exp': maintenant + 3600,
        },
        compte_service['private_key'],
        algorithm='RS256',
    )
    r = httpx.post('https://oauth2.googleapis.com/token', data={
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': assertion,
    }, timeout=20)
    r.raise_for_status()
    return r.json()['access_token']


def jetons_abonnes(project_id, jeton_acces):
    """Liste tous les jetons enregistres dans Firestore (collection
    pushTokens, ecrite par initNotificationsPush dans index.html), sous
    forme de (jeton, plateforme). Les anciens documents sans `plateforme`
    sont des iPhone."""
    url = f'https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/pushTokens'
    entetes = {'Authorization': f'Bearer {jeton_acces}'}
    jetons = []
    page_token = None
    while True:
        params = {'pageToken': page_token} if page_token else {}
        r = httpx.get(url, headers=entetes, params=params, timeout=20)
        r.raise_for_status()
        page = r.json()
        for doc in page.get('documents', []):
            valeur = doc.get('fields', {}).get('token', {}).get('stringValue')
            plateforme = doc.get('fields', {}).get('plateforme', {}).get('stringValue') or 'ios'
            if valeur:
                jetons.append((valeur, plateforme))
        page_token = page.get('nextPageToken')
        if not page_token:
            break
    # Dedoublonnage : l'app enregistrait son jeton a CHAQUE lancement (une
    # ligne de plus a chaque fois) — sans ceci, un meme iPhone recevait
    # autant de bannieres identiques que de lancements.
    return list(dict.fromkeys(jetons))


def envoyer_une_android(device_token, titre, texte, url_cible, project_id, jeton_fcm, cible=None):
    """Une notification FCM (API HTTP v1). Message de type `notification` :
    Android l'affiche lui-meme quand l'app est fermee ou en arriere-plan,
    et au toucher, `data` est remise a l'app (pushNotificationActionPerformed,
    index.html), comme `cible` cote iOS."""
    donnees = {}
    if url_cible:
        donnees['url'] = url_cible
    if cible:
        donnees['cible'] = cible
    message = {
        'token': device_token,
        'notification': {'title': titre, 'body': texte},
        'android': {'priority': 'HIGH'},
    }
    if donnees:
        message['data'] = donnees
    return httpx.post(
        f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send',
        headers={'Authorization': f'Bearer {jeton_fcm}'},
        json={'message': message},
        timeout=20,
    )


def envoyer_une(device_token, titre, texte, url_cible, apns_jwt, cible=None):
    entetes = {
        'authorization': f'bearer {apns_jwt}',
        'apns-topic': APNS_BUNDLE_ID,
        'apns-push-type': 'alert',
        'apns-priority': '10',
    }
    charge = {
        # badge 1 : pastille rouge sur l'icone, remise a zero par l'app a son
        # ouverture (AppDelegate.applicationDidBecomeActive).
        'aps': {'alert': {'title': titre, 'body': texte}, 'sound': 'default', 'badge': 1},
    }
    if url_cible:
        charge['url'] = url_cible
    if cible:
        # Lue par l'app au toucher (pushNotificationActionPerformed, index.html).
        charge['cible'] = cible
    hotes = [APNS_HOST_FORCE] if APNS_HOST_FORCE else [APNS_HOSTS['production'], APNS_HOSTS['sandbox']]
    with httpx.Client(http2=True) as client:
        for hote in hotes:
            r = client.post(
                f'{hote}/3/device/{device_token}',
                headers=entetes,
                content=json.dumps(charge),
                timeout=20,
            )
            if r.status_code != 400 or 'BadDeviceToken' not in r.text:
                return r
        return r


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--titre', required=True)
    parser.add_argument('--texte', required=True)
    parser.add_argument('--url', default=None, help="Deep link optionnel ouvert au tap de la notif.")
    parser.add_argument('--cible', default=None, choices=['refjour', 'avenir', 'carte', 'presidentielle'],
                        help="Ecran ouvert par l'app au toucher de la notification.")
    parser.add_argument('--dry-run', action='store_true', help="N'envoie rien, affiche juste qui recevrait quoi.")
    args = parser.parse_args()

    compte_service = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT'])
    project_id = os.environ.get('FIREBASE_PROJECT_ID', 'populous-66469')
    jeton_acces = jeton_acces_google(compte_service)
    jetons = jetons_abonnes(project_id, jeton_acces)
    ios = [j for j, plateforme in jetons if plateforme != 'android']
    android = [j for j, plateforme in jetons if plateforme == 'android']
    print(f'{len(jetons)} appareil(s) abonne(s) : {len(ios)} iPhone, {len(android)} Android.')

    if args.dry_run:
        print(f'[dry-run] enverrait "{args.titre}" / "{args.texte}" a {len(jetons)} appareil(s).')
        return

    envoyees = 0
    echecs = 0
    if ios:
        apns = jeton_apns(os.environ['APNS_KEY_ID'], os.environ['APNS_TEAM_ID'], os.environ['APNS_AUTH_KEY'])
        for device_token in ios:
            r = envoyer_une(device_token, args.titre, args.texte, args.url, apns, args.cible)
            if r.status_code == 200:
                envoyees += 1
            else:
                echecs += 1
                print(f'  echec iPhone {device_token[:12]}... : {r.status_code} {r.text}')
    if android:
        # Un echec Android ne doit jamais empecher/annuler l'envoi iPhone
        # (deja parti ci-dessus) : on le journalise et on continue.
        try:
            jeton_fcm = jeton_acces_google(compte_service, SCOPE_FCM)
        except Exception as e:
            echecs += len(android)
            print(f'  echec Android : jeton FCM impossible ({e})')
        else:
            for device_token in android:
                r = envoyer_une_android(device_token, args.titre, args.texte, args.url, project_id, jeton_fcm, args.cible)
                if r.status_code == 200:
                    envoyees += 1
                else:
                    echecs += 1
                    print(f'  echec Android {device_token[:12]}... : {r.status_code} {r.text}')
    print(f'{envoyees}/{len(jetons)} notifications envoyees.')


if __name__ == '__main__':
    main()
