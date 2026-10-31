# Carrousels Populous (HyperFrames)

Depuis le 31 octobre 2026, chaque post Facebook / Instagram est un **carrousel de 5 slides** (1080×1350, 4:5) généré par
[HyperFrames](https://hyperframes.heygen.com) (HTML + GSAP rendu en vidéo). Les 5 slides forment **une bande continue** :
le fond change de couleur sans couture et un élément traverse chaque frontière entre deux slides (barre des 577 voix,
portrait du député, règle de calendrier, boussole, frise 1946 → 2026…).

```
carrousels/
  generer_carrousel.py     générateur unique : --type fait|depute|avenir|boussole|vote|presidentiel --sortie DOSSIER
  moteur/
    commun/                socle : base.css, carrousel.css/js (modes slide / preview / pano), lib.js (hémicycle canvas),
                           blocs.py, carrousel.py, exporter_sieges.py, gsap.min.js (local : aucun réseau au rendu)
    <type>/                gabarit/modele.html + construire.py (données réelles du dépôt → index.html)
    assets/                images utilisées par certains types
```

## Ce que produit un rendu
`slide_1..5.mp4` (chaque slide animée), `slide_1..5.png` (image finale de chaque slide), `apercu_swipe.mp4` (la bande entière,
caméra qui glisse). Durée d'un rendu : environ 1 minute sur un Mac, quelques minutes sur GitHub Actions (Chrome sans GPU).

## Publication (`publier_reseaux.py`, déclenché par le planificateur Cloudflare)
- **Facebook** : diaporama des 5 images (même fonction que l'ancien « Vote d'hier »).
- **Instagram** : carrousel de 5 **vidéos** (URL publique obtenue en envoyant chaque slide en vidéo *non publiée* sur la Page).
  Si cette voie échoue **avant** la publication, repli automatique sur le carrousel des 5 images (rien n'est public à ce stade,
  donc aucun risque de doublon : `publier_conteneur_instagram` est la seule étape publique).
- Mode brouillon par défaut : sans `--publier`, le carrousel est généré dans `assets_social/carrousels/<date>-<type>/` et rien n'est publié.
- Si le rendu échoue, le script s'arrête en erreur (workflow rouge) : **jamais de demi-carrousel**, et plus d'ancien visuel de repli.

## Données (rien n'est inventé)
| type | source |
|---|---|
| fait | `data/refs_jour.json` (jour du MM-JJ) ; source affichée = celle du fait (« officielle » seulement si assemblee-nationale.fr) |
| depute | `index.html` (élus, atlas officiel `assets_social/atlas_portraits.webp`), vote du `data/today.json` |
| avenir | `data/agenda.json` (dès aujourd'hui) |
| boussole | `data/historique.json` (10 scrutins réels). L'écran « Ton résultat 80 % » est une **illustration**, marquée « EXEMPLE » à l'image |
| vote | `data/scrutins/<n>.json` + titre synthétique relu par un humain (`--titre`) |
| presidentiel | `data/sondages.json` (dernier sondage ; aucune photo distante, couleurs de parti) |

## Tester en local
```bash
# prérequis : Node >= 22, FFmpeg dans le PATH, Chrome ; pip install Pillow requests
python3 carrousels/generer_carrousel.py --type avenir --sortie /tmp/test
python3 publier_reseaux.py --type fait          # brouillon complet, sans rien publier
```
