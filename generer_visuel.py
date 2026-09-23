#!/usr/bin/env python3
"""Genere l'image (1080x1600, format portrait Instagram) d'un post
reseaux sociaux : un seul et unique gabarit pour toutes les
publications, repris de l'ecran d'accueil de l'app elle-meme — fond
gris avec « Populous » en filigrane vertical (meme .presiWatermark que
index.html : Plus Jakarta Sans 800, encre a 13% d'opacite), une carte
blanche arrondie centree façon pop-up (.sheet) qui porte le texte, et
deux grands guillemets bleu Populous encadrant la carte. Une seule
fonction publique, generer(), pour que publier_reseaux.py n'ait qu'a
lui passer le texte du jour (eventuellement une photo pour les posts
« depute du jour », un bloc detaille pour ce meme post, ou un pele-mele
d'exemples pour la boussole).

Pourquoi Pillow plutot qu'un rendu HTML/navigateur headless : le script
tourne sans surveillance via cron ; Pillow ne demande aucun binaire de
navigateur a maintenir, juste les polices deja telechargees dans
assets_social/fonts/.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DOSSIER = Path(__file__).parent
FONTS = DOSSIER / 'assets_social' / 'fonts'

LARGEUR, HAUTEUR = 1080, 1600

# Memes valeurs que index.html : --bg, --ink, --accent, --card.
GRIS_FOND = (243, 243, 242)
ENCRE = (16, 25, 63)
BLEU = (27, 59, 219)
BLANC = (255, 255, 255)
ROUGE = (196, 26, 26)
GRIS_SOURCE = (146, 150, 168)


def _police(nom, taille):
    return ImageFont.truetype(str(FONTS / nom), taille)


def _tronquer_pour_largeur(trace, texte, police, largeur_max):
    """Filet de securite pour un seul mot plus large que la carte (nom de
    famille compose tres long, sans espace pour casser en fin de ligne) :
    tronque caractere par caractere avec une ellipse plutot que deborder."""
    if trace.textlength(texte, font=police) <= largeur_max:
        return texte
    tronque = texte
    while len(tronque) > 1 and trace.textlength(tronque + '…', font=police) > largeur_max:
        tronque = tronque[:-1]
    return tronque + '…'


def _wrap_pour_largeur(trace, texte, police, largeur_max):
    """Casse uniquement sur les espaces : un mot seul plus large que
    `largeur_max` (nom de famille compose, sans espace pour casser) reste
    donc tel quel sur sa ligne — a l'appelant de s'assurer que la taille de
    police choisie lui laisse assez de place (cf. la boucle de `generer()`
    qui verifie la largeur reelle) ou, en dernier recours, de tronquer via
    `_tronquer_pour_largeur`."""
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


def _date_rouge(texte):
    """Date du fait en rouge, legerement inclinee — juste le texte, sans
    bandeau, posee dans le coin haut droit de la carte (pas au-dessus,
    pas de rectangle plein derriere). Inclinaison volontairement legere :
    une rotation plus marquee ferait exploser la hauteur de la boite une
    fois tournee (largeur du texte * sin(angle)) et ferait chevaucher le
    titre, qui peut faire jusqu'a 4 lignes selon le fait du jour."""
    police = _police('PlusJakartaSans-ExtraBold.ttf', 26)
    tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(tmp)
    txt = texte.upper()
    boite = d0.textbbox((0, 0), txt, font=police)
    l, h = boite[2] - boite[0], boite[3] - boite[1]

    plat = Image.new('RGBA', (l + 16, h + 16), (0, 0, 0, 0))
    ImageDraw.Draw(plat).text((8 - boite[0], 8 - boite[1]), txt, font=police, fill=(*ROUGE, 255))
    return plat.rotate(-10, expand=True, resample=Image.BICUBIC)


EXEMPLES_BOUSSOLE = [
    DOSSIER / 'assets_social' / 'exemples_boussole' / 'resultat_1.jpg',
    DOSSIER / 'assets_social' / 'exemples_boussole' / 'resultat_2.jpg',
    DOSSIER / 'assets_social' / 'exemples_boussole' / 'resultat_3.jpg',
]


def _carte_depuis_capture(chemin, largeur_cible=300, rayon=26, hauteur_max=None):
    """Charge une vraie capture d'ecran du popup « Ton resultat » de la
    boussole (coins deja arrondis par le navigateur) et la nettoie :
    recadrage d'un eventuel debordement de fond sous la carte, puis
    reclippage net aux memes coins pour effacer le liseret de fond qui
    depasse legerement autour du popup capture."""
    im = Image.open(chemin).convert('RGB')
    w, h = im.size
    if hauteur_max and h > hauteur_max:
        h = hauteur_max
        im = im.crop((0, 0, w, h))
    h_cible = round(h * largeur_cible / w)
    im = im.resize((largeur_cible, h_cible), Image.LANCZOS)
    masque = Image.new('L', im.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, im.size[0], im.size[1]), radius=rayon, fill=255)
    carte = Image.new('RGBA', im.size, (0, 0, 0, 0))
    carte.paste(im, (0, 0), masque)
    return carte


