#!/usr/bin/env python3
# Décide si les données méritent un commit.
#
# Plusieurs fichiers produits par le pipeline changent a chaque passage sans
# rien apporter : ils portent un horodatage, ou une borne de fenetre glissante.
# Comme on execute le pipeline plusieurs fois par matinee, committer a chaque
# fois noierait l historique sous des commits vides de sens.
#
# Code de sortie 0 : rien d utile n a change, ne pas committer.
# Code de sortie 1 : il y a une vraie nouveaute, committer.
import json
import pathlib
import subprocess
import sys

# Fichier -> champs a ignorer parce qu ils bougent sans porter de sens.
VOLATILES = {
    'data/today.json': ['generated_at'],
    'data/historique.json': ['generated_at', 'depuis'],
}


def contenu_utile(texte, champs):
    donnees = json.loads(texte)
    for champ in champs:
        donnees.pop(champ, None)
    return json.dumps(donnees, sort_keys=True)


modifies = subprocess.run(
    ['git', 'diff', '--cached', '--name-only'],
    capture_output=True, text=True,
).stdout.split()

if not modifies:
    sys.exit(0)

# Un nouveau scrutin, un agenda modifie, un etat mis a jour : toujours utile.
if [m for m in modifies if m not in VOLATILES]:
    sys.exit(1)

for fichier in modifies:
    champs = VOLATILES[fichier]
    ancien = subprocess.run(
        ['git', 'show', 'HEAD:' + fichier],
        capture_output=True, text=True,
    ).stdout
    if not ancien.strip():
        sys.exit(1)
    nouveau = pathlib.Path(fichier).read_text(encoding='utf-8')
    try:
        if contenu_utile(ancien, champs) != contenu_utile(nouveau, champs):
            sys.exit(1)
    except Exception:
        sys.exit(1)

sys.exit(0)
