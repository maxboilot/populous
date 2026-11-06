"""Bande son des Reels (60 s, mono 22,05 kHz) : nappe d'accords + pouls discret + arpege. Tout est synthetise (numpy), aucune musique tierce.
Usage : python3 -I fabriquer_son.py  ->  assets/audio/bande_son.wav (les Reels la coupent a leur duree)."""
import wave
from pathlib import Path
import numpy as np
SR, DUR, BPM = 22050, 60.0, 100; B = 60 / BPM
N = int(SR * DUR); out = np.zeros(N); rng = np.random.default_rng(5)
def add(t0, sig, g=1.0):
    i = int(t0 * SR)
    if i >= N: return
    sig = sig[: N - i]; out[i:i + len(sig)] += sig * g
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def tri(f, d, a=0.02, dec=1.0):
    n = int(d * SR); t = np.arange(n) / SR
    return 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t)) * np.minimum(1, t / a) * np.exp(-t / dec)
def kick():
    n = int(0.25 * SR); t = np.arange(n) / SR; f = 48 + 80 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 12)
def hat():
    n = int(0.04 * SR); x = rng.standard_normal(n); return np.diff(x, prepend=0) * np.exp(-np.arange(n) / SR * 90)
ACC = [(45, 57, 60, 64), (41, 53, 57, 60), (48, 60, 64, 67), (43, 55, 59, 62)]
for k in range(int(DUR / (4 * B)) + 1):
    t0 = k * 4 * B
    for j, m in enumerate(ACC[k % 4]):
        n = int(4 * B * SR); t = np.arange(n) / SR; s = tri(hz(m), 4 * B + 0.4, 0.4, 3.0)[:n] * np.minimum(1, (4 * B - t) / 0.4 + 0.0)
        add(t0, s, 0.05 if j else 0.08)
for b in range(int(DUR / B)):
    add(b * B, kick(), 0.30 if b >= 4 else 0.0); add(b * B + B / 2, hat(), 0.07 if b >= 4 else 0.0)
PEN = [69, 72, 74, 76, 79, 81]; arp = [0, 2, 1, 3, 2, 4, 3, 5]; t = 2.4; i = 0
while t < DUR - 1:
    add(t, tri(hz(PEN[arp[i % 8]]), 0.3, 0.003, 0.16), 0.07); t += B / 2; i += 1
out = np.tanh(out * 1.2); out /= max(abs(out).max(), 1e-9); out *= 0.55
out[-int(SR * 1.0):] *= np.linspace(1, 0, int(SR * 1.0))
dest = Path(__file__).parent / "assets" / "audio" / "bande_son.wav"
with wave.open(str(dest), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())
print("bande son :", dest, f"{DUR:.0f} s", round(dest.stat().st_size / 1e6, 2), "Mo")
