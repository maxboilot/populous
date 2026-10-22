#!/bin/bash
# (Retiré) Publiait la version web de Populous dans docs/app/.
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
echo "Populous n'existe plus en version web : il n'y a plus rien à publier avec ce script."
echo "L'app se met à jour par les boutiques (App Store / Google Play) ; les pages légales"
echo "(docs/index.html, docs/conditions/, docs/support/) se publient par un simple git push."
exit 0
