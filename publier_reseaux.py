#!/usr/bin/env python3
"""Publie un post sur la Page Facebook « Media Populous » et sur le
compte Instagram @populous_officiel, sous forme de CARROUSEL de 5 slides
(HyperFrames, cf. carrousels/generer_carrousel.py) genere a la volee.

Format (depuis le 31 octobre 2026) : chaque post est un carrousel de 5 slides
qui forment une bande continue. Facebook recoit un diaporama des 5 images ;
Instagram un carrousel de 5 VIDEOS (chaque slide s'anime quand on arrive
dessus), avec repli automatique sur les 5 images si la voie video echoue
avant la publication. L'ancien visuel unique (generer_visuel.py) n'est plus
utilise par ce script.

Contenu (jamais invente, cf. CLAUDE.md) : cinq types, choisis avec
--type sur la ligne de commande pour que chaque creneau cron sache
exactement ce qu'il poste plutot que de tirer au hasard :
  - fait        : le fait du jour deja curate dans data/refs_jour.json
  - presidentiel: le dernier sondage 2027 deja recupere (et source) dans
                  data/sondages.json — le cron tourne quotidiennement mais
                  ne publie que si ce sondage n'a pas deja ete poste (les
                  instituts n'en sortent pas un par jour), etat garde dans
                  data/state_publication.json
  - depute      : un depute tire au hasard dans elus.json, avec son
                  portrait officiel (meme atlas que index.html)
  - avenir      : les 3 prochains points a l'ordre du jour de
                  l'Assemblee, deja recuperes dans data/agenda.json
                  (planifie 1x/semaine, cf. publier_reseaux.yml)
  - boussole    : accroche fixe invitant a tester la boussole politique
                  de l'app (texte relu une fois pour toutes, jamais
                  genere a la demande) — planifie 1x/mois (le 15), pour
                  ne pas repeter un visuel quasi identique chaque jour

  - vote        : la carte d'un scrutin (« Vote d'hier »), generee par
                  generer_post_vote.py. JAMAIS planifie : declenche a la
                  main avec --numero et --titre (le titre synthetique est
                  relu et fourni par un humain), et refuse de republier
                  le meme scrutin (data/state_publication.json) sauf
                  --forcer. Avec --resume (extrait de l'expose des motifs,
                  relu par un humain) et --source-resume, le post devient
                  un diaporama de 2 images : la carte, puis « De quoi parle
                  cette loi ? ».

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
import re
import sys
import time
from pathlib import Path

import requests

from generer_visuel import generer, portrait_depute, pile_boussole_exemple
import generer_post_vote

DOSSIER = Path(__file__).parent
sys.path.insert(0, str(DOSSIER / 'carrousels'))
import generer_carrousel
import generer_reel
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


ETAT_PUBLICATION = DOSSIER / 'data' / 'state_publication.json'


def lire_etat_publication():
    if not ETAT_PUBLICATION.exists():
        return {}
    return json.loads(ETAT_PUBLICATION.read_text(encoding='utf-8'))


def ecrire_etat_publication(etat):
    ETAT_PUBLICATION.write_text(json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')


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


def _titre_court(texte, limite=80):
    """Tronque sur un mot entier — utilise uniquement quand la source ne
    fournit pas de titre distinct du texte (cf. contenu_fait_du_jour)."""
    if len(texte) <= limite:
        return texte
    coupe = texte[:limite].rsplit(' ', 1)[0]
    return coupe.rstrip('.,;: ') + '…'


# Fin de légende commune : une question NEUTRE qui appelle un commentaire, la source, 5 hashtags (les commentaires nourrissent la portée).
def _fin_fait(ref):
    src = f"📚 Source : {ref['source']}\n\n" if ref.get('source') else ''
    return ("Tu connaissais ce moment de l'histoire politique ? Dis-le en commentaire 👇\n\n" + src
            + "#Populous #HistoirePolitique #AssembléeNationale #Histoire #Politique")


def contenu_fait_du_jour():
    d = json.loads((DOSSIER / 'data' / 'refs_jour.json').read_text(encoding='utf-8'))
    cle = datetime.date.today().strftime('%m-%d')
    refs = d['refs'].get(cle) or []
    if not refs:
        return None
    ref = refs[0]
    mois, jour = cle.split('-')
    date_badge = f"{int(jour)} {MOIS_FR[int(mois) - 1]} {ref['annee']}"

    if ref.get('titre'):
        titre = f"{ref['annee']} : {ref['titre']}"
        texte = ref['texte']
        legende = f"{titre}\n\n{texte}\n\n{_fin_fait(ref)}"
    else:
        # Faits sans titre distinct (notamment ceux venus de Wikipedia via
        # construire_refs_jour_wikipedia.py, largement majoritaires dans
        # refs_jour.json) : le texte EST le titre. Le reprendre aussi comme
        # paragraphe secondaire produirait une repetition exacte a l'ecran
        # comme dans la legende — on ne l'affiche donc qu'une fois.
        titre = f"{ref['annee']} : {_titre_court(ref['texte'])}"
        texte = None
        legende = f"{ref['texte']}\n\n{_fin_fait(ref)}"

    return {
        'eyebrow': 'Fait du jour',
        'titre': titre,
        'texte': texte,
        'date_badge': date_badge,
        'legende': legende,
    }


def contenu_presidentielle():
    d = json.loads((DOSSIER / 'data' / 'sondages.json').read_text(encoding='utf-8'))
    dernier = max(d['sondages'], key=lambda s: s['date'])

    # Les instituts ne publient pas un sondage par jour : reposter le meme
    # chaque jour (le cron tourne quotidiennement) donnait un fil repetitif.
    # On ne publie donc que si ce sondage precis (date + institut, car
    # plusieurs instituts publient parfois le meme jour) n'a encore jamais
    # ete poste — cf. main(), qui met a jour l'etat apres publication reelle.
    identifiant = f"{dernier['date']}|{dernier['institut']}"
    if identifiant == lire_etat_publication().get('dernier_sondage_publie'):
        return None

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
            f"Qu'est-ce qui te frappe dans ce sondage ? Dis-le en commentaire 👇\n\n"
            f"📊 Source : {dernier['source']}\n\n#Populous #Présidentielle2027 #Sondage #Politique #France"
        ),
        'cle_etat': 'dernier_sondage_publie',
        'valeur_etat': identifiant,
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
            f"Tu sais comment ton député vote ? Dis-nous son nom en commentaire 👇\n"
            f"📲 Son activité complète à l'Assemblée est dans l'app Populous (lien en bio).\n\n"
            f"#Populous #AssembléeNationale #{elu['g']} #Député #Politique"
        ),
        'a_index': elu['a'],
        'nom_depute': elu['n'],
        'numero_scrutin': numero,
        # Portrait + donnees de vote viennent de l'Assemblee (Licence
        # Ouverte Etalab, mention de source obligatoire) — remplace le
        # pied de page "Populous - iOS" habituel (cf. docstring
        # pied_source dans generer_visuel.generer).
        'pied_source': 'Source : Assemblée nationale (data.assemblee-nationale.fr)',
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
        + "\n\nQuel texte vas-tu suivre cette semaine ? Dis-le en commentaire 👇\n"
        "📲 Chaque vote, en direct, dans l'app Populous (lien en bio).\n\n#Populous #AssembléeNationale #Agenda #Politique #Loi",
    }


def contenu_boussole():
    return {
        'eyebrow': 'Boussole politique',
        'titre': 'Compare tes opinions aux votes réels de tes élus',
        'texte': "Réponds à quelques questions et découvre quel groupe politique vote le plus comme toi.",
        'pile_resultats': pile_boussole_exemple(),
        'legende': (
            "Ta boussole politique : compare tes opinions aux votes réels de tes élus, "
            "sans jugement ni étiquette imposée.\n\nQuel groupe a le plus voté comme toi ? Dis-le en commentaire 👇\n"
            "📲 Teste la boussole dans l'app Populous (lien en bio).\n\n#Populous #BoussolePolitique #Politique #Vote #Démocratie"
        ),
    }



# ---------------------------------------------------------------- « loi votee » (automatique)
# Un vote solennel sur un TEXTE (ensemble d'un projet / d'une proposition de loi, ou premiere partie du budget) donne un
# carrousel : le texte et le tampon, de quoi il parle, les chiffres, l'hemicycle, Populous. Tout est deduit des donnees
# officielles (data/scrutins) et de regles sourcees ; rien n'est invente. Pas de resume de texte ecrit par nous (cf. CLAUDE.md) :
# l'explication ne contient que la nature du texte (Constitution, art. 39 ; LOLF, art. 1/34/42), le sort et les chiffres.
TEXTE_LOI_RE = re.compile(r"^(?:l'ensemble (?:de la|du|des) |la première partie du projet de loi de finances|la proposition de loi|le projet de loi)", re.I)
FENETRE_LOI_JOURS = 3          # on ne publie pas un vote plus vieux que ca (« vote d'hier » doit rester vrai)


def _sort_adopte(vote):
    s = (vote.get('sort') or '').lower()
    return False if 'pas adopt' in s else (True if 'adopt' in s else None)


def _scrutins_solennels_de_texte(aujourdhui):
    """Scrutins solennels sur un texte, des FENETRE_LOI_JOURS derniers jours, du plus ancien au plus recent."""
    today = json.loads((DOSSIER / 'data' / 'today.json').read_text(encoding='utf-8'))
    ref = max(n for n in (today.get('featured_numero'), today.get('last_featured_numero')) if n)
    limite = (aujourdhui - datetime.timedelta(days=FENETRE_LOI_JOURS)).isoformat()
    trouves = []
    for n in range(ref, ref - 400, -1):
        f = DOSSIER / 'data' / 'scrutins' / f'{n}.json'
        if not f.exists():
            continue
        v = json.loads(f.read_text(encoding='utf-8'))
        if v['date'] < limite:
            break                                      # les numeros sont chronologiques
        if v['date'] <= aujourdhui.isoformat() and v.get('solennel') and TEXTE_LOI_RE.match(v.get('objet') or v['titre']):
            trouves.append(v)
    return sorted(trouves, key=lambda v: (v['date'], v['numero']))


def titre_loi(objet):
    """Intitule officiel, mis en forme sans le reformuler : « l'ensemble de la proposition de loi visant a… » -> « Proposition de loi visant a… »."""
    t = re.sub(r"^(?:l'ensemble (?:de la|du|des) |la |le |l')", '', objet.strip().rstrip('.').strip(), flags=re.I)
    return _titre_court(t[:1].upper() + t[1:], 150)


