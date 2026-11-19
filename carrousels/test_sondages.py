"""Test de la lecture du tableau de sondages Wikipedia (construire_sondages.py) : les DEUX mises en page d'en-tete (ancienne a deux lignes,
actuelle a une ligne) donnent les memes candidats, et un resultat vide n'ecrase jamais le fichier. Aucun reseau.
Lancer : python3 carrousels/test_sondages.py"""
import io, json, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import construire_sondages as cs

PHOTO_LO = '[[Fichier:Nathalie Arthaud (LO) 19-05-2024.jpg|alt=Nathalie Arthaud|50x50px]]'
PHOTO_LFI = '[[Fichier:Jean Luc Melenchon 2026.jpg|50x50px]]'
NOM_LO = '[[Nathalie Arthaud|Arthaud]]<br><small>([[Lutte ouvrière|LO]])</small>'
NOM_LFI = '[[Jean-Luc Mélenchon|Mélenchon]]<br><small>([[La France insoumise|LFI]])</small>'
SONDAGE = ['| rowspan="2" | [http://x.fr/ifop.pdf Ifop]', '| rowspan="2" |12-17 novembre', '| rowspan="2" |{{formatnum:952}}', '|1', '|19', '|—']

# Mise en page actuelle (18 nov. 2026) : une seule ligne d'en-tete, photo + nom + parti dans chaque cellule, puis la barre de couleurs.
ACTUELLE = '\n'.join(['{| class="wikitable"', '! rowspan=2 | Sondeur', '! rowspan=2 | Date', '! rowspan=2 | Échantillon',
                      f'! width=70px scope=col | {PHOTO_LO}<br>{NOM_LO}', f'! width=70px scope=col | {PHOTO_LFI}<br>{NOM_LFI}', '! width="70px" scope="col" | Autres',
                      '|- style="line-height:5px;"', '| {{Infobox Parti politique français/couleurs|LO}} |', '| {{Infobox Parti politique français/couleurs|LFI}} |', '| |',
                      '|-', *SONDAGE, '|-', '|1', '|2', '|—'])
# Ancienne mise en page : ligne 0 = photos, ligne 1 = noms + partis.
ANCIENNE = '\n'.join(['{| class="wikitable"', '! rowspan=2 | Sondeur', '! rowspan=2 | Date', '! rowspan=2 | Échantillon', f'! {PHOTO_LO}', f'! {PHOTO_LFI}', '! Autres',
                      '|-', f'! {NOM_LO}', f'! {NOM_LFI}', '! Autres', '|- style="line-height:5px;"', '| |', '| |', '| |', '|-', *SONDAGE])


class TestLectureEntete(unittest.TestCase):
    def test_les_deux_mises_en_page_donnent_les_memes_candidats(self):
        attendu = [('arthaud', 'Arthaud', 'LO', 'Nathalie Arthaud (LO) 19-05-2024.jpg'), ('melenchon', 'Mélenchon', 'LFI', 'Jean Luc Melenchon 2026.jpg')]
        for nom, wikitext in (('actuelle', ACTUELLE), ('ancienne', ANCIENNE)):
            with self.subTest(mise_en_page=nom):
                cands = cs.parse_candidats(cs.parse_rows(wikitext))
                self.assertEqual([(c['cle'], c['nom'], c['parti'], c['fichier']) for c in cands], attendu)

    def test_sondage_lu_avec_la_mise_en_page_actuelle(self):
        rows = cs.parse_rows(ACTUELLE)
        cands = cs.parse_candidats(rows)
        sondages = cs.parse_sondages(rows, annee=2026, n_cols=len(cands) + 4)
        self.assertEqual(len(sondages), 1)
        self.assertEqual((sondages[0]['institut'], sondages[0]['date'], sondages[0]['echantillon']), ('Ifop', '2026-11-17', 952))


class TestPasDEcrasement(unittest.TestCase):
    def lancer(self, wikitext, sortie):
        page = {'query': {'pages': {'1': {'revisions': [{'slots': {'main': {'*': '==== Second semestre 2026 ====\n' + wikitext + '\n== Fin =='}}}]}}}}
        with mock.patch.object(cs, 'requete', return_value=page), mock.patch.object(cs, 'resoudre_images', return_value={}), mock.patch.object(cs, 'SORTIE', sortie), \
                redirect_stdout(io.StringIO()):
            return cs.main()

    def test_une_page_illisible_ne_modifie_pas_le_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            sortie = Path(d) / 'sondages.json'
            sortie.write_text('{"sondages":[{"institut":"Ifop"}]}', encoding='utf-8')
            with self.assertRaises(SystemExit) as e:
                self.lancer('{|\n! Sondeur\n|-\n| rien\n', sortie)
            self.assertIn('ECHEC', str(e.exception))
            self.assertEqual(json.loads(sortie.read_text(encoding='utf-8')), {'sondages': [{'institut': 'Ifop'}]})

    def test_une_page_lisible_est_ecrite(self):
        with tempfile.TemporaryDirectory() as d:
            sortie = Path(d) / 'sondages.json'
            self.lancer(ACTUELLE, sortie)
            self.assertEqual([s['institut'] for s in json.loads(sortie.read_text(encoding='utf-8'))['sondages']], ['Ifop'])


if __name__ == '__main__':
    unittest.main()
