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
                  (planifie 1x/semaine, cf. publier_reseaux.yml)
  - boussole    : accroche fixe invitant a tester la boussole politique
                  de l'app (texte relu une fois pour toutes, jamais
                  genere a la demande) — planifie 1x/mois (le 15), pour
                  ne pas repeter un visuel quasi identique chaque jour

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
import time
from pathlib import Path

import requests

from generer_visuel import generer, portrait_depute, pile_boussole_exemple

DOSSIER = Path(__file__).parent
GRAPH = 'https://graph.facebook.com/v21.0'

MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
           'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

# Memes tables que index.html (DEP_NAMES, VOTE_COLORS, POS_LABEL) : dupliquees
# ici pour que le bloc « depute du jour » du visuel reprenne exactement la
# meme information que la fiche depute de l'app, jusqu'au dernier vote connu.
DEP_NAMES = {"01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence", "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes", "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente", "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud", "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura", "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne", "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort", "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise", "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "975": "Saint-Pierre-et-Miquelon", "976": "Mayotte", "977": "Saint-Barthélemy / Saint-Martin", "986": "Wallis-et-Futuna", "987": "Polynésie française", "988": "Nouvelle-Calédonie", "099": "Français de l'étranger"}
VOTE_COLORS = {'pour': (27, 138, 107), 'contre': (196, 80, 28), 'abstention': (124, 140, 196), 'absent': (58, 68, 112)}
POS_LABEL = {'pour': "A voté pour", 'contre': "A voté contre", 'abstention': "S'est abstenu·e", 'absent': "Absent·e lors du vote"}


def _norm_pos(p):
    return 'absent' if p in (None, 'non_votant') else p


def _hex_vers_rgb(hexcode):
    h = hexcode.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


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
    mois, jour = cle.split('-')
    date_badge = f"{int(jour)} {MOIS_FR[int(mois) - 1]} {ref['annee']}"
    return {
        'eyebrow': 'Fait du jour',
        'titre': titre,
        'texte': ref['texte'],
        'date_badge': date_badge,
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
        'eyebrow': 'Actu présidentielle 2027',
        'titre': f"{noms.get(tete[0], tete[0])} en tête à {tete[1]:.0f}%",
        'texte': f"Sondage {dernier['institut']} du {date_fr} ({dernier['echantillon']} personnes) : {detail}.",
        'legende': (
            f"Présidentielle 2027 — sondage {dernier['institut']} du {date_fr}\n\n{detail}\n\n"
            f"Source : {dernier['source']}\n\n#Populous #Presidentielle2027 #Sondage"
        ),
    }


def contenu_depute():
    elus = json.loads((DOSSIER / 'elus.json').read_text(encoding='utf-8'))['elus']
    elu = random.choice(elus)

    today = json.loads((DOSSIER / 'data' / 'today.json').read_text(encoding='utf-8'))
    numero = today.get('featured_numero') or today.get('last_featured_numero')
    vote_txt, vote_bloc = '', None
    if numero is not None:
        scrutin = json.loads((DOSSIER / 'data' / 'scrutins' / f'{numero}.json').read_text(encoding='utf-8'))
        pos = _norm_pos(scrutin['par_circonscription'].get(elu['k']))
        label = 'Vote du jour' if today.get('featured_numero') is not None else 'Dernier vote connu'
        date_fr = datetime.date.fromisoformat(scrutin['date']).strftime('%d/%m/%Y')
        vote_bloc = {
            'label': label, 'titre': scrutin['titre'], 'numero': scrutin['numero'], 'date': date_fr,
            'position_label': POS_LABEL[pos], 'couleur': VOTE_COLORS[pos],
        }
        vote_txt = f"\n{label} : {scrutin['titre']}\n{POS_LABEL[pos]} — scrutin n°{scrutin['numero']} du {date_fr}\n"

    circonscription = f"{DEP_NAMES.get(elu['dep'], elu['dep'])} — {elu['ci']}e circonscription · {elu['age']} ans"
    profession = elu['pro'] or 'Non renseignée'
    return {
        'eyebrow': 'Député du jour',
        'titre': elu['n'],
        'bloc_depute': {
            'groupe_sigle': elu['g'], 'groupe_couleur': _hex_vers_rgb(elu['col']), 'groupe_nom': elu['gn'],
            'circonscription': circonscription, 'profession': profession, 'vote': vote_bloc,
        },
        'legende': (
            f"{elu['n']} ({elu['g']})\n\n{elu['gn']}\n{circonscription}\nProfession : {profession}\n{vote_txt}\n"
            f"Retrouve son activité complète à l'Assemblée sur Populous.\n\n#Populous #AssembleeNationale #{elu['g']}"
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
        'eyebrow': 'À venir',
        'titre': "Cette semaine à l'Assemblée",
        'texte': '  •  '.join(lignes),
        'legende': "Cette semaine à l'Assemblée nationale :\n\n" + '\n'.join(f"- {l}" for l in lignes)
        + "\n\nSuis chaque vote en direct sur Populous.\n\n#Populous #AssembleeNationale",
    }


def contenu_boussole():
    return {
        'eyebrow': 'Boussole politique',
        'titre': 'Compare tes opinions aux votes réels de tes élus',
        'texte': "Réponds à quelques questions et découvre quel groupe politique vote le plus comme toi.",
        'pile_resultats': pile_boussole_exemple(),
        'legende': (
            "Ta boussole politique : compare tes opinions aux votes réels de tes élus, "
            "sans jugement ni étiquette imposée.\n\nTeste la boussole sur Populous.\n\n#Populous #BoussolePolitique"
        ),
    }


CHOIX = {
    'fait': contenu_fait_du_jour,
    'presidentiel': contenu_presidentielle,
    'depute': contenu_depute,
    'avenir': contenu_avenir,
    'boussole': contenu_boussole,
}


def _lever_avec_detail(r):
    """r.raise_for_status(), mais avec le corps de la reponse dans le
    message d'erreur — sans ca, un echec Graph API ne montre dans les
    logs GitHub Actions qu'un « 400 Client Error » sans dire pourquoi."""
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise requests.exceptions.HTTPError(f"{e} — corps de la reponse : {r.text}", response=r) from None


def publier_photo_facebook(page_id, page_token, chemin_image, legende):
    with open(chemin_image, 'rb') as f:
        r = requests.post(
            f'{GRAPH}/{page_id}/photos',
            data={'caption': legende, 'access_token': page_token},
            files={'source': f},
            timeout=30,
        )
    _lever_avec_detail(r)
    return r.json()  # {'id': photo_id, 'post_id': page_id_postid}


def url_publique_photo(photo_id, token):
    r = requests.get(f'{GRAPH}/{photo_id}', params={'fields': 'images', 'access_token': token}, timeout=20)
    _lever_avec_detail(r)
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
    _lever_avec_detail(r)
    creation_id = r.json()['id']

    # Le traitement du container (recuperation + encodage de l'image cote
    # Instagram) est asynchrone : publier immediatement echoue parfois
    # (400) si le statut n'est pas encore FINISHED. On sonde plutot que
    # de publier a l'aveugle juste apres la creation.
    for _ in range(10):
        r = requests.get(f'{GRAPH}/{creation_id}', params={'fields': 'status_code', 'access_token': page_token}, timeout=20)
        _lever_avec_detail(r)
        statut = r.json().get('status_code')
        if statut == 'FINISHED':
            break
        if statut == 'ERROR':
            raise RuntimeError(f"Le container Instagram {creation_id} a echoue (status_code=ERROR).")
        time.sleep(3)
    else:
        raise RuntimeError(f"Le container Instagram {creation_id} n'etait toujours pas pret apres 30s d'attente.")

    r = requests.post(
        f'{GRAPH}/{ig_user_id}/media_publish',
        data={'creation_id': creation_id, 'access_token': page_token},
        timeout=30,
    )
    _lever_avec_detail(r)
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
    generer(
        chemin_image, eyebrow=contenu['eyebrow'], titre=contenu['titre'], texte=contenu.get('texte'), photo=photo,
        date_badge=contenu.get('date_badge'), bloc_depute=contenu.get('bloc_depute'),
        pile_resultats=contenu.get('pile_resultats'),
    )

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
