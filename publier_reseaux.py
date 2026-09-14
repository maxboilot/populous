#!/usr/bin/env python3
"""Publie un post sur la Page Facebook « Media Populous » et sur le
compte Instagram @populous_officiel, avec un visuel genere a la volee.

Contenu (jamais invente, cf. CLAUDE.md) : cinq types, choisis avec
--type sur la ligne de commande pour que chaque creneau cron sache
exactement ce qu'il poste plutot que de tirer au hasard :
  - fait        : le fait du jour deja curate dans data/refs_jour.json
  - presidentiel: le dernier sondage 2027 deja recupere (et source) dans
                  data/sondages.json
  - depute      : un depute tire au hasard dans elus.json, avec son
                  portrait officiel (meme atlas que index.html)
  - avenir      : les 3 prochains points a l'ordre du jour de
                  l'Assemblee, deja recuperes dans data/agenda.json
  - boussole    : accroche fixe invitant a tester la boussole politique
                  de l'app (texte relu une fois pour toutes, jamais
                  genere a la demande)

Par defaut le script tourne en mode "brouillon" : il genere le visuel
et affiche la legende sans rien publier. Il faut explicitement passer
--publier pour que la publication ait lieu (choix deliberer : ne
jamais publier en public sans qu'un humain ait vu le rendu au moins
une fois pour ce point d'entree).

Comment Instagram recoit son image : l'API Content Publishing exige une
URL publique (pas d'upload binaire direct). On publie d'abord la photo
sur la Page Facebook (ce qu'on veut de toute facon), ce qui renvoie une
URL CDN publique pour cette image ; on la reutilise ensuite comme
image_url pour Instagram. Ca evite de dependre de git/GitHub Pages pour
heberger des images ephemeres — cf. CLAUDE.md, jamais de push sans
validation explicite, ce que ferait un cron non surveille.
"""
import argparse
import datetime
import json
import os
import random
import sys
from pathlib import Path

import requests

from generer_visuel import generer, portrait_depute

DOSSIER = Path(__file__).parent
GRAPH = 'https://graph.facebook.com/v21.0'


def lire_env():
    """Cle -> valeur pour FB_PAGE_ID / FB_PAGE_TOKEN / IG_USER_ID.

    En local : fichier .env (jamais commite, cf. .gitignore). Sur
    GitHub Actions : pas de .env dans le depot (memes secrets, mais
    exposes en variables d'environnement par le workflow) — on y
    retombe si le fichier n'existe pas, plutot que d'exiger deux
    facons differentes de renseigner les identifiants."""
    chemin = DOSSIER / '.env'
    if not chemin.exists():
        return {cle: os.environ[cle] for cle in ('FB_PAGE_ID', 'FB_PAGE_TOKEN', 'IG_USER_ID') if cle in os.environ}
    valeurs = {}
    for ligne in chemin.read_text(encoding='utf-8').splitlines():
        if '=' in ligne and not ligne.startswith('#'):
            cle, _, valeur = ligne.partition('=')
            valeurs[cle.strip()] = valeur.strip()
    return valeurs


def contenu_fait_du_jour():
    d = json.loads((DOSSIER / 'data' / 'refs_jour.json').read_text(encoding='utf-8'))
    cle = datetime.date.today().strftime('%m-%d')
    refs = d['refs'].get(cle) or []
    if not refs:
        return None
    ref = refs[0]
    titre = f"{ref['annee']} : {ref['titre']}" if ref.get('titre') else ref['texte'][:80]
    return {
        'eyebrow': 'Fait du jour',
        'titre': titre,
        'texte': ref['texte'],
        'legende': f"{titre}\n\n{ref['texte']}\n\n#Populous #HistoirePolitique #AssembleeNationale",
    }


def contenu_presidentielle():
    d = json.loads((DOSSIER / 'data' / 'sondages.json').read_text(encoding='utf-8'))
    dernier = max(d['sondages'], key=lambda s: s['date'])
    noms = {c['cle']: c['nom'] for c in d['candidats']}
    classement = sorted(dernier['scores'].items(), key=lambda kv: -kv[1])[:3]
    tete = classement[0]
    date_fr = datetime.date.fromisoformat(dernier['date']).strftime('%d/%m/%Y')
    detail = ' · '.join(f"{noms.get(cle, cle)} {score:.0f}%" for cle, score in classement)
    return {
        'eyebrow': 'Actu presidentielle 2027',
        'titre': f"{noms.get(tete[0], tete[0])} en tete a {tete[1]:.0f}%",
        'texte': f"Sondage {dernier['institut']} du {date_fr} ({dernier['echantillon']} personnes) : {detail}.",
        'legende': (
            f"Presidentielle 2027 — sondage {dernier['institut']} du {date_fr}\n\n{detail}\n\n"
            f"Source : {dernier['source']}\n\n#Populous #Presidentielle2027 #Sondage"
        ),
    }


