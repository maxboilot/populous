#!/bin/bash
# Publie une nouvelle version de Populous.
#
# Usage : place le nouveau fichier téléchargé dans ce même dossier sous
# le nom index.html (écrase l'ancien), puis lance :
#
#   ./publier.sh
#
# GitHub Pages sert le dossier docs/ (docs/index.html = politique de
# confidentialité, docs/support/ = assistance — URLs déclarées dans App
# Store Connect, à ne jamais déplacer). L'app de test, elle, vit dans
# docs/app/ : ce script y recopie index.html à chaque publication, donc
# les deux restent identiques sans jamais se marcher dessus.
set -e
if [ ! -f index.html ]; then
  echo "Erreur : aucun fichier index.html trouvé dans ce dossier."
  echo "Renomme le fichier téléchargé en index.html avant de relancer."
  exit 1
fi
mkdir -p docs/app
cp index.html docs/app/index.html
git add index.html docs/app/index.html
git commit -m "Mise à jour de l'app — $(date '+%Y-%m-%d %H:%M')"
git push
echo ""
echo "Publié sur https://maxboilot.github.io/populous/app/ — compte 30 à 90 secondes."
echo "Si l'app affiche encore l'ancienne version après ce délai, force un rechargement"
echo "dans le navigateur (Cmd+Maj+R) — c'est le cache, pas la publication, qui traîne."
