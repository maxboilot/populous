#!/bin/bash
# Publie une nouvelle version de Populous.
#
# Usage : place le nouveau fichier téléchargé dans ce même dossier sous
# le nom index.html (écrase l'ancien), puis lance :
#
#   ./publier.sh
#
set -e
if [ ! -f index.html ]; then
  echo "Erreur : aucun fichier index.html trouvé dans ce dossier."
  echo "Renomme le fichier téléchargé en index.html avant de relancer."
  exit 1
fi
git add index.html
git commit -m "Mise à jour de l'app — $(date '+%Y-%m-%d %H:%M')"
git push
echo ""
echo "Publié. GitHub Pages met généralement 30 à 90 secondes à répercuter le changement."
echo "Si l'app affiche encore l'ancienne version après ce délai, force un rechargement"
echo "dans le navigateur (Cmd+Maj+R) — c'est le cache, pas la publication, qui traîne."
