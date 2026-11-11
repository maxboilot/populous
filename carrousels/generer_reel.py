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


try:
    import marseillaise
except Exception as e:                                          # numpy absent, etc. : bande son synthetisee
    marseillaise = None; print(f'[marseillaise] module indisponible, bande son synthetisee : {e}', file=sys.stderr)


def _marseillaise_possible(scenario):
    """Reel commemoratif (« musique »: « marseillaise ») : la musique impose ses mesures (2,88 s) ; les scenes doivent durer chacune un nombre entier de mesures
    et au moins leur temps de lecture, sinon la bande son synthetisee est conservee."""
    if scenario.get('musique') != 'marseillaise' or marseillaise is None or not marseillaise.disponible():
        return False
    sys.path.insert(0, str(MOTEUR / 'reel')); import lecture
    for x in scenario['scenes']:
        d = float(x.get('duree', 0)); k = d / marseillaise.MESURE
        if abs(k - round(k)) > 0.01 or d + 0.01 < lecture.duree_min(x):
            print(f'[marseillaise] scene « {x["type"]} » de {d:.2f} s hors mesure ou trop courte pour etre lue : bande son synthetisee conservee', file=sys.stderr); return False
    return True


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
        marseillaise_ok = _marseillaise_possible(scenario)
        scenario, instru, n2, ne = (scenario, False, 0, 0) if marseillaise_ok else _caler_sur_la_musique(scenario)
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
        if marseillaise_ok:
            try:
                marseillaise.monter(brut, reel, duree, tmp=travail); monte = True
            except Exception as e:
                print(f'[marseillaise] musique ignoree, bande son synthetisee conservee : {e}', file=sys.stderr)
        elif instru:
            try:
                musique.monter(brut, reel, duree, float(scenario.get('fin', {}).get('duree', 3.8)), n2, ne, tmp=travail); monte = True
            except Exception as e:                                  # jamais de Reel perdu pour un probleme de musique
                print(f'[musique] instru ignore, bande son synthetisee conservee : {e}', file=sys.stderr)
        if not monte:
            _lancer(['ffmpeg', '-v', 'error', '-y', '-i', str(brut), '-c:v', 'copy', '-af', f'afade=t=out:st={max(duree - 0.8, 0):.2f}:d=0.8', '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-b:a', '160k', '-movflags', '+faststart', str(reel)], projet, env, 'fondu sonore')
        _lancer(['ffmpeg', '-v', 'error', '-y', '-ss', str(scenario.get('couverture_s', 2.6)), '-i', str(brut), '-frames:v', '1', str(couverture)], projet, env, 'couverture')
        pb = problemes_de_conformite(reel)
        if pb:                                                      # filet de securite : un Reel hors normes est reencode ici plutot que refuse par Instagram a 18 h
            print(f'[conformite] {"; ".join(pb)} -> reencodage', file=sys.stderr)
            rendre_conforme(reel, travail)
        for p in (reel, couverture):
            if not p.exists() or p.stat().st_size < 2000:
                raise RuntimeError(f'fichier de reel manquant ou vide : {p}')
        return {'reel': reel, 'couverture': couverture, 'duree': duree}
    finally:
        if not garder_travail:
            shutil.rmtree(travail, ignore_errors=True)


def problemes_de_conformite(chemin):
    """Ecarts entre la video et ce que Meta accepte sans broncher (H.264 yuv420p, AAC stereo 44,1/48 kHz, <= 60 i/s, <= 90 s). Liste vide = conforme.
    Ne leve jamais : si ffprobe est absent ou illisible, renvoie []. Ne remplace pas un essai reel, mais evite les causes connues de refus."""
    try:
        sortie = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(chemin)], capture_output=True, text=True, check=True, timeout=60).stdout
        infos = json.loads(sortie)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    video = next((x for x in infos.get('streams', []) if x.get('codec_type') == 'video'), None)
    audio = next((x for x in infos.get('streams', []) if x.get('codec_type') == 'audio'), None)
    pb = []
    if not video or video.get('codec_name') != 'h264' or video.get('pix_fmt') != 'yuv420p':
        pb.append('video : H.264 yuv420p attendu')
    else:
        num, _, den = (video.get('r_frame_rate') or '0/1').partition('/')
        if float(num or 0) / float(den or 1) > 60:
            pb.append('video : plus de 60 images/s')
    if not audio:
        pb.append('pas de piste son')
    elif audio.get('codec_name') != 'aac' or int(audio.get('sample_rate') or 0) not in (44100, 48000) or int(audio.get('channels') or 0) not in (1, 2):
        pb.append(f"son : AAC 44,1/48 kHz mono/stereo attendu (lu : {audio.get('codec_name')} {audio.get('sample_rate')} Hz, {audio.get('channels')} canaux)")
    if float((infos.get('format') or {}).get('duration') or 0) > 90:
        pb.append('duree : plus de 90 s')
    return pb


def rendre_conforme(chemin, tmp):
    """Reencode `chemin` (en place) aux normes de Meta : video recodee en H.264 yuv420p 30 i/s, son AAC stereo 44,1 kHz."""
    cible = Path(tmp) / 'conforme.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(chemin), '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-r', '30', '-crf', '21',
                    '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-b:a', '160k', '-movflags', '+faststart', str(cible)], check=True, capture_output=True, text=True)
    shutil.move(str(cible), str(chemin))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--scenario', required=True); ap.add_argument('--sortie', required=True); ap.add_argument('--scrutin', type=int)
    a = ap.parse_args()
    r = generer(json.loads(Path(a.scenario).read_text(encoding='utf-8')), a.sortie, scrutin=a.scrutin)
    print('OK', r['reel'], f"{r['duree']:.1f} s")