def explication_loi(vote):
    """([[titre, texte], ...], source). 2 ou 3 blocs, tous deduits de la nature du texte, du sort et des chiffres officiels."""
    objet = vote.get('objet') or vote['titre']; t = vote['tally']
    lecture = re.search(r"\(([^)]*lecture[^)]*)\)", objet)
    adopte = _sort_adopte(vote)
    sort = {True: 'adopté', False: 'rejeté'}[adopte]
    chiffres = f"{t['pour']} pour, {t['contre']} contre, {t['abstention']} abstention{'s' if t['abstention'] > 1 else ''}"
    annee = re.search(r"projet de loi de finances pour (\d{4})", objet, re.I)
    if annee and re.match(r"la première partie", objet, re.I):          # LOLF art. 34 (contenu) et art. 42 (ordre d'examen)
        return ([["Ce que c’est", f"La première partie du budget {annee.group(1)} : elle autorise l’État à percevoir les recettes et fixe l’équilibre général des finances publiques."],
                 ["Pourquoi ça compte", "Passage obligé : la seconde partie, qui fixe les crédits (les dépenses), ne peut pas être discutée avant que celle-ci soit adoptée."],
                 ["Ce vote", f"Vote solennel sur l’ensemble de la première partie{', en ' + lecture.group(1) if lecture else ''} : {chiffres}."]],
                "Sources : loi organique relative aux lois de finances (art. 34 et 42) · assemblee-nationale.fr")
    m = re.search(r"(proposition|projet) de loi( organique)?", objet, re.I)
    if not m:
        raise RuntimeError(f"Nature du texte introuvable dans : {objet}")
    kind = m.group(1).lower(); org = ' organique' if m.group(2) else ''
    qui = 'des parlementaires' if kind == 'proposition' else 'le Gouvernement'
    ce_que = f"{'Une' if kind == 'proposition' else 'Un'} {kind} de loi{org} : un texte déposé par {qui}."
    if lecture:
        ce_que += f" Ici : {lecture.group(1)} à l’Assemblée nationale."
    vote_txt = f"Vote solennel sur {'l’ensemble du texte' if 'ensemble' in objet.lower() else 'le texte'}. Résultat : {sort} ({chiffres})."
    return ([["Ce que c’est", ce_que], ["Ce vote", vote_txt]],
            "Sources : Constitution (art. 39) · assemblee-nationale.fr")


