"""Bande son « La Marseillaise au violon » des Reels commemoratifs : tout est synthetise (numpy), aucune musique tierce.
Melodie et accompagnement : fichier MIDI « Allons, enfants de la patrie » de Rabanus Flavus (Peter Gerloff), Wikimedia Commons, licence CC0 (domaine public mondial) ;
la melodie date de 1792 (Rouget de Lisle). Arrangement : violon solo (vibrato, archet), nappe de cordes, violoncelle, reverberation. Tempo choisi pour que les scenes
du Reel tombent sur les temps : B = 0,72 s (83 BPM), mesure = 4 temps = 2,88 s.
Structure : 1 mesure d'introduction (nappe seule) ; vers 1 (deux premieres phrases, 8 mesures) ; refrain (« Aux armes, citoyens », 6 mesures) ; accord final tenu.
Sans le fichier MIDI ou numpy, generer_reel.py garde la bande son synthetisee : jamais de Reel perdu pour la musique."""
import struct, subprocess, wave
from pathlib import Path
import numpy as np

SR = 44100
B = 0.72                                        # duree d'un temps (s)
MESURE = 4 * B
INTRO = MESURE                                  # nappe seule avant le violon
SEG1 = (0.0, 32.0)                              # temps MIDI : « Allons enfants… » et « Contre nous de la tyrannie… »
SEG2 = (88.0, 112.0)                            # temps MIDI : refrain « Aux armes, citoyens… »
ICI = Path(__file__).resolve().parent
MIDI = ICI / 'assets' / 'audio' / 'marseillaise.mid'


def disponible(): return MIDI.exists()


def _lire_midi(path):
    d = Path(path).read_bytes(); n, div = struct.unpack('>HH', d[10:14]) if False else (struct.unpack('>H', d[10:12])[0], struct.unpack('>H', d[12:14])[0]); pos = 14; pistes = []
    for _ in range(n):
        ln = struct.unpack('>I', d[pos + 4:pos + 8])[0]; tr = d[pos + 8:pos + 8 + ln]; pos += 8 + ln; i = 0; t = 0; run = None; notes = []; act = {}
        def vlq():
            nonlocal i
            v = 0
            while True:
                b = tr[i]; i += 1; v = (v << 7) | (b & 0x7f)
                if not b & 0x80: return v
        while i < len(tr):
            t += vlq(); b = tr[i]
            if b == 0xff: i += 2; l = vlq(); i += l; continue
            if b in (0xf0, 0xf7): i += 1; l = vlq(); i += l; continue
            if b & 0x80: run = b; i += 1
            k = run & 0xf0
            if k in (0xc0, 0xd0): i += 1; continue
            v1, v2 = tr[i], tr[i + 1]; i += 2
            if k == 0x90 and v2 > 0: act[(run & 15, v1)] = t
            elif k == 0x80 or (k == 0x90 and v2 == 0):
                if (run & 15, v1) in act: t0 = act.pop((run & 15, v1)); notes.append((t0 / div, (t - t0) / div, v1))
        pistes.append(sorted(notes))
    return pistes


def _hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def _t(m):
    """Temps MIDI -> secondes dans le Reel, ou None si hors des deux passages joues."""
    if SEG1[0] <= m < SEG1[1]: return INTRO + (m - SEG1[0]) * B
    if SEG2[0] <= m < SEG2[1]: return INTRO + (SEG1[1] - SEG1[0]) * B + (m - SEG2[0]) * B
    return None


def fin_refrain(): return INTRO + ((SEG1[1] - SEG1[0]) + (111.5 - SEG2[0])) * B       # fin de la derniere note de la melodie (s)


def _violon(f0, d, vel=1.0, rng=None):
    """Une note de violon : archet doux, vibrato qui s'installe, harmoniques decroissantes, souffle d'archet."""
    n = int(d * SR); t = np.arange(n) / SR; rng = rng or np.random.default_rng(1)
    vib = np.clip((t - 0.22) / 0.35, 0, 1) * 0.0125 * (d > 0.45)                       # profondeur ~ +/- 0,22 demi-ton
    f = f0 * (1 + rng.uniform(-0.0015, 0.0015)) * (1 + vib * np.sin(2 * np.pi * 5.4 * t + rng.uniform(0, 6.28)))
    ph = 2 * np.pi * np.cumsum(f) / SR; y = np.zeros(n)
    for k in range(1, 15):
        if f0 * k > 8000: break
        y += np.sin(k * ph) * k ** -1.15 * (1 + 0.5 * np.sin(k * 0.9))
    att = min(0.09, d * 0.3); rel = min(0.14, d * 0.4)
    env = np.minimum(1, t / att) * np.minimum(1, (d - t) / rel) * (0.88 + 0.12 * np.sin(np.pi * np.clip(t / d, 0, 1)))
    bruit = np.diff(rng.standard_normal(n + 1)); bruit = np.convolve(bruit, np.ones(3) / 3, 'same')
    return (y * 0.45 + bruit * 0.035) * env * vel


def _corde(f0, d, att=0.16, rel=0.3, dent=0.003, harm=9, rng=None):
    """Note de nappe de cordes (plusieurs archets legerement desaccordes)."""
    n = int(d * SR); t = np.arange(n) / SR; y = np.zeros(n); rng = rng or np.random.default_rng(2)
    for dc in (-dent, 0.0, dent):
        ph = 2 * np.pi * np.cumsum(np.full(n, f0 * (1 + dc) * (1 + 0.004 * np.sin(2 * np.pi * 4.8 * t + rng.uniform(0, 6.28))))) / SR
        for k in range(1, harm + 1): y += np.sin(k * ph) * k ** -1.4
    return y / 3 * np.minimum(1, t / att) * np.minimum(1, np.maximum(d - t, 0) / rel)


