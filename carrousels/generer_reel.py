#!/usr/bin/env python3
"""Rend un Reel vertical (1080x1920, avec bande son) avec HyperFrames, a partir d'un scenario JSON (voir moteur/reel/construire.py).
Sortie : reel.mp4 (son coupe en fondu a la fin) + couverture.png (image de la 1re scene terminee).
Usage : python3 carrousels/generer_reel.py --scenario scenario.json --sortie DOSSIER [--scrutin N]   (Node >= 22, FFmpeg, Chrome)"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
REPO = ICI.parent
MOTEUR = ICI / 'moteur'
sys.path.insert(0, str(ICI))
from generer_carrousel import HYPERFRAMES, _lancer          # meme version figee de HyperFrames, meme gestion d'erreur


sys.path.insert(0, str(MOTEUR / 'reel'))
try:
    import musique
except Exception as e:                                          # numpy absent, etc. : on garde la bande son synthetisee
    musique = None; print(f'[musique] module indisponible, bande son synthetisee : {e}', file=sys.stderr)


def _caler_sur_la_musique(scenario):
    """Si l'instru est disponible : durees alignees sur ses temps, pause et zoom avant la carte Populous. Renvoie (scenario, instru_utilise, n2, ne)."""
    if musique is not None and musique.disponible():
        try:
            sc, n2, ne = musique.caler(scenario); return sc, True, n2, ne
        except Exception as e:
            print(f'[musique] instru ignore, bande son synthetisee conservee : {e}', file=sys.stderr)
    return scenario, False, 0, 0


def generer(scenario, sortie, *, scrutin=None, garder_travail=False):
    """Renvoie {'reel': Path, 'couverture': Path, 'duree': float}. Leve RuntimeError au moindre echec (jamais de demi-reel)."""
    sortie = Path(sortie); sortie.mkdir(parents=True, exist_ok=True)
    travail = Path(tempfile.mkdtemp(prefix='reel-'))
    try:
        shutil.copytree(MOTEUR / 'commun', travail / 'commun')
        projet = travail / 'reel'
        shutil.copytree(MOTEUR / 'reel', projet)
        (projet / 'meta.json').write_text('{"id":"reel-populous","name":"reel-populous"}', encoding='utf-8')
        (projet / 'assets' / 'fonts').mkdir(parents=True, exist_ok=True)
        for police in ('ExtraBold', 'Bold', 'Medium'):
            shutil.copy(REPO / 'assets_social' / 'fonts' / f'PlusJakartaSans-{police}.ttf', projet / 'assets' / 'fonts')
        shutil.copy(MOTEUR / 'commun' / 'gsap.min.js', projet / 'assets' / 'gsap.min.js')
        scenario, instru, n2, ne = _caler_sur_la_musique(scenario)
        (travail / 'scenario.json').write_text(json.dumps(scenario, ensure_ascii=False), encoding='utf-8')
        env = {**os.environ, 'POPULOUS_REPO': str(REPO), 'REEL_SCENARIO': str(travail / 'scenario.json')}
        if scrutin is not None:
            sys.path.insert(0, str(MOTEUR / 'commun'))
            import exporter_sieges
            exporter_sieges.REPO = REPO
            exporter_sieges.exporter(scrutin, travail / 'sieges.json')
            env['SIEGES_JSON'] = str(travail / 'sieges.json')
        _lancer([sys.executable, 'construire.py'], projet, env, 'construction du reel')
        (projet / 'sortie').mkdir()
        _lancer(['npx', '--yes', HYPERFRAMES, 'render', '-w', '2', '-q', 'looks', '-o', 'sortie/brut.mp4'], projet, env, 'rendu du reel')
        brut = projet / 'sortie' / 'brut.mp4'
        duree = float(_lancer(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(brut)], projet, env, 'duree').strip())
        reel, couverture = sortie / 'reel.mp4', sortie / 'couverture.png'
        monte = False
        if instru:
            try:
                musique.monter(brut, reel, duree, float(scenario.get('fin', {}).get('duree', 3.8)), n2, ne, tmp=travail); monte = True
            except Exception as e:                                  # jamais de Reel perdu pour un probleme de musique
                print(f'[musique] instru ignore, bande son synthetisee conservee : {e}', file=sys.stderr)
        if not monte:
            _lancer(['ffmpeg', '-v', 'error', '-y', '-i', str(brut), '-c:v', 'copy', '-af', f'afade=t=out:st={max(duree - 0.8, 0):.2f}:d=0.8', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(reel)], projet, env, 'fondu sonore')
        _lancer(['ffmpeg', '-v', 'error', '-y', '-ss', '2.6', '-i', str(brut), '-frames:v', '1', str(couverture)], projet, env, 'couverture')
        for p in (reel, couverture):
            if not p.exists() or p.stat().st_size < 2000:
                raise RuntimeError(f'fichier de reel manquant ou vide : {p}')
        return {'reel': reel, 'couverture': couverture, 'duree': duree}
    finally:
        if not garder_travail:
            shutil.rmtree(travail, ignore_errors=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--scenario', required=True); ap.add_argument('--sortie', required=True); ap.add_argument('--scrutin', type=int)
    a = ap.parse_args()
    r = generer(json.loads(Path(a.scenario).read_text(encoding='utf-8')), a.sortie, scrutin=a.scrutin)
    print('OK', r['reel'], f"{r['duree']:.1f} s")