def contenu_loi():
    """Le prochain texte vote (vote solennel) a publier, ou None. Un seul par execution ; les autres partent aux executions suivantes."""
    aujourdhui = datetime.date.today()
    deja = set(lire_etat_publication().get('lois_publiees', []))
    for vote in _scrutins_solennels_de_texte(aujourdhui):
        if vote['numero'] in deja:
            continue
        if _sort_adopte(vote) is None:
            print(f"Scrutin {vote['numero']} : sort officiel illisible, ignore ({vote.get('sort')!r}).")
            continue
        titre = titre_loi(vote.get('objet') or vote['titre'])
        blocs, source = explication_loi(vote)
        contours = generer_post_vote.charger_contours((DOSSIER / 'index.html').read_text(encoding='utf-8'))
        legende = generer_post_vote.legende(vote, titre, contours)
        return {'legende': legende, 'cle_etat': 'lois_publiees', 'valeur_etat': sorted(deja | {vote['numero']}),
                'numero_scrutin': vote['numero'], 'titre_loi': titre, 'explication': blocs, 'source_explication': source}
    return None


CHOIX = {
    'fait': contenu_fait_du_jour,
    'presidentiel': contenu_presidentielle,
    'depute': contenu_depute,
    'avenir': contenu_avenir,
    'boussole': contenu_boussole,
    'loi': contenu_loi,
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


def preparer_vote(args):
    """Parametres du carrousel + legende du post « Vote d'hier ». Lit data/ et index.html du
    checkout (le workflow tourne sur une copie fraiche de main). Renvoie (parametres, contenu)."""
    if not args.numero or not args.titre:
        sys.exit("--type vote exige --numero et --titre (titre synthetique relu par un humain).")
    if args.resume and not args.source_resume:
        sys.exit("--resume exige --source-resume (ex. « exposé des motifs de la proposition de loi n°3106 »).")
    vote = json.loads((DOSSIER / 'data' / 'scrutins' / f'{args.numero}.json').read_text(encoding='utf-8'))
    if args.publier and not args.forcer and lire_etat_publication().get('dernier_vote_publie') == args.numero:
        sys.exit(f"Le scrutin {args.numero} a deja ete publie (--forcer pour republier).")
    contours = generer_post_vote.charger_contours((DOSSIER / 'index.html').read_text(encoding='utf-8'))
    legende = generer_post_vote.legende(vote, args.titre, contours)
    if args.resume:        # l'ancien 2e visuel « De quoi parle cette loi ? » passe dans la legende (texte relu par un humain)
        legende = legende.replace('\n\n#', f"\n\nDe quoi parle cette loi ? {args.resume} (source : {args.source_resume})\n\n#", 1)
    contenu = {'legende': legende, 'cle_etat': 'dernier_vote_publie', 'valeur_etat': args.numero}
    return {'scrutin': args.numero, 'titre_vote': args.titre}, contenu


def parametres_carrousel(type_, contenu):
    """Ce dont le generateur de carrousel a besoin pour un type donne (memes donnees que la legende)."""
    if type_ == 'fait':
        return {'mmjj': datetime.date.today().strftime('%m-%d')}
    if type_ == 'depute':
        return {'depute': contenu['nom_depute'], 'scrutin': contenu.get('numero_scrutin')}
    if type_ == 'loi':
        return {'scrutin': contenu['numero_scrutin'], 'titre_vote': contenu['titre_loi'], 'explication': json.dumps(contenu['explication'], ensure_ascii=False), 'source_explication': contenu['source_explication']}
    return {}


def _attendre_conteneur_instagram(creation_id, page_token, essais=10, pause=3):
    """Sonde le statut d'un container Instagram jusqu'a FINISHED (cf.
    publier_instagram : publier a l'aveugle echoue parfois en 400). En cas d'ERROR, le texte d'Instagram
    (ex. « Media upload has failed with error code 2207076 ») est inclus dans l'erreur."""
    for _ in range(essais):
        r = requests.get(f'{GRAPH}/{creation_id}', params={'fields': 'status_code,status', 'access_token': page_token}, timeout=20)
        _lever_avec_detail(r)
        infos = r.json()
        statut = infos.get('status_code')
        if statut == 'FINISHED':
            return
        if statut == 'ERROR':
            raise RuntimeError(f"Le container Instagram {creation_id} a echoue : {infos.get('status')}")
        time.sleep(pause)
    raise RuntimeError(f"Le container Instagram {creation_id} n'etait toujours pas pret apres {essais * pause}s d'attente.")


def _poster_avec_reessais(url, essais=3, pause=6, **kw):
    """requests.post avec nouvel essai sur les erreurs serveur ponctuelles de Meta (HTTP 5xx, ex. 500 « An unknown
    error occurred » code 1 / sous-code 99 constate le 1er nov. 2026). Une erreur 4xx est definitive : pas de nouvel essai."""
    for essai in range(1, essais + 1):
        r = requests.post(url, **kw)
        if r.status_code < 500 or essai == essais:
            return r
        print(f"  {url.split('/')[-1]} : HTTP {r.status_code} (essai {essai}/{essais}), nouvel essai dans {pause}s")
        time.sleep(pause)


def televerser_photos_facebook_non_publiees(page_id, page_token, chemins_images):
    """Envoie les images sur la Page SANS les publier (published=false) : sert uniquement a obtenir leurs URL publiques pour Instagram."""
    ids = []
    for chemin in chemins_images:
        with open(chemin, 'rb') as f:
            r = requests.post(f'{GRAPH}/{page_id}/photos', data={'published': 'false', 'access_token': page_token}, files={'source': f}, timeout=60)
        _lever_avec_detail(r)
        ids.append(r.json()['id'])
    return ids


def publier_diaporama_facebook(page_id, page_token, chemins_images, legende):
    """Diaporama Facebook : chaque image est envoyee NON publiee
    (published=false), puis un seul post /feed les rassemble via
    attached_media. Renvoie (reponse du post, [ids des photos])."""
    ids = []
    for chemin in chemins_images:
        with open(chemin, 'rb') as f:
            r = requests.post(
                f'{GRAPH}/{page_id}/photos',
                data={'published': 'false', 'access_token': page_token},
                files={'source': f},
                timeout=60,
            )
        _lever_avec_detail(r)
        ids.append(r.json()['id'])
    data = {'message': legende, 'access_token': page_token}
    for i, photo_id in enumerate(ids):
        data[f'attached_media[{i}]'] = json.dumps({'media_fbid': photo_id})
    r = requests.post(f'{GRAPH}/{page_id}/feed', data=data, timeout=30)
    _lever_avec_detail(r)
    return r.json(), ids


def _creer_enfant_video_instagram(ig_user_id, page_token, chemin):
    """Enfant VIDEO du carrousel par ENVOI DIRECT (resumable upload) : Instagram donne une adresse d'envoi
    (rupload.facebook.com) et on y poste les octets du fichier. Aucune URL publique n'est necessaire. L'ancienne voie
    (URL d'une video Facebook non publiee) etait refusee par Instagram : erreur 2207076, constate le 1er nov. 2026."""
    r = _poster_avec_reessais(f'{GRAPH}/{ig_user_id}/media', data={'media_type': 'VIDEO', 'is_carousel_item': 'true',
                              'upload_type': 'resumable', 'thumb_offset': '5500', 'access_token': page_token}, timeout=60)  # couverture = etat final de la slide, pas le 1er cadre (« 0000 » flou)
    _lever_avec_detail(r)
    infos = r.json()
    octets = Path(chemin).read_bytes()
    r = _poster_avec_reessais(infos['uri'], headers={'Authorization': f'OAuth {page_token}', 'offset': '0', 'file_size': str(len(octets))},
                              data=octets, timeout=240)
    _lever_avec_detail(r)
    return infos['id']


def preparer_carrousel_instagram(ig_user_id, page_token, elements, legende):
    """Cree (SANS publier) le carrousel Instagram : un container enfant par element, puis un container CAROUSEL qui
    les reference. elements = [('IMAGE', url_publique) | ('VIDEO', chemin_du_fichier)]. La legende ne se met que sur le
    parent. Renvoie l'id du parent, pret a publier. Aucun effet public tant que publier_conteneur_instagram n'est pas
    appele : une erreur ici autorise un repli sans risque de doublon."""
    enfants, video = [], False
    for genre, valeur in elements:
        if genre == 'VIDEO':
            enfants.append(_creer_enfant_video_instagram(ig_user_id, page_token, valeur)); video = True
            continue
        r = _poster_avec_reessais(f'{GRAPH}/{ig_user_id}/media', data={'is_carousel_item': 'true', 'image_url': valeur, 'access_token': page_token}, timeout=60)
        _lever_avec_detail(r)
        enfants.append(r.json()['id'])
    for enfant in enfants:
        _attendre_conteneur_instagram(enfant, page_token, essais=(40 if video else 10), pause=(5 if video else 3))
    r = _poster_avec_reessais(
        f'{GRAPH}/{ig_user_id}/media',
        data={'media_type': 'CAROUSEL', 'children': ','.join(enfants), 'caption': legende, 'access_token': page_token},
        timeout=30,
    )
    _lever_avec_detail(r)
    parent = r.json()['id']
    _attendre_conteneur_instagram(parent, page_token, essais=(20 if video else 10), pause=(5 if video else 3))
    return parent


# ---------------------------------------------------------------- Reels (au moins un par jour)
# Le texte vote la veille quand il y en a un (meme choix et memes textes que le carrousel « loi »), sinon le prochain Reel
# pedagogique de data/reels_pedagogiques.json (faits verifies sur sources officielles, cites dans la legende). Une file epuisee repart du debut.
def scenario_loi_reel(vote, titre, blocs, source):
    """Scenario de Reel (voir carrousels/moteur/reel/construire.py) d'un vote solennel sur un texte : le texte + tampon, les chiffres, de quoi il parle, l'hemicycle."""
    adopte = _sort_adopte(vote)
    d = datetime.date.fromisoformat(vote['date'])
    return {'scenes': [
        {'type': 'titre', 'eyebrow': f"Vote solennel · {d.day} {MOIS_FR[d.month - 1]} {d.year}", 'titre': titre,
         'tampon': 'ADOPTÉ' if adopte else 'REJETÉ', 'couleur': 'vert' if adopte else 'orange', 'duree': 4.4},
        {'type': 'chiffres', 'duree': 5.0},
        {'type': 'cartes', 'titre': 'De quoi parle ce texte ?', 'sous': {2: 'Deux choses à savoir.', 3: 'Trois choses à savoir.'}[len(blocs)],
         'cartes': blocs, 'duree': 2.6 + 1.6 * len(blocs)},
        {'type': 'hemicycle', 'duree': 4.2}],
        'fin': {'duree': 3.8}, 'source': source}


def contenu_reel():
    """Le Reel du jour, ou None. Renvoie un dict : scenario, scrutin (ou None), legende, cle_etat, valeur_etat."""
    aujourdhui = datetime.date.today()
    etat = lire_etat_publication()
    deja = set(etat.get('lois_reel_publiees', []))
    for vote in _scrutins_solennels_de_texte(aujourdhui):
        if vote['numero'] in deja or _sort_adopte(vote) is None:
            continue
        titre = titre_loi(vote.get('objet') or vote['titre'])
        blocs, source = explication_loi(vote)
        contours = generer_post_vote.charger_contours((DOSSIER / 'index.html').read_text(encoding='utf-8'))
        return {'type_reel': 'loi', 'scenario': scenario_loi_reel(vote, titre, blocs, source), 'scrutin': vote['numero'],
                'legende': generer_post_vote.legende(vote, titre, contours), 'cle_etat': 'lois_reel_publiees', 'valeur_etat': sorted(deja | {vote['numero']})}
    file_ = json.loads((DOSSIER / 'data' / 'reels_pedagogiques.json').read_text(encoding='utf-8'))['reels']
    publies = [i for i in etat.get('reels_pedagogiques_publies', []) if any(r['id'] == i for r in file_)]
    if len(publies) >= len(file_):
        publies = []                                           # tous publies : on repart du debut
    for r in file_:
        if r['id'] not in publies:
            return {'type_reel': 'pedagogique', 'scenario': {'scenes': r['scenes'], 'fin': {'duree': 3.8}, 'source': r['source']}, 'scrutin': None,
                    'legende': r['legende'], 'cle_etat': 'reels_pedagogiques_publies', 'valeur_etat': publies + [r['id']], 'id': r['id']}
    return None


def publier_reel_instagram(ig_user_id, page_token, chemin, legende, thumb_offset=2600):
    """Reel Instagram par envoi direct (resumable upload), publie aussi dans le fil. Renvoie la reponse de la publication."""
    r = _poster_avec_reessais(f'{GRAPH}/{ig_user_id}/media', data={'media_type': 'REELS', 'upload_type': 'resumable', 'caption': legende,
                              'share_to_feed': 'true', 'thumb_offset': str(thumb_offset), 'access_token': page_token}, timeout=60)
    _lever_avec_detail(r)
    infos = r.json()
    octets = Path(chemin).read_bytes()
    r = _poster_avec_reessais(infos['uri'], headers={'Authorization': f'OAuth {page_token}', 'offset': '0', 'file_size': str(len(octets))}, data=octets, timeout=300)
    _lever_avec_detail(r)
    _attendre_conteneur_instagram(infos['id'], page_token, essais=60, pause=5)
    return publier_conteneur_instagram(ig_user_id, page_token, infos['id'])


def publier_reel_facebook(page_id, page_token, chemin, description):
    """Reel sur la Page Facebook (3 phases : start, envoi des octets, finish). Renvoie l'id de la video."""
    r = _poster_avec_reessais(f'{GRAPH}/{page_id}/video_reels', data={'upload_phase': 'start', 'access_token': page_token}, timeout=60)
    _lever_avec_detail(r)
    infos = r.json(); video_id = infos['video_id']
    octets = Path(chemin).read_bytes()
    r = _poster_avec_reessais(infos['upload_url'], headers={'Authorization': f'OAuth {page_token}', 'offset': '0', 'file_size': str(len(octets))}, data=octets, timeout=300)
    _lever_avec_detail(r)
    r = _poster_avec_reessais(f'{GRAPH}/{page_id}/video_reels', data={'upload_phase': 'finish', 'video_id': video_id, 'video_state': 'PUBLISHED',
                              'description': description, 'access_token': page_token}, timeout=60)
    _lever_avec_detail(r)
    for _ in range(30):                                        # attend que Facebook ait fini de traiter la video (sans bloquer indefiniment)
        r = requests.get(f'{GRAPH}/{video_id}', params={'fields': 'status', 'access_token': page_token}, timeout=20)
        if r.status_code == 200 and (r.json().get('status') or {}).get('video_status') in ('ready', 'published'):
            break
        time.sleep(6)
    return video_id


def main_reel(args):
    contenu = contenu_reel()
    if contenu is None:
        print("Rien a publier pour --type reel aujourd'hui.")
        return
    dossier_sortie = DOSSIER / 'assets_social' / 'reels' / f"{datetime.date.today().isoformat()}-{contenu['type_reel']}"
    print(f"Generation du reel « {contenu['type_reel']} » (HyperFrames) -> {dossier_sortie}")
    reel = generer_reel.generer(contenu['scenario'], dossier_sortie, scrutin=contenu['scrutin'])
    print(f"Reel : {reel['duree']:.1f} s, {reel['reel']}\nLegende :\n{contenu['legende']}\n")
    if not args.publier:
        print("Mode brouillon (--publier non passe) : rien n'a ete publie.")
        return
    env = lire_env()
    plateformes = {x.strip() for x in args.plateformes.split(',') if x.strip()}
    if plateformes - {'facebook', 'instagram'} or not plateformes:
        sys.exit(f"--plateformes : valeurs possibles « facebook », « instagram » (recu : {args.plateformes}).")
    reussies, echecs = [], []
    for nom, f in (('instagram', lambda: publier_reel_instagram(env['IG_USER_ID'], env['FB_PAGE_TOKEN'], reel['reel'], contenu['legende'])),
                   ('facebook', lambda: publier_reel_facebook(env['FB_PAGE_ID'], env['FB_PAGE_TOKEN'], reel['reel'], contenu['legende']))):
        if nom not in plateformes:
            continue
        try:
            print(f"{nom.capitalize()} publie : {f()}"); reussies.append(nom)
        except Exception as e:                                 # une plateforme en panne ne doit pas empecher l'autre
            print(f"::error::{nom} : {e}"); echecs.append(nom)
    if reussies:                                               # etat mis a jour des qu'une plateforme a publie : jamais de doublon au creneau suivant
        etat = lire_etat_publication(); etat[contenu['cle_etat']] = contenu['valeur_etat']; ecrire_etat_publication(etat)
        print(f"Etat mis a jour : {contenu['cle_etat']} = {contenu['valeur_etat']}")
    if echecs:
        sys.exit(f"Reel non publie sur : {', '.join(echecs)}.")


def publier_conteneur_instagram(ig_user_id, page_token, creation_id, essais=6, pause=10):
    """Seule etape publique cote Instagram. Instagram annonce parfois FINISHED trop tot : media_publish repond alors
    400 « Media ID is not available » (code 9007, sous-code 2207027 : « patientez un peu ») — constate le 31 oct. 2026
    (run #150 : Facebook publie, Instagram refuse). On reessaie plusieurs fois, uniquement pour cette erreur-la
    (une autre erreur est definitive) ; tant que ce n'est pas un succes rien n'est public, donc pas de risque de doublon."""
    for essai in range(1, essais + 1):
        r = requests.post(f'{GRAPH}/{ig_user_id}/media_publish', data={'creation_id': creation_id, 'access_token': page_token}, timeout=60)
        if ((r.status_code == 400 and '2207027' in r.text) or r.status_code >= 500) and essai < essais:
            print(f"  Instagram : contenu pas encore pret (essai {essai}/{essais}), nouvel essai dans {pause}s")
            time.sleep(pause)
            continue
        _lever_avec_detail(r)
        return r.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--type', choices=[*CHOIX.keys(), 'vote', 'reel'], required=True)
    parser.add_argument('--publier', action='store_true', help="Publie reellement (sinon : brouillon local seulement).")
    parser.add_argument('--numero', type=int, help="(vote) numero du scrutin.")
    parser.add_argument('--titre', help="(vote) titre synthetique, relu par un humain.")
    parser.add_argument('--forcer', action='store_true', help="(vote) republie meme si deja publie.")
    parser.add_argument('--resume', help="(vote) extrait de l'expose des motifs, relu par un humain : ajoute un paragraphe a la legende.")
    parser.add_argument('--source-resume', dest='source_resume', help="(vote) source du resume, ex. « exposé des motifs de la proposition de loi n°3106 ».")
    parser.add_argument('--plateformes', default='facebook,instagram', help="Ou publier : « facebook,instagram » (defaut), « instagram » ou « facebook » (rattrapage sans doublon).")
    parser.add_argument('--sans-video-instagram', action='store_true', help="Instagram : carrousel d'images au lieu de videos.")
    args = parser.parse_args()

    if args.type == 'reel':
        return main_reel(args)
    if args.type == 'vote':
        params, contenu = preparer_vote(args)
    else:
        contenu = CHOIX[args.type]()
        if contenu is None:
            print(f"Rien a publier pour --type {args.type} aujourd'hui.")
            return
        params = parametres_carrousel(args.type, contenu)

    dossier_sortie = DOSSIER / 'assets_social' / 'carrousels' / f'{datetime.date.today().isoformat()}-{args.type}'
    print(f"Generation du carrousel « {args.type} » (HyperFrames) -> {dossier_sortie}")
    carrousel = generer_carrousel.generer(args.type, dossier_sortie, **params)    # leve RuntimeError au moindre echec : jamais de demi-carrousel publie
    print(f"Carrousel : {len(carrousel['slides_png'])} slides, apercu {carrousel['apercu']}")
    print(f"Legende :\n{contenu['legende']}\n")

    if not args.publier:
        print("Mode brouillon (--publier non passe) : rien n'a ete publie.")
        return

    env = lire_env()
    page_id, page_token, ig_user_id = env['FB_PAGE_ID'], env['FB_PAGE_TOKEN'], env['IG_USER_ID']
    plateformes = {x.strip() for x in args.plateformes.split(',') if x.strip()}
    inconnues = plateformes - {'facebook', 'instagram'}
    if inconnues or not plateformes:
        sys.exit(f"--plateformes : valeurs possibles « facebook », « instagram » (recu : {args.plateformes}).")

    ids_photos = None
    if 'facebook' in plateformes:
        reponse_fb, ids_photos = publier_diaporama_facebook(page_id, page_token, carrousel['slides_png'], contenu['legende'])
        print(f"Facebook publie (diaporama de {len(ids_photos)} images) : {reponse_fb}")

    if 'instagram' in plateformes:
        parent = None
        if not args.sans_video_instagram:
            try:
                parent = preparer_carrousel_instagram(ig_user_id, page_token, [('VIDEO', c) for c in carrousel['slides_mp4']], contenu['legende'])
                print("Instagram : carrousel de 5 videos pret.")
            except Exception as e:      # rien n'est public a ce stade : repli sur les images, sans risque de doublon
                print(f"::warning::Voie video Instagram impossible ({e}) : repli sur le carrousel d'images.")
        if parent is None:
            if ids_photos is None:      # Facebook non publie : on envoie quand meme les images (non publiees) pour obtenir leurs URL publiques
                ids_photos = televerser_photos_facebook_non_publiees(page_id, page_token, carrousel['slides_png'])
            urls_images = [url_publique_photo(pid, page_token) for pid in ids_photos]
            parent = preparer_carrousel_instagram(ig_user_id, page_token, [('IMAGE', u) for u in urls_images], contenu['legende'])
            print("Instagram : carrousel de 5 images pret.")
        reponse_ig = publier_conteneur_instagram(ig_user_id, page_token, parent)
        print(f"Instagram publie : {reponse_ig}")

    if 'cle_etat' in contenu:
        etat = lire_etat_publication()
        etat[contenu['cle_etat']] = contenu['valeur_etat']
        ecrire_etat_publication(etat)
        print(f"Etat mis a jour : {contenu['cle_etat']} = {contenu['valeur_etat']}")


if __name__ == '__main__':
    sys.exit(main())
