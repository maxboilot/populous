"""Bande son des Reels : instru (extrait de 52,6 s, chiffre dans le depot public) cale sur les temps du morceau.
Structure : 1er visuel = partie calme ; des le 2e visuel = groove complet (caisses claires) qui entre par un filtre qui s'ouvre ;
le volume baisse sur la fin du dernier visuel de contenu ; silence de 0,9 s ; reprise du groove sur la carte Populous (zoom).
Grille mesuree sur le morceau : 109,93 BPM (temps = 0,5458 s), reprise a 78,856 s (temps fort), partie calme = les 28 temps avant la reprise.
Sans l'extrait (ou si un cas sort des limites du morceau), generer_reel.py garde la bande son synthetisee : jamais de Reel perdu pour la musique."""
import json, math, subprocess, wave
from pathlib import Path
import numpy as np
import lecture

SR = 44100; B = 0.5458; R = 78.856            # temps (s) ; instant de la reprise dans le morceau d'origine
EXT0 = 65.476                                  # position, dans le morceau d'origine, du debut de l'extrait (65,5 s moins le retard de l'encodeur MP3 : 24 ms)
PAUSE = 0.9; FONDU = 1.4                       # silence avant la carte Populous ; baisse de volume avant la fin du dernier visuel de contenu (s)
MAX_N2, MAX_GROOVE = 16, 66                    # limites de l'extrait : temps du 1er visuel / temps de groove disponibles
ICI = Path(__file__).resolve().parent
INSTRU = ICI / 'assets' / 'audio' / 'instru2.mp3'


def disponible(): return INSTRU.exists()


def caler(sc):
    """Durees des scenes : au moins le temps de lecture (lecture.py), arrondies au temps superieur du morceau (chaque scene >= 4 temps).
    Renvoie (scenario, n2, ne) : n2 = temps du 1er visuel, ne = temps de fin des visuels de contenu. ValueError si le Reel sort des limites du morceau."""
    sc = json.loads(json.dumps(sc)); ends, prev = [], 0
    for x in sc['scenes']:
        e = prev + max(4, math.ceil(max(float(x.get('duree', 4)), lecture.duree_min(x)) / B - 1e-6)); ends.append(e); prev = e
    n2, ne = ends[0], ends[-1]
    if len(ends) < 2 or n2 > MAX_N2 or ne - n2 > MAX_GROOVE: raise ValueError(f'Reel hors limites du morceau (1er visuel {n2} temps, groove {ne - n2} temps)')
    prev = 0
    for x, e in zip(sc['scenes'], ends): x['duree'] = round((e - prev) * B, 4); prev = e
    sc['effet_fin'] = 'zoom'; sc['pause_fin'] = PAUSE
    return sc, int(n2), int(ne)


def charger():
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(INSTRU), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def _passe_bas(x, fc):
    F = np.fft.rfftfreq(len(x), 1 / SR); return np.fft.irfft(np.fft.rfft(x, axis=0) / (1 + (F / fc) ** 4)[:, None], len(x), axis=0)


def _lisser(seg, n_visuel1):
    """Partie calme : niveau regularise (compression douce sur 0,4 s) puis montee continue de 70 % a 100 % jusqu'au groove."""
    w = int(0.4 * SR); mono = seg.mean(1); env = np.sqrt(np.convolve(mono ** 2, np.ones(w) / w, 'same')) + 1e-4
    g = np.clip((np.median(env) / env) ** 0.6, 0.6, 1.6); g = np.convolve(g, np.ones(w) / w, 'same')
    return seg * (g * np.interp(np.arange(len(seg)), [0, n_visuel1], [0.70, 1.0]))[:, None]


def _ouvrir(groove):
    """Le groove entre filtre (passe-bas 900 Hz) et s'ouvre en ~1,1 s, niveau de 75 % a 100 %."""
    n = int(1.1 * SR); w = np.zeros(len(groove)); w[:n] = np.linspace(0, 1, n) ** 1.5; w[n:] = 1.0; w = w * w * (3 - 2 * w)
    out = _passe_bas(groove, 900) * (1 - w)[:, None] + groove * w[:, None]
    return out * np.interp(np.arange(len(groove)), [0, n], [0.75, 1.0], right=1.0)[:, None]


def piste(X, n2, ne, duree_totale, fin_d=3.8):
    T = lambda s: int(round((s - EXT0) * SR)); tb = lambda k: int(round(k * B * SR)); p = int(PAUSE * SR)
    cal_fin, g0 = T(R - 8 * B), T(R)               # la partie calme se termine sur une frontiere de mesure : le groove entre en phase
    out = np.zeros((int(duree_totale * SR) + SR, 2))
    def poser(seg, at, fade_in=0, fade_out=0):
        seg = seg.copy()
        if fade_in: seg[:fade_in] *= np.sin(np.linspace(0, np.pi / 2, fade_in))[:, None]
        if fade_out: seg[-fade_out:] *= np.cos(np.linspace(0, np.pi / 2, fade_out))[:, None]
        out[at:at + len(seg)] += seg
    tr = int(0.3 * SR)
    poser(_lisser(X[cal_fin - tb(n2):cal_fin + tr], tb(n2)), 0, fade_in=int(0.5 * SR), fade_out=tr)
    groove = X[g0:g0 + tb(ne - n2)]
    if len(groove) != tb(ne - n2): raise ValueError('groove trop long pour l\'extrait')
    poser(_ouvrir(groove), tb(n2), fade_out=int(FONDU * SR))                  # le volume descend jusqu'a la fin du contenu
    poser(X[g0 - p:g0], tb(ne), fade_in=int(0.03 * SR))                       # le silence d'origine (ambiance de la salle)
    reprise = X[g0:g0 + int((fin_d + 1.0) * SR)]
    if len(reprise) < int((fin_d + 0.5) * SR): raise ValueError('reprise trop courte')
    poser(reprise, tb(ne) + p)                                                 # reprise = carte Populous
    return out[: int(duree_totale * SR)]


def monter(brut, sortie, duree, fin_d=3.8, n2=0, ne=0, tmp=None):
    """Fabrique la piste, la colle sur les images de `brut` (copie du flux video) et ecrit `sortie` (AAC, niveau -17 LUFS, limiteur)."""
    tmp = Path(tmp or Path(sortie).parent); wav = tmp / '_son_reel.wav'
    y = piste(charger(), n2, ne, duree + 0.1, fin_d)
    with wave.open(str(wav), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(brut), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
                        '-af', f'acompressor=threshold=0.16:ratio=2:attack=25:release=300,loudnorm=I=-17:TP=-2.5:LRA=14,afade=t=out:st={duree - 0.8:.2f}:d=0.8,atrim=0:{duree:.2f},alimiter=limit=0.66:level=disabled',
                        '-t', f'{duree:.2f}', '-movflags', '+faststart', str(sortie)], check=True, capture_output=True, text=True)
    finally:
        wav.unlink(missing_ok=True)
