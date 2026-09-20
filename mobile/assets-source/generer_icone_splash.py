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
    juste "P", blanc sur fond noir, dans un rond qui remplit le
    cercle inscrit. Facebook et Instagram affichent la photo de
    profil en cercle, ou le mot "Populous" entier (meme centre)
    devenait illisible a la petite taille d'un avatar — retour de Max
    apres deux essais avec le mot complet. Ce script ne publie rien
    lui-meme.

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


def avatar_p(taille):
    """Avatar reseaux sociaux : "P" seul, blanc sur noir, cale pour un
    cadrage circulaire (photo de profil Facebook/Instagram)."""
    img = Image.new('RGB', (taille, taille), NOIR)
    trace = ImageDraw.Draw(img)
    # Le rayon du cercle inscrit vaut taille/2 : on vise confortablement
    # en dessous pour une marge de securite au cadrage circulaire.
    cible = taille * 0.62
    police, boite = _plus_grand_corps(trace, 'P', cible, cible, corps_depart=round(taille * 0.9))
    largeur, hauteur = boite[2] - boite[0], boite[3] - boite[1]
    x = (taille - largeur) // 2 - boite[0]
    y = (taille - hauteur) // 2 - boite[1]
    trace.text((x, y), 'P', font=police, fill=BLANC)
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

    avatar = avatar_p(1024)
    avatar.save(SORTIE_AVATAR)
    print('Avatar reseaux sociaux ecrit :', SORTIE_AVATAR)


if __name__ == '__main__':
    main()
