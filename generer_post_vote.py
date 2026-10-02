#!/usr/bin/env python3
"""Genere le visuel « Vote d'hier » (1080x1350, format 4:5 feed / boost) :
la carte des 577 circonscriptions colorees comme dans l'app (memes couleurs,
memes contours), la legende Pour / Contre / Abstention / Absents et le
titre synthetique de la loi.

Usage :
    python3 generer_post_vote.py                  # dernier scrutin mis en avant
    python3 generer_post_vote.py 8441             # un scrutin precis
    python3 generer_post_vote.py 8441 --titre "Violences sexuelles et sexistes"
    python3 generer_post_vote.py --local          # lit data/ du depot local

Garde-fous editoriaux (cf. CLAUDE.md) :
  * Le titre synthetique est un BROUILLON deduit du libelle officiel ; il est
    toujours affiche dans le terminal et doit etre relu par Max (--titre pour
    le remplacer). Rien n'est publie par ce script : il ecrit seulement un PNG.
  * Le sort (adopte / rejete) est lu dans le champ officiel `sort`, JAMAIS
    dans le booleen `adopte` : ce dernier est faux dans les donnees actuelles
    ("n'a pas adopte" contient "adopt", cf. ingest_scrutins.py).
  * Le sous-titre precise la nature exacte du scrutin (sous-amendement,
    amendement, article, ensemble) pour ne pas faire passer le vote d'un
    amendement pour celui de la loi entiere.
  * Les chiffres Pour/Contre/Abstention sont ceux du decompte officiel
    (syntheseVote). « Absents » compte les CIRCONSCRIPTIONS sans vote
    exprime, c'est-a-dire ce que la carte montre en fonce.

Les donnees (scrutin, contours) sont celles de l'app : le script lit les
contours dans index.html, donc aucun fichier geographique supplementaire.
"""
import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

DOSSIER = Path(__file__).parent
sys.path.insert(0, str(DOSSIER))
import generer_visuel as gv  # noqa: E402  (polices, filigrane, carte arrondie)

RAW = 'https://raw.githubusercontent.com/maxboilot/populous/main/'
LARGEUR, HAUTEUR = 1080, 1350
SURECH = 2  # sur-echantillonnage de la carte (anti-crenelage)

# Memes valeurs que index.html (VOTE_COLORS, LAND, INK).
COULEURS = {'pour': '#1B8A6B', 'contre': '#C4501C', 'abstention': '#7C8CC4', 'absent': '#3A4470'}
LAND, INK = '#EEF2FC', '#132368'
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre']


# ---------------------------------------------------------------- donnees
def _telecharger(url):
    """curl plutot que urllib : le Python installe depuis python.org n'a pas
    les certificats du systeme (CERTIFICATE_VERIFY_FAILED)."""
    r = subprocess.run(['curl', '-fsSL', '-H', 'Cache-Control: no-cache', url],
                       capture_output=True, check=False)
    if r.returncode:
        sys.exit(f'Telechargement impossible ({url}) : {r.stderr.decode().strip()}')
    return r.stdout.decode('utf-8')


def lire_json(chemin, local):
    if local:
        return json.loads((DOSSIER / chemin).read_text(encoding='utf-8'))
    return json.loads(_telecharger(RAW + chemin))


def numero_par_defaut(local):
    t = lire_json('data/today.json', local)
    n = t.get('featured_numero') or t.get('last_featured_numero')
    if not n:
        sys.exit('Aucun scrutin mis en avant dans data/today.json : donne un numero.')
    return int(n)


def source_index_html(local):
    if local:
        return (DOSSIER / 'index.html').read_text(encoding='utf-8')
    return _telecharger(RAW + 'index.html')


# ------------------------------------------------- contours (index.html)
_CH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
_IDX = {c: k for k, c in enumerate(_CH)}


