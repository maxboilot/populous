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
seuls : une erreur HTTP 5xx (problème temporaire côté serveur) ou une
erreur réseau (coupure, timeout). Une erreur 4xx (ex. 404) est
définitive — la retenter n'aurait aucun sens, donc pas de nouvel essai.
"""
import ssl
import time
import urllib.error
import urllib.request

TENTATIVES = 3
DELAI_BASE = 4  # secondes ; doublé-ish à chaque nouvel essai (x essai)


def telecharger(url, *, timeout, headers, tentatives=TENTATIVES):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers)
    for essai in range(1, tentatives + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or essai == tentatives:
                raise
            erreur = e
        except (urllib.error.URLError, TimeoutError) as e:
            if essai == tentatives:
                raise
            erreur = e
        attente = DELAI_BASE * essai
        print(f'  {url} : {erreur} (tentative {essai}/{tentatives}), nouvel essai dans {attente}s')
        time.sleep(attente)
