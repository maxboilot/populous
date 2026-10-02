#!/usr/bin/env python3
"""Correction ponctuelle : recalcule `adopte` dans data/scrutins/*.json a
partir du libelle officiel `sort` (le booleen etait faux : "n'a pas adopte"
contient "adopt", cf. ingest_scrutins.py). Idempotent ; ne touche a aucun
autre champ ni a la mise en forme du fichier."""
import json
import re
from pathlib import Path

DOSSIER = Path(__file__).parent / 'data' / 'scrutins'
corriges = deja_bons = ignores = 0
for chemin in sorted(DOSSIER.glob('*.json')):
    brut = chemin.read_text(encoding='utf-8')
    sc = json.loads(brut)
    sort = (sc.get('sort') or '').lower()
    if 'adopt' not in sort:
        ignores += 1  # libelle inattendu : on ne devine pas
        print(f"ignore {chemin.name} : sort={sc.get('sort')!r}")
        continue
    vrai = 'pas adopt' not in sort
    if sc.get('adopte') is vrai:
        deja_bons += 1
        continue
    nouveau, n = re.subn(r'("adopte":\s*)(true|false)', r'\1' + ('true' if vrai else 'false'), brut, count=1)
    assert n == 1, chemin.name
    chemin.write_text(nouveau, encoding='utf-8')
    corriges += 1
print(f'{corriges} corriges, {deja_bons} deja bons, {ignores} ignores')