def pile_boussole_exemple(largeur_cible=300):
    """Empile les 3 vraies captures d'ecran du popup de resultat
    (assets_social/exemples_boussole/, fournies une fois pour toutes)
    en pele-mele legerement tourne, pour illustrer aux utilisateurs a
    quoi ressemble leur resultat sur le post de promo de la boussole."""
    cartes = [
        _carte_depuis_capture(EXEMPLES_BOUSSOLE[0], largeur_cible, hauteur_max=1332),
        _carte_depuis_capture(EXEMPLES_BOUSSOLE[1], largeur_cible, hauteur_max=1450),
        _carte_depuis_capture(EXEMPLES_BOUSSOLE[2], largeur_cible, hauteur_max=1712),
    ]
    rotations = [-11, 7, -4]
    dx = [0, 150, 300]
    dy = [65, 0, 85]
    marge = 36
    zone_l = max(c.width for c in cartes) + max(dx) + marge * 2
    zone_h = max(c.height + dy[i] for i, c in enumerate(cartes)) + marge * 2
    calque = Image.new('RGBA', (zone_l, zone_h), (0, 0, 0, 0))
    for i, c in enumerate(cartes):
        ombre = Image.new('RGBA', c.size, (0, 0, 0, 0))
        ImageDraw.Draw(ombre).rounded_rectangle((0, 10, c.size[0], c.size[1]), radius=26, fill=(16, 25, 63, 90))
        ombre = ombre.filter(ImageFilter.GaussianBlur(14))
        c_rot = c.rotate(rotations[i], expand=True, resample=Image.BICUBIC)
        o_rot = ombre.rotate(rotations[i], expand=True, resample=Image.BICUBIC)
        x, y = marge + dx[i], marge + dy[i]
        calque.alpha_composite(o_rot, (x, y))
        calque.alpha_composite(c_rot, (x, y))
    return calque


