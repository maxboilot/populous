#!/usr/bin/env python3
"""Téléchargement partagé par les scripts du pipeline, avec nouvelles
tentatives en cas d'échec temporaire.

Pourquoi ce module existe : le 9 septembre 2026, construire_agenda.py a
échoué en HTTP 503 "Backend fetch failed" en interrogeant l'open data de
l'Assemblée nationale — un simple aléa côté serveur, pas un vrai
problème, mais qui faisait planter tout le run (et donc perdre la mise
à jour du jour) faute de deuxième essai. Les autres scripts du pipeline
téléchargent les mêmes sources et sont exposés au même risque.

On ne retente que les échecs qui ont une chance de se résoudre tout
seuls : une erreur HTTP 5xx (problème temporaire côté serveur), une
erreur réseau (coupure, timeout), ou une erreur de protocole HTTP en
cours de lecture de la réponse (ex. IncompleteRead — le serveur coupe
la connexion avant d'avoir envoyé tout le corps annoncé ; constaté
plusieurs fois sur construire_agenda.py, même symptôme que les
coupures gérées ci-dessus mais une exception différente, non
capturée jusqu'ici car levée par r.read(), après le retour de
urlopen()). Une erreur 4xx (ex. 404) est définitive — la retenter
n'aurait aucun sens, donc pas de nouvel essai.

Le magasin de certificats par défaut du système peut être incomplet
selon l'environnement (constaté le 14 septembre 2026 : SSL
CERTIFICATE_VERIFY_FAILED sur assemblee-nationale.fr avec le contexte
SSL par défaut, alors que le paquet certifi — déjà présent, installé
avec "requests" — valide le même certificat sans problème). On
utilise donc son magasin quand il est disponible, sans que ce soit une
condition bloquante ailleurs.
"""
import http.client
import ssl
import time
import urllib.error
import urllib.request

try:
    import certifi
    _CAFILE = certifi.where()
except ImportError:
    _CAFILE = None

TENTATIVES = 3
DELAI_BASE = 4  # secondes ; doublé-ish à chaque nouvel essai (x essai)


def telecharger(url, *, timeout, headers, tentatives=TENTATIVES):
    ctx = ssl.create_default_context(cafile=_CAFILE) if _CAFILE else ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers)
    for essai in range(1, tentatives + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or essai == tentatives:
                raise
            erreur = e
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as e:
            if essai == tentatives:
                raise
            erreur = e
        attente = DELAI_BASE * essai
        print(f'  {url} : {erreur} (tentative {essai}/{tentatives}), nouvel essai dans {attente}s')
        time.sleep(attente)