class _Lecteur:
    def __init__(self, s):
        self.s, self.p = s, 0

    def int(self):
        n, sh = 0, 1
        while True:
            c = _IDX[self.s[self.p]]
            self.p += 1
            n += (c & 31) * sh
            sh *= 32
            if c < 32:
                break
        return -((n + 1) // 2) if n & 1 else n // 2

    def fini(self):
        return self.p >= len(self.s)


def charger_contours(html):
    """Rejoue decodeGeo()/ringLatLngs() d'index.html. Renvoie
    [(cle 'dep|circo', [anneau [(lat, lon), ...], ...]), ...]."""
    i = html.index('const GEO = {')
    blk = html[i:html.index('};', i)]
    step = float(re.search(r'step:([0-9.]+)', blk).group(1))
    lon0 = float(re.search(r'lon0:(-?[0-9.]+)', blk).group(1))
    lat0 = float(re.search(r'lat0:(-?[0-9.]+)', blk).group(1))
    champ = lambda k: re.search(k + r':"([^"]*)"', blk).group(1)  # noqa: E731
    ra, arcs = _Lecteur(champ('arcs')), []
    while not ra.fini():
        n, x, y, pts = ra.int(), 0, 0, []
        for _ in range(n):
            x += ra.int()
            y += ra.int()
            pts.append((x, y))
        arcs.append(pts)
    rg, metas, out = _Lecteur(champ('geoms')), champ('meta').split(';'), []
    for cle in metas:
        parts = []
        for _ in range(rg.int()):
            ring, prev = [], 0
            for _ in range(rg.int()):
                prev += rg.int()
                ring.append(prev)
            parts.append(ring)
        anneaux = []
        for ring in parts:
            pts, last = [], None
            for ai in ring:
                rev = ai < 0
                a = arcs[~ai if rev else ai]
                n = len(a)
                for k in range(n):
                    p = a[n - 1 - k if rev else k]
                    if last == p:
                        continue
                    last = p
                    pts.append((lat0 + p[1] * step, lon0 + p[0] * step))
            anneaux.append(pts)
        out.append((cle, anneaux))
    return out


def _mercator(lat, lon):
    return lon, -math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _melange(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(_hex(a), _hex(b)))


def position(vote, cle):
    p = vote['par_circonscription'].get(cle, 'absent')
    return 'absent' if p in ('non_votant', 'absent') or p not in COULEURS else p


def dessiner_carte(contours, vote, largeur, hauteur):
    pts = [_mercator(la, lo) for _, rs in contours for r in rs if len(r) > 2 for la, lo in r]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    sc = min(largeur * SURECH / (x1 - x0), hauteur * SURECH / (y1 - y0))
    ox, oy = (largeur * SURECH - (x1 - x0) * sc) / 2, (hauteur * SURECH - (y1 - y0) * sc) / 2
    im = Image.new('RGBA', (largeur * SURECH, hauteur * SURECH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    trait = (*_hex(INK), 82)  # opacity .32 comme styleOf() dans l'app
    for cle, rs in contours:
        fond = _melange(LAND, COULEURS[position(vote, cle)], 0.88)
        for r in rs:
            if len(r) < 3:
                continue
            xy = [((px - x0) * sc + ox, (py - y0) * sc + oy)
                  for px, py in (_mercator(la, lo) for la, lo in r)]
            d.polygon(xy, fill=fond, outline=trait)
    return im.resize((largeur, hauteur), Image.LANCZOS)


# ------------------------------------------------------- textes (brouillon)
def sort_adopte(vote):
    """Vrai sens du scrutin, lu dans le libelle officiel."""
    s = (vote.get('sort') or '').lower()
    if 'pas adopt' in s:
        return False
    if 'adopt' in s:
        return True
    return None


def nature_scrutin(titre):
    t = titre.lower()
    art = re.search(r"(?:à|après) l'article (premier|\d+[a-z]?)", t)
    art = f"l'article {art.group(1)}" if art else None
    if t.startswith('le sous-amendement'):
        return 'Sous-amendement' + (f' à {art}' if art else '')
    if t.startswith("l'amendement"):
        prep = 'après' if "après l'article" in t else 'à'
        return 'Amendement' + (f' {prep} {art}' if art else '')
    if re.match(r"l'article (premier|\d+)", t):
        return 'Article ' + re.match(r"l'article (premier|\d+[a-z]?)", t).group(1)
    if t.startswith("l'ensemble"):
        return "Vote sur l'ensemble du texte"
    if 'motion' in t:
        return 'Motion'
    return 'Scrutin'


def texte_concerne(titre):
    t = titre.lower()
    if 'proposition de loi' in t:
        return 'de la proposition de loi'
    if 'projet de loi' in t:
        return 'du projet de loi'
    return ''


def titre_brouillon(titre):
    """Brouillon du titre synthetique, a RELIRE : prend l'intitule de la loi
    apres « proposition/projet de loi », retire la mention de lecture et les
    tournures administratives en tete (visant a, portant, apportant une
    reponse integrale au phenomene des...). Un intitule qui commence par
    « de/du/d' » (« de finances pour 2026 ») garde sa nature de texte."""
    m = re.search(r'(proposition|projet) de loi\s+(.+)$', titre, flags=re.I)
    nature, s = (m.group(1).capitalize(), m.group(2)) if m else ('', titre)
    s = re.sub(r'\s*\((?:première|nouvelle|deuxième|seconde|lecture|texte)[^)]*\)', '', s, flags=re.I)
    s = s.strip().rstrip('. ')
    for debut in (r'apportant une réponse intégrale au phénomène des\s+', r'apportant une réponse intégrale au\s+',
                  r'visant à\s+', r'visant le\s+', r'portant\s+', r'relative? (?:à|au|aux)\s+',
                  r'tendant à\s+', r'pour\s+'):
        s2 = re.sub('^' + debut, '', s, flags=re.I)
        if s2 != s:
            s = s2
            break
    elif_prefixe = re.match(r"(de |du |des |d['’])", s, flags=re.I)
    if elif_prefixe and nature:
        s = f'{nature} de loi {s}'
    return s[:1].upper() + s[1:]


def date_fr(iso):
    d = dt.date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def bandeau(iso, aujourdhui=None):
    d = dt.date.fromisoformat(iso)
    ref = aujourdhui or dt.date.today()
    if d == ref - dt.timedelta(days=1):
        return "VOTE D'HIER"
    if d == ref:
        return "VOTE D'AUJOURD'HUI"
    return f"VOTE DU {date_fr(iso).upper()}"


def sujet_phrase(titre_officiel):
    """« Le sous-amendement à l'article 5 », « L'article 5 », « Le texte »..."""
    nature = nature_scrutin(titre_officiel)
    if nature.startswith('Vote sur'):
        return 'Le texte'
    if nature.startswith('Article'):
        return "L'" + nature[0].lower() + nature[1:]
    if nature.startswith('Amendement'):
        return "L'" + nature[0].lower() + nature[1:]
    if nature.startswith('Sous-amendement'):
        return 'Le ' + nature[0].lower() + nature[1:]
    return 'Le scrutin'


def _pl(n, mot):
    return f'{n} {mot}{"s" if n > 1 else ""}'


def legende(vote, titre, contours, aujourdhui=None):
    """Legende du post (Facebook + Instagram), 100 % deduite des chiffres
    officiels : aucun commentaire politique. Le titre vient de l'humain."""
    t = vote['tally']
    n_abs = sum(1 for k, _ in contours if position(vote, k) == 'absent')
    adopte = sort_adopte(vote)
    issue = {True: ' a été adopté', False: ' a été rejeté', None: ''}[adopte]
    quand = bandeau(vote['date'], aujourdhui).capitalize().replace("D'hier", "d'hier")
    lignes = [
        f"{quand} à l'Assemblée nationale — {titre}.",
        f"{sujet_phrase(vote['titre'])}{issue} : {t['contre']} voix contre, {t['pour']} pour, "
        f"{_pl(t['abstention'], 'abstention')}.",
        f"{_pl(n_abs, 'circonscription')} n'{'a' if n_abs == 1 else 'ont'} enregistré aucun vote exprimé : "
        f"le député n'a pas pris part au vote.",
        "Et le vote de ton député ? Retrouve-le sur la carte dans l'app Populous.",
        '#Populous #AssembléeNationale #Vote',
    ]
    return '\n\n'.join(lignes)


# ------------------------------------------------------------------ rendu
def generer(vote, contours, titre, sortie):
    F = gv._police
    W, H = LARGEUR, HAUTEUR
    img = Image.new('RGBA', (W, H), (*gv.GRIS_FOND, 255))
    img.alpha_composite(gv._filigrane_vertical(W, H))

    cx0, cy0, cx1, cy1, R = 54, 70, W - 54, H - 70, 44
    ombre = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ombre).rounded_rectangle((cx0, cy0 + 16, cx1, cy1 + 16), radius=R, fill=(16, 25, 63, 70))
    img.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(22)))
    carte, _ = gv._carte_arrondie(cx1 - cx0, cy1 - cy0, R)
    img.alpha_composite(carte, (cx0, cy0))
    d = ImageDraw.Draw(img)

    px0, px1 = cx0 + 66, cx1 - 66
    y = cy0 + 60
    d.text((px0, y), bandeau(vote['date']), font=F('PlusJakartaSans-ExtraBold.ttf', 30), fill=gv.BLEU)
    d.text((px1, y + 2), date_fr(vote['date']), font=F('PlusJakartaSans-Bold.ttf', 26),
           fill=gv.GRIS_SOURCE, anchor='ra')
    y += 62

    pt = F('PlusJakartaSans-ExtraBold.ttf', 50)
    lignes = gv._wrap_pour_largeur(d, titre, pt, px1 - px0)
    for l in lignes[:3]:
        d.text((px0, y), gv._tronquer_pour_largeur(d, l, pt, px1 - px0), font=pt, fill=gv.ENCRE)
        y += 60
    y += 6

    adopte = sort_adopte(vote)
    issue = {True: 'adopté', False: 'rejeté', None: ''}[adopte]
    cible = texte_concerne(vote['titre'])
    sous = f"{nature_scrutin(vote['titre'])}{' ' + cible if cible and not nature_scrutin(vote['titre']).startswith('Vote') else ''}"
    sous = f"{sous} · {issue}" if issue else sous
    ps = F('PlusJakartaSans-Medium.ttf', 28)
    for l in gv._wrap_pour_largeur(d, sous, ps, px1 - px0):
        d.text((px0, y), l, font=ps, fill=(74, 85, 120))
        y += 38
    y += 14

    leg_h = 150
    mh = cy1 - 78 - leg_h - y
    img.alpha_composite(dessiner_carte(contours, vote, px1 - px0, mh), (px0, y))
    y += mh + 10

    t = vote['tally']
    n_abs = sum(1 for k, _ in contours if position(vote, k) == 'absent')
    items = [('pour', 'Pour', t['pour']), ('contre', 'Contre', t['contre']),
             ('abstention', 'Abstention', t['abstention']), ('absent', 'Absents', n_abs)]
    colw = (px1 - px0) // 4
    pn, pl = F('PlusJakartaSans-ExtraBold.ttf', 50), F('PlusJakartaSans-Bold.ttf', 26)
    for i, (k, lab, n) in enumerate(items):
        x = px0 + i * colw
        d.ellipse((x, y + 12, x + 22, y + 34), fill=COULEURS[k])
        d.text((x + 34, y + 4), str(n), font=pn, fill=gv.ENCRE)
        d.text((x + 34, y + 64), lab, font=pl, fill=(74, 85, 120))

    pf = F('PlusJakartaSans-Medium.ttf', 21)
    d.line((px0, cy1 - 100, px1, cy1 - 100), fill=(224, 225, 232), width=2)
    d.text((px0, cy1 - 82), "Absents : circonscriptions dont le député n'a pas pris part au vote",
           font=pf, fill=gv.GRIS_SOURCE)
    d.text((px0, cy1 - 52), f"Source : Assemblée nationale · scrutin n°{vote['numero']}", font=pf, fill=gv.GRIS_SOURCE)
    d.text((px1, cy1 - 78), 'Populous', font=F('PlusJakartaSans-ExtraBold.ttf', 34), fill=gv.BLEU, anchor='ra')
    img.convert('RGB').save(sortie)


