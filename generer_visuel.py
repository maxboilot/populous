#!/usr/bin/env python3
"""Genere l'image (1080x1350, format portrait Instagram) d'un post
reseaux sociaux : un seul et unique gabarit pour toutes les
publications, repris de l'ecran d'accueil de l'app elle-meme — fond
gris avec « Populous » en filigrane vertical (meme .presiWatermark que
index.html : Plus Jakarta Sans 800, encre a 13% d'opacite), une carte
blanche arrondie centree façon pop-up (.sheet) qui porte le texte, et
deux grands guillemets bleu Populous encadrant la carte. Une seule
fonction publique, generer(), pour que publier_reseaux.py n'ait qu'a
lui passer le texte du jour (eventuellement une photo pour les posts
« depute du jour »).

Pourquoi Pillow plutot qu'un rendu HTML/navigateur headless : le script
tourne sans surveillance via cron ; Pillow ne demande aucun binaire de
navigateur a maintenir, juste les polices deja telechargees dans
assets_social/fonts/.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DOSSIER = Path(__file__).parent
FONTS = DOSSIER / 'assets_social' / 'fonts'

LARGEUR, HAUTEUR = 1080, 1350

# Memes valeurs que index.html : --bg, --ink, --accent, --card.
GRIS_FOND = (243, 243, 242)
ENCRE = (16, 25, 63)
BLEU = (27, 59, 219)
BLANC = (255, 255, 255)


def _police(nom, taille):
    return ImageFont.truetype(str(FONTS / nom), taille)


def _wrap_pour_largeur(trace, texte, police, largeur_max):
    mots = texte.split()
    lignes, ligne = [], ''
    for mot in mots:
        essai = f'{ligne} {mot}'.strip()
        if trace.textlength(essai, font=police) <= largeur_max:
            ligne = essai
        else:
            if ligne:
                lignes.append(ligne)
            ligne = mot
    if ligne:
        lignes.append(ligne)
    return lignes


def _filigrane_vertical(largeur, hauteur):
    """Reproduit .presiWatermark : "Populous" en vertical (writing-mode:
    vertical-rl), aligne a droite, encre a 13% d'opacite. Rendu a plat
    puis tourne, comme le ferait le navigateur."""
    police = _police('PlusJakartaSans-ExtraBold.ttf', 180)
    tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    boite = d.textbbox((0, 0), 'Populous', font=police)
    mot_l, mot_h = boite[2] - boite[0], boite[3] - boite[1]

    plat = Image.new('RGBA', (mot_l + 20, mot_h + 20), (0, 0, 0, 0))
    ImageDraw.Draw(plat).text((10 - boite[0], 10 - boite[1]), 'Populous', font=police,
                               fill=(*ENCRE, int(255 * 0.13)))
    vertical = plat.rotate(-90, expand=True)  # lecture de haut en bas

    calque = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
    x = largeur - vertical.width - 20
    y = (hauteur - vertical.height) // 2
    calque.alpha_composite(vertical, (x, y))
    return calque


def _carte_arrondie(largeur, hauteur, rayon):
    """Rectangle blanc a coins arrondis avec ombre douce, comme .sheet."""
    echelle = 2
    masque = Image.new('L', (largeur * echelle, hauteur * echelle), 0)
    ImageDraw.Draw(masque).rounded_rectangle(
        (0, 0, largeur * echelle, hauteur * echelle), radius=rayon * echelle, fill=255)
    masque = masque.resize((largeur, hauteur), Image.LANCZOS)

    carte = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
    carte.paste(Image.new('RGBA', (largeur, hauteur), (*BLANC, 255)), (0, 0), masque)
    return carte, masque


def generer(sortie, *, eyebrow, titre, texte=None, photo=None):
    """Ecrit un PNG 1080x1350 dans `sortie` (Path ou str).

    eyebrow : categorie courte ("FAIT DU JOUR", "A VENIR"...), affichee
      en tete de carte.
    titre : le texte principal (gras).
    texte : paragraphe secondaire optionnel (plus petit, sous le titre).
    photo : image PIL carree optionnelle (ex. portrait de depute),
      affichee en cercle a gauche du titre.
    """
    img = Image.new('RGBA', (LARGEUR, HAUTEUR), (*GRIS_FOND, 255))
    img.alpha_composite(_filigrane_vertical(LARGEUR, HAUTEUR))

    # Ombre de la carte : calque noir flou derriere le rectangle blanc.
    # Marges genereuses pour que le gris + le filigrane restent visibles
    # tout autour, comme un vrai pop-up flottant plutot qu'un plein cadre.
    marge_carte = 96
    cx0, cy0 = marge_carte, 300
    cx1, cy1 = LARGEUR - marge_carte, HAUTEUR - 300
    rayon = 44

    ombre = Image.new('RGBA', img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ombre)
    od.rounded_rectangle((cx0, cy0 + 18, cx1, cy1 + 18), radius=rayon, fill=(16, 25, 63, 70))
    ombre = ombre.filter(ImageFilter.GaussianBlur(24))
    img.alpha_composite(ombre)

    carte, _ = _carte_arrondie(cx1 - cx0, cy1 - cy0, rayon)
    img.alpha_composite(carte, (cx0, cy0))

    trace = ImageDraw.Draw(img)

    # Grands guillemets bleus encadrant la carte (2x plus gros que le
    # premier essai, cf. retour utilisateur).
    police_guillemet = _police('PlusJakartaSans-ExtraBold.ttf', 520)
    trace.text((cx0 - 70, cy0 - 250), '“', font=police_guillemet, fill=BLEU)
    boite_fermant = trace.textbbox((0, 0), '”', font=police_guillemet)
    largeur_fermant = boite_fermant[2] - boite_fermant[0]
    y_guillemet_fermant = cy1 - 260
    trace.text((cx1 - largeur_fermant + 50, y_guillemet_fermant), '”', font=police_guillemet, fill=BLEU)

    # Contenu de la carte.
    pad = 84
    inner_x0, inner_x1 = cx0 + pad, cx1 - pad
    y = cy0 + 84

    police_eyebrow = _police('PlusJakartaSans-Bold.ttf', 30)
    trace.text((inner_x0, y), eyebrow.upper(), font=police_eyebrow, fill=BLEU)
    y += 56

    if photo is not None:
        diametre = 220
        masque_p = Image.new('L', (diametre * 4, diametre * 4), 0)
        ImageDraw.Draw(masque_p).ellipse((0, 0, diametre * 4, diametre * 4), fill=255)
        masque_p = masque_p.resize((diametre, diametre), Image.LANCZOS)
        photo_ronde = photo.resize((diametre, diametre), Image.LANCZOS).convert('RGBA')
        img.alpha_composite(Image.composite(photo_ronde, Image.new('RGBA', photo_ronde.size, (0, 0, 0, 0)), masque_p),
                             (inner_x0, y))
        texte_x0 = inner_x0 + diametre + 40
    else:
        texte_x0 = inner_x0

    largeur_titre = inner_x1 - texte_x0
    for taille in (68, 58, 50, 44, 40):
        police_titre = _police('PlusJakartaSans-ExtraBold.ttf', taille)
        lignes_titre = _wrap_pour_largeur(trace, titre, police_titre, largeur_titre)
        hauteur_ligne = int(taille * 1.2)
        if hauteur_ligne * len(lignes_titre) <= 330 or taille == 40:
            break

    y_titre = y
    for ligne in lignes_titre:
        trace.text((texte_x0, y_titre), ligne, font=police_titre, fill=ENCRE)
        y_titre += hauteur_ligne

    y = max(y_titre, y + (220 if photo is not None else 0)) + 30

    if texte:
        police_texte = _police('PlusJakartaSans-Medium.ttf', 32)
        lignes_texte = _wrap_pour_largeur(trace, texte, police_texte, inner_x1 - inner_x0)
        max_lignes = max(1, (y_guillemet_fermant - 20 - y) // 46)
        if len(lignes_texte) > max_lignes:
            lignes_texte = lignes_texte[:max_lignes]
            lignes_texte[-1] = lignes_texte[-1].rstrip() + '…'
        for ligne in lignes_texte:
            trace.text((inner_x0, y), ligne, font=police_texte, fill=(74, 85, 120))
            y += 46

    # Pied de page hors carte, petit et aligne a gauche : "Populous App
    # -> App Store". La fleche est dessinee a la main (le glyphe ->
    # n'existe pas dans Plus Jakarta Sans et se rendrait en tofu).
    police_pied = _police('PlusJakartaSans-Bold.ttf', 22)
    gauche, droite = 'Populous App', 'App Store'
    l_gauche = trace.textlength(gauche, font=police_pied)
    largeur_fleche = 34
    x = marge_carte
    y_pied = HAUTEUR - 64
    trace.text((x, y_pied), gauche, font=police_pied, fill=ENCRE)
    x += l_gauche + 16
    y_mid = y_pied + 15
    trace.line((x, y_mid, x + largeur_fleche, y_mid), fill=ENCRE, width=3)
    trace.line((x + largeur_fleche - 10, y_mid - 9, x + largeur_fleche, y_mid), fill=ENCRE, width=3)
    trace.line((x + largeur_fleche - 10, y_mid + 9, x + largeur_fleche, y_mid), fill=ENCRE, width=3)
    x += largeur_fleche + 16
    trace.text((x, y_pied), droite, font=police_pied, fill=ENCRE)

    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(sortie, 'PNG')


def portrait_depute(a_index, chemin_atlas='assets_social/atlas_portraits.webp', atlas_cols=24, atlas_rows=25):
    """Renvoie l'image PIL (carree) d'un depute decoupee dans l'atlas de
    portraits deja utilise par index.html (meme fichier, meme indexation
    `a`), prete a passer en `photo=` a generer()."""
    atlas = Image.open(DOSSIER / chemin_atlas).convert('RGB')
    cw, ch = atlas.width // atlas_cols, atlas.height // atlas_rows
    col, row = a_index % atlas_cols, a_index // atlas_cols
    return atlas.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))


if __name__ == '__main__':
    generer(
        DOSSIER / 'assets_social' / 'apercu.png',
        eyebrow='Fait du jour',
        titre="1958 : la Ve République est adoptée par référendum",
        texte="Le 28 septembre 1958, les Français approuvent à 82% la nouvelle Constitution portée par le général de Gaulle, fondant la Cinquième République.",
    )
    print('Apercu genere dans assets_social/apercu.png')
