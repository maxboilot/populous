#!/usr/bin/env python3
"""Génère le carrousel d'un post Populous avec HyperFrames (HTML + GSAP rendu en vidéo).

Un carrousel = 5 slides 1080x1350 (4:5) qui forment UNE bande continue : le fond change de couleur sans couture
et un élément traverse chaque frontière entre deux slides. Pour chaque type de post on produit :
  - slide_1.mp4 … slide_5.mp4   chaque slide animée (Instagram : carrousel de vidéos, chaque slide démarre quand on arrive dessus)
  - slide_1.png … slide_5.png   l'image finale de chaque slide (Facebook : diaporama ; repli d'Instagram)
  - apercu_swipe.mp4            la bande entière avec une caméra qui glisse de slide en slide

Contenu RÉEL uniquement : tout vient de data/, elus.json et index.html du dépôt (cf. CLAUDE.md). Aucune photo distante,
aucun appel réseau pendant le rendu (GSAP et polices sont dans le dépôt).

Prérequis : Node >= 22 (npx), FFmpeg, Chrome/Chromium, Python 3 + Pillow. HyperFrames est lancé via `npx hyperframes@0.8.222`.
Usage : python3 carrousels/generer_carrousel.py --type fait|depute|avenir|boussole|vote|loi|presidentiel --sortie DOSSIER [options]
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
REPO = ICI.parent
MOTEUR = ICI / 'moteur'
HYPERFRAMES = 'hyperframes@0.8.222'          # version figée : un rendu reste identique avec le temps
TYPES = ('fait', 'depute', 'avenir', 'boussole', 'vote', 'loi', 'presidentiel')
IMAGE_FINALE_S = 6.2                         # les slides durent 6,5 s ; on prend l'état final de l'animation


def _lancer(cmd, cwd, env, quoi):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{quoi} a échoué (code {r.returncode}) :\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}")
    return r.stdout


def generer(type_, sortie, *, mmjj=None, depute=None, scrutin=None, titre_vote=None, explication=None, source_explication=None, garder_travail=False):
    """Rend le carrousel du type demandé dans le dossier `sortie`. Renvoie
    {'slides_mp4': [...], 'slides_png': [...], 'apercu': Path}. Lève RuntimeError au moindre échec (jamais de demi-carrousel)."""
    if type_ not in TYPES:
        raise ValueError(f"type inconnu : {type_}")
    sortie = Path(sortie); sortie.mkdir(parents=True, exist_ok=True)
    travail = Path(tempfile.mkdtemp(prefix=f'carrousel-{type_}-'))
    try:
        shutil.copytree(MOTEUR / 'commun', travail / 'commun')
        projet = travail / type_
        shutil.copytree(MOTEUR / type_, projet)
        (projet / 'meta.json').write_text(f'{{"id":"carrousel-{type_}","name":"carrousel-{type_}"}}', encoding='utf-8')
        assets = projet / 'assets'; (assets / 'fonts').mkdir(parents=True)
        for police in ('ExtraBold', 'Bold', 'Medium'):
            shutil.copy(REPO / 'assets_social' / 'fonts' / f'PlusJakartaSans-{police}.ttf', assets / 'fonts')
        shutil.copy(MOTEUR / 'commun' / 'gsap.min.js', assets / 'gsap.min.js')
        if type_ == 'depute':
            shutil.copy(REPO / 'assets_social' / 'atlas_portraits.webp', assets / 'atlas_portraits.webp')

        env = {**os.environ, 'POPULOUS_REPO': str(REPO)}
        extra = []
        if type_ == 'fait':
            extra = [mmjj or datetime.date.today().strftime('%m-%d')]
        if type_ == 'depute':
            extra = [depute] if depute else []
        if type_ in ('depute', 'vote', 'loi', 'boussole'):
            if scrutin is None and type_ != 'boussole':
                raise RuntimeError(f"--type {type_} exige un numéro de scrutin.")
            if scrutin is not None:
                sys.path.insert(0, str(MOTEUR / 'commun'))
                import exporter_sieges
                exporter_sieges.REPO = REPO
                exporter_sieges.exporter(scrutin, travail / 'sieges.json')
            else:      # boussole : la géométrie de l'hémicycle suffit ; on prend le scrutin le plus récent du dépôt
                dernier = max((p for p in (REPO / 'data' / 'scrutins').glob('*.json')), key=lambda p: int(p.stem))
                sys.path.insert(0, str(MOTEUR / 'commun'))
                import exporter_sieges
                exporter_sieges.REPO = REPO
                exporter_sieges.exporter(int(dernier.stem), travail / 'sieges.json')
            env['SIEGES_JSON'] = str(travail / 'sieges.json')
        if titre_vote:
            env['TITRE_VOTE'] = titre_vote
        if explication:
            env['EXPLICATION_LOI'] = explication            # JSON : [[titre, texte], ...] relu par un humain
            env['SOURCE_EXPLICATION'] = source_explication or ''

        def rendre(nom_sortie):
            _lancer(['npx', '--yes', HYPERFRAMES, 'render', '-w', '2', '-q', 'looks', '-o', f'sortie/{nom_sortie}.mp4'], projet, env, f'rendu de {nom_sortie}')

        (projet / 'sortie').mkdir()
        slides_mp4, slides_png = [], []
        for i in range(5):
            _lancer([sys.executable, 'construire.py', 'slide', str(i), *extra], projet, env, f'construction de la slide {i + 1}')
            rendre(f'slide_{i + 1}')
            mp4, png = projet / 'sortie' / f'slide_{i + 1}.mp4', projet / 'sortie' / f'slide_{i + 1}.png'
            _lancer(['ffmpeg', '-v', 'error', '-y', '-ss', str(IMAGE_FINALE_S), '-i', str(mp4), '-frames:v', '1', str(png)], projet, env, f'image fixe de la slide {i + 1}')
            slides_mp4.append(mp4); slides_png.append(png)
        _lancer([sys.executable, 'construire.py', 'preview', *extra], projet, env, "construction de l'aperçu")
        rendre('apercu_swipe')

        resultat = {'slides_mp4': [], 'slides_png': [], 'apercu': sortie / 'apercu_swipe.mp4'}
        for chemin in slides_mp4 + slides_png + [projet / 'sortie' / 'apercu_swipe.mp4']:
            shutil.copy(chemin, sortie / chemin.name)
        resultat['slides_mp4'] = [sortie / p.name for p in slides_mp4]
        resultat['slides_png'] = [sortie / p.name for p in slides_png]
        for p in resultat['slides_mp4'] + resultat['slides_png'] + [resultat['apercu']]:
            if not p.exists() or p.stat().st_size < 2000:
                raise RuntimeError(f"fichier de carrousel manquant ou vide : {p}")
        return resultat
    finally:
        if not garder_travail:
            shutil.rmtree(travail, ignore_errors=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--type', choices=TYPES, required=True)
    p.add_argument('--sortie', required=True)
    p.add_argument('--mmjj', help="(fait) jour au format MM-JJ, défaut : aujourd'hui")
    p.add_argument('--depute', help="(depute) nom complet")
    p.add_argument('--scrutin', type=int, help="(depute, vote) numéro du scrutin")
    p.add_argument('--titre-vote', help="(vote, loi) titre synthétique relu par un humain")
    p.add_argument('--explication', help="(loi) JSON [[titre, texte], ...] : 2 ou 3 blocs « de quoi parle ce texte », relus par un humain")
    p.add_argument('--source-explication', help="(loi) source citée sous l'explication")
    a = p.parse_args()
    r = generer(a.type, a.sortie, mmjj=a.mmjj, depute=a.depute, scrutin=a.scrutin, titre_vote=a.titre_vote, explication=a.explication, source_explication=a.source_explication)
    print('OK', *[str(x) for x in r['slides_png']], r['apercu'], sep='\n')
