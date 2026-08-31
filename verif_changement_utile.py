#!/usr/bin/env python3
# Décide si les données méritent un commit.
#
# Le pipeline réécrit today.json à chaque passage, ne serait-ce que pour son
# horodatage. Comme on tourne désormais plusieurs fois par matinée, committer
# systématiquement noierait l'historique sous des commits vides de sens.
#
# Code de sortie 0 : rien d'utile n'a changé, ne pas committer.
# Code de sortie 1 : il y a une vraie nouveauté, committer.
import json
import pathlib
import subprocess
import sys


def contenu_utile(texte: str) -> str:
    donnees = json.loads(texte)
    donnees.pop('generated_at', None)
    return json.dumps(donnees, sort_keys=True)


modifies = subprocess.run(
    ['git', 'diff', '--cached', '--name-only'],
    capture_output=True, text=True,
).stdout.split()

# Un nouveau scrutin, un agenda modifié, un état mis à jour : toujours utile.
if [m for m in modifies if m != 'data/today.json']:
    sys.exit(1)

ancien = subprocess.run(
    ['git', 'show', 'HEAD:data/today.json'],
    capture_output=True, text=True,
).stdout
nouveau = pathlib.Path('data/today.json').read_text(encoding='utf-8')

sys.exit(0 if contenu_utile(ancien) == contenu_utile(nouveau) else 1)