def contenu_depute():
    elus = json.loads((DOSSIER / 'elus.json').read_text(encoding='utf-8'))['elus']
    elu = random.choice(elus)
    detail = f"{elu['gn']} · {elu['vn']} · {elu['pro']}"
    return {
        'eyebrow': 'Depute du jour',
        'titre': elu['n'],
        'texte': detail,
        'legende': (
            f"{elu['n']} ({elu['g']})\n\n{elu['gn']}\nCirconscription de {elu['vn']}\nProfession : {elu['pro']}\n\n"
            f"Retrouve son activite complete a l'Assemblee sur Populous.\n\n#Populous #AssembleeNationale #{elu['g']}"
        ),
        'a_index': elu['a'],
    }


def contenu_avenir():
    agenda = json.loads((DOSSIER / 'data' / 'agenda.json').read_text(encoding='utf-8'))
    aujourdhui = datetime.date.today().isoformat()
    a_venir = sorted((a for a in agenda if a['date'] >= aujourdhui), key=lambda a: (a['date'], a['heure']))[:3]
    if not a_venir:
        return None
    lignes = []
    for item in a_venir:
        date_fr = datetime.date.fromisoformat(item['date']).strftime('%d/%m')
        sujet = item['ordre_du_jour'].split('—', 1)[-1].strip()
        lignes.append(f"{date_fr} : {sujet}")
    return {
        'eyebrow': 'A venir',
        'titre': "Cette semaine à l'Assemblée",
        'texte': '  •  '.join(lignes),
        'legende': "Cette semaine a l'Assemblee nationale :\n\n" + '\n'.join(f"- {l}" for l in lignes)
        + "\n\nSuis chaque vote en direct sur Populous.\n\n#Populous #AssembleeNationale",
    }


def contenu_boussole():
    return {
        'eyebrow': 'Boussole politique',
        'titre': 'Compare tes opinions aux votes reels de tes elus',
        'texte': "Reponds a quelques questions et decouvre quel groupe politique vote le plus comme toi.",
        'legende': (
            "Ta boussole politique : compare tes opinions aux votes reels de tes elus, "
            "sans jugement ni etiquette imposee.\n\nTeste la boussole sur Populous.\n\n#Populous #BoussolePolitique"
        ),
    }


CHOIX = {
    'fait': contenu_fait_du_jour,
    'presidentiel': contenu_presidentielle,
    'depute': contenu_depute,
    'avenir': contenu_avenir,
    'boussole': contenu_boussole,
}


def publier_photo_facebook(page_id, page_token, chemin_image, legende):
    with open(chemin_image, 'rb') as f:
        r = requests.post(
            f'{GRAPH}/{page_id}/photos',
            data={'caption': legende, 'access_token': page_token},
            files={'source': f},
            timeout=30,
        )
    r.raise_for_status()
    return r.json()  # {'id': photo_id, 'post_id': page_id_postid}


def url_publique_photo(photo_id, token):
    r = requests.get(f'{GRAPH}/{photo_id}', params={'fields': 'images', 'access_token': token}, timeout=20)
    r.raise_for_status()
    images = r.json().get('images', [])
    if not images:
        raise RuntimeError("Aucune URL publique retournee pour la photo.")
    return images[0]['source']  # la plus grande resolution en premier


def publier_instagram(ig_user_id, page_token, image_url, legende):
    r = requests.post(
        f'{GRAPH}/{ig_user_id}/media',
        data={'image_url': image_url, 'caption': legende, 'access_token': page_token},
        timeout=30,
    )
    r.raise_for_status()
    creation_id = r.json()['id']
    r = requests.post(
        f'{GRAPH}/{ig_user_id}/media_publish',
        data={'creation_id': creation_id, 'access_token': page_token},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--type', choices=CHOIX.keys(), required=True)
    parser.add_argument('--publier', action='store_true', help="Publie reellement (sinon : brouillon local seulement).")
    args = parser.parse_args()

    contenu = CHOIX[args.type]()
    if contenu is None:
        print(f"Rien a publier pour --type {args.type} aujourd'hui.")
        return

    chemin_image = DOSSIER / 'assets_social' / f'{datetime.date.today().isoformat()}-{args.type}.png'
    photo = portrait_depute(contenu['a_index']) if 'a_index' in contenu else None
    generer(chemin_image, eyebrow=contenu['eyebrow'], titre=contenu['titre'], texte=contenu.get('texte'), photo=photo)

    print(f"Visuel : {chemin_image}")
    print(f"Legende :\n{contenu['legende']}\n")

    if not args.publier:
        print("Mode brouillon (--publier non passe) : rien n'a ete publie.")
        return

    env = lire_env()
    page_id, page_token, ig_user_id = env['FB_PAGE_ID'], env['FB_PAGE_TOKEN'], env['IG_USER_ID']

    reponse_fb = publier_photo_facebook(page_id, page_token, chemin_image, contenu['legende'])
    print(f"Facebook publie : {reponse_fb}")

    url_image = url_publique_photo(reponse_fb['id'], page_token)
    reponse_ig = publier_instagram(ig_user_id, page_token, url_image, contenu['legende'])
    print(f"Instagram publie : {reponse_ig}")


if __name__ == '__main__':
    sys.exit(main())
