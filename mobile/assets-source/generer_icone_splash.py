#!/usr/bin/env python3
"""Genere l'icone iOS, l'ecran de demarrage et le logo carre reseaux
sociaux de Populous : le mot "Populous" exactement comme il apparait
sur l'accueil de l'app (index.html, .d — Plus Jakarta Sans ExtraBold,
couleur --ink), en noir sur fond blanc, cale en bas a gauche. Choix de
Max plutot qu'un symbole dessine — cf. historique de conversation.

Produit, tous depuis le meme dessin (un carre) :
  - AppIcon-512@2x.png     (1024x1024, sans alpha — exige d'App Store)
  - splash-2732x2732*.png  (les 3 variantes d'echelle Capacitor —
    LaunchScreen.storyboard doit rester en scaleAspectFit + fond blanc
    pour ne jamais rogner le texte cale a gauche : contrairement a un
    motif centre, un aspectFill sur un ecran de telephone (bien plus
    haut que large) couperait les bords gauche/droit et donc le mot)
  - assets_social/logo_carre_blanc.png (a poster a la main sur
    Facebook/Instagram — ce script ne publie rien lui-meme)

A relancer puis reconstruire dans Xcode si le texte, la police ou la
couleur du titre changent un jour dans index.html.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent

FONT = RACINE / 'assets_social' / 'fonts' / 'PlusJakartaSans-ExtraBold.ttf'
BLANC = (255, 255, 255)
ENCRE = (16, 25, 63)   # --ink de index.html — meme couleur exacte que le titre a l'ecran
MARGE_RATIO = 0.09     # espace laisse a gauche et en bas, en proportion du cote

SORTIE_IOS = RACINE / 'mobile' / 'ios' / 'App' / 'App' / 'Assets.xcassets'
SORTIE_SOCIAL = RACINE / 'assets_social' / 'logo_carre_blanc.png'


def logo_carre(taille):
    img = Image.new('RGB', (taille, taille), BLANC)
    trace = ImageDraw.Draw(img)

    marge = round(taille * MARGE_RATIO)
    largeur_cible = taille - 2 * marge

    # La plus grande taille de police qui tient dans la largeur cible.
    corps = round(taille * 0.3)
    while corps > 8:
        police = ImageFont.truetype(str(FONT), corps)
        boite = trace.textbbox((0, 0), 'Populous', font=police)
        if boite[2] - boite[0] <= largeur_cible:
            break
        corps -= 1

    boite = trace.textbbox((0, 0), 'Populous', font=police)
    x = marge - boite[0]
    y = (taille - marge) - (boite[3] - boite[1]) - boite[1]
    trace.text((x, y), 'Populous', font=police, fill=ENCRE)
    return img


def main():
    icone = logo_carre(1024)
    chemin_icone = SORTIE_IOS / 'AppIcon.appiconset' / 'AppIcon-512@2x.png'
    icone.save(chemin_icone)
    print('Icone ecrite :', chemin_icone)

    splash = logo_carre(2732)
    dossier_splash = SORTIE_IOS / 'Splash.imageset'
    for nom in ('splash-2732x2732.png', 'splash-2732x2732-1.png', 'splash-2732x2732-2.png'):
        splash.save(dossier_splash / nom)
        print('Splash ecrit :', dossier_splash / nom)

    logo_social = logo_carre(1024)
    logo_social.save(SORTIE_SOCIAL)
    print('Logo reseaux sociaux ecrit :', SORTIE_SOCIAL)


if __name__ == '__main__':
    main()