def _tag_pill(img, trace, x, y, texte, couleur, police):
    """Puce texte sur fond teinte translucide. Le fond translucide est
    dessine sur un calque a part puis compose via alpha_composite : un
    fill RGBA directement sur `img` n'est pas mele (juste ecrit tel
    quel), ce qui, une fois l'image finale aplatie en RGB, ferait
    ressortir la couleur pleine et rendrait le texte illisible dessus."""
    pad_x, pad_y = 12, 6
    w = trace.textlength(texte, font=police)
    h = police.size
    largeur, hauteur = int(w + pad_x * 2) + 2, h + pad_y * 2
    calque = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
    ImageDraw.Draw(calque).rounded_rectangle((0, 0, largeur, hauteur), radius=hauteur // 2, fill=couleur + (34,))
    img.alpha_composite(calque, (int(x), int(y)))
    trace.text((x + pad_x, y + pad_y - 1), texte, font=police, fill=couleur)
    return w + pad_x * 2


def _dessiner_bloc_depute(img, trace, x0, x1, y, bloc):
    """Rejoue, sous le nom et la photo, ce que l'app montre dans la
    fiche d'un depute jusqu'au « Dernier vote connu » inclus."""
    largeur = x1 - x0

    p_groupe = _police('PlusJakartaSans-Bold.ttf', 26)
    rayon_pt = 9
    trace.ellipse((x0, y + 6, x0 + rayon_pt * 2, y + 6 + rayon_pt * 2), fill=bloc['groupe_couleur'])
    trace.text((x0 + rayon_pt * 2 + 12, y), bloc['groupe_sigle'], font=p_groupe, fill=ENCRE)
    y += 42

    p_meta = _police('PlusJakartaSans-Medium.ttf', 24)
    for ligne in _wrap_pour_largeur(trace, bloc['circonscription'], p_meta, largeur):
        trace.text((x0, y), ligne, font=p_meta, fill=(74, 85, 120))
        y += 32
    y += 6

    p_gn = _police('PlusJakartaSans-Medium.ttf', 21)
    for ligne in _wrap_pour_largeur(trace, bloc['groupe_nom'], p_gn, largeur):
        trace.text((x0, y), ligne, font=p_gn, fill=(74, 85, 120))
        y += 28
    y += 8

    p_pro = _police('PlusJakartaSans-Bold.ttf', 23)
    trace.text((x0, y), f"Profession : {bloc['profession']}", font=p_pro, fill=ENCRE)
    y += 46

    v = bloc.get('vote')
    if v:
        trace.line((x0, y, x1, y), fill=(224, 225, 232), width=2)
        y += 26
        p_hd = _police('PlusJakartaSans-Bold.ttf', 20)
        trace.text((x0, y), v['label'], font=p_hd, fill=v['couleur'])
        y += 32
        p_titre_v = _police('PlusJakartaSans-Medium.ttf', 24)
        for ligne in _wrap_pour_largeur(trace, v['titre'], p_titre_v, largeur)[:3]:
            trace.text((x0, y), ligne, font=p_titre_v, fill=ENCRE)
            y += 31
        y += 6
        p_meta2 = _police('PlusJakartaSans-Medium.ttf', 19)
        trace.text((x0, y), f"Scrutin n°{v['numero']} · {v['date']}", font=p_meta2, fill=(140, 148, 175))
        y += 34
        p_tag = _police('PlusJakartaSans-Bold.ttf', 19)
        _tag_pill(img, trace, x0, y, v['position_label'], v['couleur'], p_tag)
        y += 44
    return y


def generer(sortie, *, eyebrow, titre, texte=None, photo=None,
            date_badge=None, bloc_depute=None, pile_resultats=None, pied_source=None):
    """Ecrit un PNG 1080x1350 dans `sortie` (Path ou str).

    eyebrow : categorie courte ("FAIT DU JOUR", "A VENIR"...), affichee
      en tete de carte.
    titre : le texte principal (gras).
    texte : paragraphe secondaire optionnel (plus petit, sous le titre) —
      ignore si `bloc_depute` est fourni.
    photo : image PIL carree optionnelle (ex. portrait de depute),
      affichee en cercle a gauche du titre.
    date_badge : texte court ("28 SEPTEMBRE 1958"...) affiche en rouge,
      legerement incline, dans le coin haut droit de la carte (fait du
      jour) — juste le texte, pas de bandeau.
    bloc_depute : dict decrivant le depute (groupe, circonscription,
      profession, dernier vote) affiche sous le nom, a la place de
      `texte` — cf. contenu_depute() dans publier_reseaux.py.
    pile_resultats : image PIL (RGBA) deja composee — cf.
      pile_boussole_exemple() — collee sous `texte`.
    pied_source : si fourni, remplace le pied de page "Populous - iOS"
      par ce texte (petit, gris clair) au meme endroit —
      utilise pour les posts « depute du jour » : la photo et les
      donnees de vote viennent de l'Assemblee, la Licence Ouverte
      Etalab impose la mention de la source, et l'accoler a un appel a
      telecharger l'app risquerait de la faire lire comme un usage
      publicitaire (licence photos de l'Assemblee interdite en pub).
    """
    carte_etendue = bool(bloc_depute) or bool(pile_resultats)

    img = Image.new('RGBA', (LARGEUR, HAUTEUR), (*GRIS_FOND, 255))
    img.alpha_composite(_filigrane_vertical(LARGEUR, HAUTEUR))

    # Ombre de la carte : calque noir flou derriere le rectangle blanc.
    # Marges genereuses pour que le gris + le filigrane restent visibles
    # tout autour, comme un vrai pop-up flottant plutot qu'un plein cadre.
    # Les posts a contenu dense (depute, boussole) reduisent ces marges
    # pour agrandir la carte, sans jamais empieter sur le pied de page.
    marge_carte = 96
    marge_haut = 180 if carte_etendue else 300
    marge_bas = 240 if carte_etendue else 300
    cx0, cy0 = marge_carte, marge_haut
    cx1, cy1 = LARGEUR - marge_carte, HAUTEUR - marge_bas
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

    y_titre_debut = y + 56

    # Date du fait, en rouge, calee juste au-dessus du debut du titre
    # (dont la hauteur varie de 1 a 4 lignes selon le fait du jour) :
    # ainsi elle ne risque jamais de le chevaucher, quelle que soit sa
    # propre taille une fois tournee.
    if date_badge:
        etiquette = _date_rouge(date_badge)
        y_etiquette = max(cy0 + 14, y_titre_debut - 12 - etiquette.height)
        img.alpha_composite(etiquette, (inner_x1 - etiquette.width, y_etiquette))
        trace = ImageDraw.Draw(img)

    y += 56

    if photo is not None:
        diametre = 220
        masque_p = Image.new('L', (diametre * 4, diametre * 4), 0)
        ImageDraw.Draw(masque_p).ellipse((0, 0, diametre * 4, diametre * 4), fill=255)
        masque_p = masque_p.resize((diametre, diametre), Image.LANCZOS)
        # Les portraits de l'atlas ne font que 64x64px a la source : un
        # agrandissement direct a 220px donne un rendu blocky. On repasse
        # par un palier intermediaire plus grand + un leger flou avant de
        # redescendre a la taille finale, ce qui lisse les gros pixels
        # sans pour autant rendre le portrait flou a l'oeil.
        photo_ronde = photo.resize((diametre * 3, diametre * 3), Image.LANCZOS)
        photo_ronde = photo_ronde.filter(ImageFilter.GaussianBlur(1.6))
        photo_ronde = photo_ronde.resize((diametre, diametre), Image.LANCZOS).convert('RGBA')
        img.alpha_composite(Image.composite(photo_ronde, Image.new('RGBA', photo_ronde.size, (0, 0, 0, 0)), masque_p),
                             (inner_x0, y))
        texte_x0 = inner_x0 + diametre + 40
    else:
        texte_x0 = inner_x0

    largeur_titre = inner_x1 - texte_x0
    max_hauteur_titre = 420
    for taille in (68, 58, 50, 44, 40):
        police_titre = _police('PlusJakartaSans-ExtraBold.ttf', taille)
        lignes_titre = _wrap_pour_largeur(trace, titre, police_titre, largeur_titre)
        hauteur_ligne = int(taille * 1.2)
        # Il ne suffit pas que le total tienne en hauteur (420px) : un mot
        # compose sans espace (nom de famille a rallonge) peut rester seul
        # sur une ligne trop large tout en respectant le budget de hauteur,
        # et deborder de la carte sans que cette condition ne le detecte.
        largeur_reelle = max(trace.textlength(l, font=police_titre) for l in lignes_titre)
        if (hauteur_ligne * len(lignes_titre) <= max_hauteur_titre and largeur_reelle <= largeur_titre) or taille == 40:
            break

    # Filet de securite final : meme a 40 (la plus petite taille testee),
    # un mot compose exceptionnellement long resterait plus large que la
    # carte — on le tronque plutot que de le laisser deborder. N'affecte
    # pas les cas normaux : a ce stade la ligne tient deja la plupart du
    # temps, _tronquer_pour_largeur est un no-op si elle rentre deja.
    lignes_titre = [_tronquer_pour_largeur(trace, l, police_titre, largeur_titre) for l in lignes_titre]

    # Meme a la plus petite taille, un titre tres long (certains textes de
    # loi depassent 200 caracteres) peut encore deborder du budget de
    # hauteur : on le tronque a un nombre de lignes fixe plutot que de
    # laisser le "texte" en dessous se faire ecraser contre le guillemet
    # fermant.
    max_lignes_titre = max(1, max_hauteur_titre // hauteur_ligne)
    if len(lignes_titre) > max_lignes_titre:
        lignes_titre = lignes_titre[:max_lignes_titre]
        lignes_titre[-1] = lignes_titre[-1].rstrip() + '…'

    y_titre = y
    for ligne in lignes_titre:
        trace.text((texte_x0, y_titre), ligne, font=police_titre, fill=ENCRE)
        y_titre += hauteur_ligne

    y = max(y_titre, y + (220 if photo is not None else 0)) + 30

    if bloc_depute:
        y = _dessiner_bloc_depute(img, trace, inner_x0, inner_x1, y, bloc_depute)
    elif texte:
        police_texte = _police('PlusJakartaSans-Medium.ttf', 32)
        lignes_texte = _wrap_pour_largeur(trace, texte, police_texte, inner_x1 - inner_x0)
        max_lignes = max(1, (y_guillemet_fermant - 20 - y) // 46)
        if len(lignes_texte) > max_lignes:
            lignes_texte = lignes_texte[:max_lignes]
            lignes_texte[-1] = lignes_texte[-1].rstrip() + '…'
        for ligne in lignes_texte:
            trace.text((inner_x0, y), ligne, font=police_texte, fill=(74, 85, 120))
            y += 46

    if pile_resultats is not None:
        # Cale a gauche (et deborde un peu du cadre a gauche) pour ne
        # pas recouvrir le second guillemet, en bas a droite de la carte.
        px = cx0 - 20
        py = y - 10
        img.alpha_composite(pile_resultats, (px, py))

    # Pied de page hors carte, petit et aligne a gauche.
    trace = ImageDraw.Draw(img)
    y_pied = HAUTEUR - 64
    if pied_source:
        # Petit, gris clair mais lisible : simple mention de source, pas
        # d'appel a l'action (cf. docstring de `pied_source`).
        police_source = _police('PlusJakartaSans-Medium.ttf', 22)
        largeur_dispo = (LARGEUR - marge_carte) - marge_carte
        texte_source = _tronquer_pour_largeur(trace, pied_source, police_source, largeur_dispo)
        trace.text((marge_carte, y_pied), texte_source, font=police_source, fill=GRIS_SOURCE)
    else:
        police_pied = _police('PlusJakartaSans-Bold.ttf', 22)
        trace.text((marge_carte, y_pied), 'Populous - iOS', font=police_pied, fill=ENCRE)

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
        date_badge='28 septembre 1958',
    )
    print('Apercu genere dans assets_social/apercu.png')
