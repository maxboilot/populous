"""Bande son des Reels : intro piano doux (synthese numpy, original) sur la 1re scene, puis l'extrait d'instru (assets/audio/instru_max.mp3)
qui entre sur le changement de scene. Si l'instru est absent ou si la fabrication echoue, on garde la bande son synthetisee (bande_son.wav).
Usage (appele par generer_reel.py) : musique.preparer(projet, duree_scene_1)"""
import subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np

SR = 44100
ICI = Path(__file__).resolve().parent
INSTRU = ICI / 'assets' / 'audio' / 'instru_max.mp3'


def _piano(m, d, vel, rng):
    n = int(d * SR); t = np.arange(n) / SR; f = 440.0 * 2 ** ((m - 69) / 12); y = np.zeros(n)
    for k in range(1, 9):                                    # partiels legerement inharmoniques, plus brefs dans l'aigu
        fk = f * k * np.sqrt(1 + 0.00035 * k * k)
        if fk > 9000: break
        y += (1 / k ** 1.25) * np.sin(2 * np.pi * fk * t + k) * np.exp(-t * (1.1 + 0.55 * k + (m - 40) * 0.012))
    y += rng.standard_normal(n) * np.exp(-t * 70) * 0.05     # bruit du marteau
    return y * np.minimum(1, t / 0.004) * vel


def intro_piano(T, sortie):
    """Arpege doux re-la-do-fa (compatible fa majeur / re mineur) sur T secondes, queue qui s'eteint apres l'entree du beat."""
    rng = np.random.default_rng(7); L = int((T + 1.8) * SR); mix = np.zeros(L)
    notes = [(0.00, 38, .50), (0.30, 57, .42), (0.75, 60, .42), (1.20, 65, .46), (1.65, 69, .40), (2.15, 72, .34)]
    tfin = max(2.3, T - 1.0); notes += [(tfin, 53, .40), (tfin + 0.04, 60, .34), (tfin + 0.09, 69, .30)]
    for t0, m, v in notes:
        p = _piano(m, 3.2, v, rng); i = int(t0 * SR); s = p[: L - i]; mix[i:i + len(s)] += s
    y = mix.copy()
    for dt, g in [(0.071, .32), (0.113, .26), (0.167, .2), (0.241, .15), (0.331, .1), (0.463, .07)]:   # reverb douce
        d = int(dt * SR); z = np.zeros(L); z[d:] = mix[:-d]; acc = 0.0
        for i in range(L): acc += 0.35 * (z[i] - acc); z[i] = acc
        y += z * g
    k = int((T + 0.2) * SR); y[k:] *= np.linspace(1, 0, L - k) ** 1.5
    y *= 0.30 / max(abs(y).max(), 1e-9)
    with wave.open(str(sortie), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())


def preparer(projet, duree_scene1):
    """Ecrit projet/assets/audio/bande_son.wav (60 s). Renvoie True si l'instru a ete utilise, False si on garde la bande son synthetisee."""
    if not INSTRU.exists():
        return False
    T = float(duree_scene1); sortie = Path(projet) / 'assets' / 'audio' / 'bande_son.wav'
    try:
        with tempfile.TemporaryDirectory(prefix='piano-') as tmp:
            piano = Path(tmp) / 'piano.wav'; intro_piano(T, piano); ms = int(T * 1000); mix = Path(tmp) / 'mix.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(piano), '-i', str(INSTRU), '-filter_complex',
                f'[0:a]aformat=sample_rates=44100:channel_layouts=stereo[p];'
                f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=7,afade=t=in:d=0.06,adelay={ms}|{ms},aformat=sample_rates=44100:channel_layouts=stereo[b];'
                f'[p][b]amix=inputs=2:normalize=0:duration=longest,atrim=0:60[a]', '-map', '[a]', '-ar', '44100', '-ac', '2', str(mix)],
                check=True, capture_output=True, text=True)
            if mix.stat().st_size < 100000: raise RuntimeError('bande son vide')
            sortie.write_bytes(mix.read_bytes())
        return True
    except Exception as e:                                   # jamais de Reel perdu pour un probleme de musique
        print(f'[musique] instru ignore, bande son synthetisee conservee : {e}', file=sys.stderr)
        return False