def _egaliser(x, courbe):
    F = np.fft.rfftfreq(len(x), 1 / SR); G = courbe(F)
    return np.fft.irfft(np.fft.rfft(x) * G, len(x))


def _corps_violon(F):                          # resonances du corps du violon + coupure des aigus
    return (1 + 0.5 * np.exp(-((F - 500) / 160) ** 2) + 0.9 * np.exp(-((F - 1500) / 450) ** 2) + 1.0 * np.exp(-((F - 3000) / 900) ** 2)) / (1 + (F / 7500) ** 4)


def _reverb(x, duree=2.6, humide=0.30, seed=3):
    rng = np.random.default_rng(seed); n = int(duree * SR); t = np.arange(n) / SR; out = np.zeros((len(x), 2))
    for c in (0, 1):
        ir = rng.standard_normal(n) * np.exp(-t / 0.75); ir *= np.minimum(1, t / 0.012)
        for dly, g in ((0.021, .5), (0.037, .4), (0.053, .3), (0.071, .22)): ir[int(dly * SR) + c * 37] += g * 6
        F = np.fft.rfftfreq(n, 1 / SR); ir = np.fft.irfft(np.fft.rfft(ir) / (1 + (F / 4200) ** 2), n)          # les aigus s'eteignent plus vite
        ir /= np.sqrt((ir ** 2).sum())
        L = len(x) + n; w = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[: len(x)]
        out[:, c] = x * (1 - humide) + w * humide * 1.6
    return out


def piste(duree_totale):
    """Piste stereo (numpy, SR Hz) de `duree_totale` secondes : la derniere note de la melodie se termine a fin_refrain() ; l'accord final se prolonge puis s'eteint."""
    P = _lire_midi(MIDI); melodie, accomp = P[1], P[4]
    n = int((duree_totale + 3.0) * SR); vl = np.zeros(n); cd = np.zeros(n); vc = np.zeros(n); rng = np.random.default_rng(7)
    def poser(buf, t0, sig, g):
        i = int(t0 * SR)
        if i < 0 or i >= n: return
        sig = sig[: n - i]; buf[i:i + len(sig)] += sig * g
    for m0, d, p in melodie:                                              # violon solo
        t0 = _t(m0)
        if t0 is None: continue
        dur = d * B + (0.09 if d * B > 0.3 else 0.03)
        poser(vl, t0, _violon(_hz(p), dur, rng=rng), 1.0)
    for m0, d, p in accomp:                                               # nappe + violoncelle
        t0 = _t(m0)
        if t0 is None or m0 >= 31.9 and m0 < 88: continue
        dur = d * B + 0.25
        if p <= 48: poser(cd, t0, _corde(_hz(p), dur + 0.25, att=0.10, rel=0.35, harm=6, rng=rng), 1.15)
        else: poser(vc, t0, _corde(_hz(p), dur, att=0.18, rel=0.4, rng=rng), 0.62)
    fin = fin_refrain()                                                   # introduction (nappe seule) et accord final tenu
    for p, g, buf in ((43, 1.15, cd), (50, 0.8, vc), (55, 0.8, vc), (59, 0.7, vc)):
        poser(buf, 0.0, _corde(_hz(p), INTRO + 0.6, att=INTRO * 0.8, rel=0.5, rng=rng) * 0.9, g)
    for p, g, buf in ((43, 1.15, cd), (55, 0.9, cd), (50, 0.8, vc), (59, 0.8, vc), (62, 0.7, vc), (67, 0.7, vc)):
        poser(buf, fin - 0.25, _corde(_hz(p), duree_totale - fin + 1.2, att=0.35, rel=1.2, rng=rng), g)
    poser(vl, fin - 0.05, _violon(_hz(67), duree_totale - fin + 0.6, rng=rng), 0.8)              # le violon tient la tonique jusqu'a la fin
    vl = _egaliser(vl, _corps_violon); cd = _egaliser(cd, lambda F: 1 / (1 + (F / 600) ** 2)); vc = _egaliser(vc, lambda F: 1 / (1 + (F / 2400) ** 2))
    mix = _reverb(vl * 0.95 + vc * 0.55 + cd * 0.45)
    mix = mix[: int(duree_totale * SR)]; mix /= max(np.abs(mix).max(), 1e-9); mix *= 0.7
    k = int(0.5 * SR); mix[:k] *= np.linspace(0, 1, k)[:, None]
    return mix


def monter(brut, sortie, duree, tmp=None):
    """Fabrique la piste, la colle sur les images de `brut` (copie du flux video) et ecrit `sortie` (AAC, niveau -17 LUFS, limiteur)."""
    tmp = Path(tmp or Path(sortie).parent); wav = tmp / '_son_marseillaise.wav'
    y = piste(duree + 0.1)
    with wave.open(str(wav), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(brut), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-b:a', '256k',
                        '-af', f'loudnorm=I=-17:TP=-2.5:LRA=14,afade=t=out:st={duree - 1.2:.2f}:d=1.2,atrim=0:{duree:.2f},alimiter=limit=0.66:level=disabled',
                        '-t', f'{duree:.2f}', '-movflags', '+faststart', str(sortie)], check=True, capture_output=True, text=True)
    finally:
        wav.unlink(missing_ok=True)
