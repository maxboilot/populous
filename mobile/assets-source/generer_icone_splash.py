#!/usr/bin/env python3
"""Genere l'icone iOS, l'ecran de demarrage et l'avatar reseaux sociaux
de Populous, en noir et blanc pur (demande explicite de Max).

Deux dessins distincts, pas le meme motif recycle partout :

  - Icone (AppIcon-512@2x.png, 1024x1024, sans alpha — exige d'App
    Store) et ecran de demarrage (splash-2732x2732*.png, les 3
    variantes d'echelle Capacitor) : le mot "Populous" en entier, meme
    police que l'accueil de l'app (index.html, .d — Plus Jakarta Sans
    ExtraBold), cale en bas a gauche sur fond blanc. Contexte carre
    (icone a coins arrondis, ecran de demarrage en scaleAspectFit), un
    coin ne pose pas probleme. LaunchScreen.storyboard doit rester en
    scaleAspectFit + fond blanc pour ne jamais rogner le texte :
    contrairement a un motif centre, un aspectFill sur un ecran de
    telephone (bien plus haut que large) couperait les bords
    gauche/droit et donc le mot.

  - Avatar reseaux sociaux (assets_social/logo_avatar_reseaux.png) :
    le mot "Populous" en entier (Max y tient, malgre le risque de
    lisibilite reduite une fois recadre en petit cercle par
    Facebook/Instagram — un essai en "P" seul, plus lisible en cercle,
    a ete refuse), centre plutot que cale en bas a gauche pour rester
    dans le disque inscrit au cadrage circulaire. Ce script ne publie
    rien lui-meme.

A relancer puis reconstruire dans Xcode si le texte, la police ou la
couleur du titre changent un jour dans index.html.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent

FONT = RACINE / 'assets_social' / 'fonts' / 'PlusJakartaSans-ExtraBold.ttf'
BLANC = (255, 255, 255)
NOIR = (0, 0, 0)
MARGE_RATIO = 0.09  # espace laisse a gauche et en bas du wordmark, en proportion du cote

SORTIE_IOS = RACINE / 'mobile' / 'ios' / 'App' / 'App' / 'Assets.xcassets'
SORTIE_AVATAR = RACINE / 'assets_social' / 'logo_avatar_reseaux.png'


def _plus_grand_corps(trace, texte, largeur_cible, hauteur_cible=None, corps_depart=900):
    corps = corps_depart
    while corps > 8:
        police = ImageFont.truetype(str(FONT), corps)
        boite = trace.textbbox((0, 0), texte, font=police)
        largeur, hauteur = boite[2] - boite[0], boite[3] - boite[1]
        if largeur <= largeur_cible and (hauteur_cible is None or hauteur <= hauteur_cible):
            return police, boite
        corps -= 1
    return police, boite


def wordmark(taille):
    """Icone / ecran de demarrage : "Populous" en entier, en bas a gauche."""
    img = Image.new('RGB', (taille, taille), BLANC)
    trace = ImageDraw.Draw(img)
    marge = round(taille * MARGE_RATIO)
    police, boite = _plus_grand_corps(trace, 'Populous', taille - 2 * marge, corps_depart=round(taille * 0.3))
    x = marge - boite[0]
    y = (taille - marge) - (boite[3] - boite[1]) - boite[1]
    trace.text((x, y), 'Populous', font=police, fill=NOIR)
    return img


def avatar_reseaux(taille):
    """Avatar reseaux sociaux : "Populous" en entier, noir sur blanc,
    centre (pas en bas a gauche) pour rester dans le disque inscrit au
    cadrage circulaire de Facebook/Instagram."""
    img = Image.new('RGB', (taille, taille), BLANC)
    trace = ImageDraw.Draw(img)
    marge = round(taille * MARGE_RATIO)
    police, boite = _plus_grand_corps(trace, 'Populous', taille - 2 * marge, corps_depart=round(taille * 0.3))
    largeur, hauteur = boite[2] - boite[0], boite[3] - boite[1]
    x = (taille - largeur) // 2 - boite[0]
    y = (taille - hauteur) // 2 - boite[1]
    trace.text((x, y), 'Populous', font=police, fill=NOIR)
    return img


def main():
    icone = wordmark(1024)
    chemin_icone = SORTIE_IOS / 'AppIcon.appiconset' / 'AppIcon-512@2x.png'
    icone.save(chemin_icone)
    print('Icone ecrite :', chemin_icone)

    splash = wordmark(2732)
    dossier_splash = SORTIE_IOS / 'Splash.imageset'
    for nom in ('splash-2732x2732.png', 'splash-2732x2732-1.png', 'splash-2732x2732-2.png'):
        splash.save(dossier_splash / nom)
        print('Splash ecrit :', dossier_splash / nom)

    avatar = avatar_reseaux(1024)
    avatar.save(SORTIE_AVATAR)
    print('Avatar reseaux sociaux ecrit :', SORTIE_AVATAR)


if __name__ == '__main__':
    main()
