#!/usr/bin/env python3
"""Genere l'icone iOS, l'ecran de demarrage et le logo carre reseaux
sociaux de Populous, tous les trois a partir du MEME fichier source :
logo_source.png (le visuel "Populous" avec la rosette, fond bleu nuit).

Ce script ne redessine rien : il recolore le fond du logo source avec
le bleu de marque de l'app (--accent dans index.html) puis le recadre
en carre par letterboxing (jamais de crop qui couperait la rosette ou
le mot "Populous") pour les trois formats suivants :
  - AppIcon-512@2x.png     (1024x1024, sans alpha — exige d'App Store)
  - splash-2732x2732*.png  (les 3 variantes d'echelle Capacitor)
  - assets_social/logo_carre_bleu.png (a poster a la main sur
    Facebook/Instagram — ce script ne publie rien lui-meme)

Recolorage du fond : le fond de logo_source.png est un bleu nuit
quasi uni mais legerement bruite (compression), donc un simple
remplacement par egalite exacte de couleur laisserait des pixels
residuels. On mesure plutot, pixel par pixel, la distance a la
couleur de fond d'origine et on melange vers la nouvelle couleur en
consequence (0 = totalement inchange, 1 = totalement remplace), avec
un palier (D_IN) en dessous duquel le remplacement est total : ca
elimine le bruit de fond sans toucher aux bords antialiases de la
rosette et du texte.

A relancer puis reconstruire dans Xcode si le bleu de marque change.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent

SOURCE = ICI / 'logo_source.png'
FOND_ORIGINE = np.array([25, 39, 61], dtype=np.float32)     # fond actuel de logo_source.png
FOND_MARQUE = np.array([27, 59, 219], dtype=np.float32)     # --accent de index.html (#1B3BDB)
D_IN, D_OUT = 18.0, 55.0                                    # palier de remplacement / bord antialiase

SORTIE_IOS = RACINE / 'mobile' / 'ios' / 'App' / 'App' / 'Assets.xcassets'
SORTIE_SOCIAL = RACINE / 'assets_social' / 'logo_carre_bleu.png'


def recolorer_fond(im):
    arr = np.array(im.convert('RGB')).astype(np.float32)
    dist = np.linalg.norm(arr - FOND_ORIGINE, axis=2)
    poids = np.clip((D_OUT - dist) / (D_OUT - D_IN), 0, 1)[..., None]
    out = arr + poids * (FOND_MARQUE - FOND_ORIGINE)
    return Image.fromarray(np.clip(out, 0, 255).astype('uint8'))


def carre_par_letterboxing(im, taille):
    """Redimensionne `im` a la largeur `taille` puis complete en hauteur
    avec le bleu de marque — jamais de recadrage, tout le visuel (rosette
    + mot "Populous") reste visible integralement, juste plus de bleu
    au-dessus et en dessous."""
    ratio = taille / im.width
    redim = im.resize((taille, round(im.height * ratio)), Image.LANCZOS)
    fond = tuple(int(c) for c in FOND_MARQUE)
    canevas = Image.new('RGB', (taille, taille), fond)
    y = (taille - redim.height) // 2
    canevas.paste(redim, (0, y))
    return canevas


def main():
    source = Image.open(SOURCE)
    recolore = recolorer_fond(source)

    icone = carre_par_letterboxing(recolore, 1024)
    chemin_icone = SORTIE_IOS / 'AppIcon.appiconset' / 'AppIcon-512@2x.png'
    icone.save(chemin_icone)
    print('Icone ecrite :', chemin_icone)

    splash = carre_par_letterboxing(recolore, 2732)
    dossier_splash = SORTIE_IOS / 'Splash.imageset'
    for nom in ('splash-2732x2732.png', 'splash-2732x2732-1.png', 'splash-2732x2732-2.png'):
        splash.save(dossier_splash / nom)
        print('Splash ecrit :', dossier_splash / nom)

    logo_social = carre_par_letterboxing(recolore, 1024)
    logo_social.save(SORTIE_SOCIAL)
    print('Logo reseaux sociaux ecrit :', SORTIE_SOCIAL)


if __name__ == '__main__':
    main()