def main():
    ap = argparse.ArgumentParser(description="Visuel « Vote d'hier » Populous")
    ap.add_argument('numero', nargs='?', type=int, help='numero du scrutin (defaut : scrutin mis en avant)')
    ap.add_argument('--titre', help='titre synthetique (remplace le brouillon automatique)')
    ap.add_argument('--local', action='store_true', help='lire data/ et index.html du depot local')
    ap.add_argument('--sortie', help='fichier PNG de sortie')
    a = ap.parse_args()

    numero = a.numero or numero_par_defaut(a.local)
    vote = lire_json(f'data/scrutins/{numero}.json', a.local)
    titre = a.titre or titre_brouillon(vote['titre'])

    sortie = Path(a.sortie) if a.sortie else DOSSIER / 'assets_social' / f"{vote['date']}-vote-{numero}.png"
    generer(vote, charger_contours(source_index_html(a.local)), titre, sortie)

    t = vote['tally']
    contours_ = None
    print(f"Scrutin n°{numero} du {vote['date']} — sort officiel : {vote['sort']}")
    print(f"Pour {t['pour']} · Contre {t['contre']} · Abstention {t['abstention']}")
    print(f"Titre {'fourni' if a.titre else 'BROUILLON (a relire !)'} : {titre}")
    print(f"Libelle officiel : {vote['titre']}")
    print(f'Image : {sortie}')


if __name__ == '__main__':
    main()
