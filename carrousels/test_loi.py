"""Test du type « loi » (carrousel d'un texte vote) : selection, titre, explication. Aucun reseau, aucune API.
Lancer : python3 -m unittest carrousels.test_loi -v   (depuis la racine du depot)"""
import datetime, sys, types, unittest
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(RACINE / 'carrousels'))
try:
    import requests  # noqa: F401
except ImportError:                       # Mac sans `requests` : un module factice suffit, ces tests n'appellent aucune API
    sys.modules['requests'] = types.ModuleType('requests')
import publier_reseaux as pr


def vote(objet, sort="l'Assemblée nationale a adopté", pour=300, contre=100, abst=10, **kw):
    return {'numero': kw.pop('numero', 1), 'date': '2026-11-04', 'solennel': True, 'objet': objet, 'titre': objet,
            'sort': sort, 'adopte': kw.pop('adopte', True), 'tally': {'pour': pour, 'contre': contre, 'abstention': abst, 'absent': 0}, **kw}


class TestLoi(unittest.TestCase):
    def test_seuls_les_textes_sont_retenus(self):
        for ok in ("l'ensemble de la proposition de loi visant à x", "l'ensemble du projet de loi y", "la première partie du projet de loi de finances pour 2027 (première lecture).", "la proposition de loi organique z"):
            self.assertTrue(pr.TEXTE_LOI_RE.match(ok), ok)
        for non in ("l'amendement n° 1 du Gouvernement à l'article 5 du projet de loi", "l'article 57 et état A du projet de loi de finances", "la motion de censure", "la déclaration du Gouvernement portant sur x"):
            self.assertFalse(pr.TEXTE_LOI_RE.match(non), non)

    def test_titre_officiel_non_reformule(self):
        self.assertEqual(pr.titre_loi("l'ensemble de la proposition de loi visant à protéger les mineurs"), "Proposition de loi visant à protéger les mineurs")
        self.assertEqual(pr.titre_loi("la première partie du projet de loi de finances pour 2027 (première lecture)."), "Première partie du projet de loi de finances pour 2027 (première lecture)")
        self.assertLessEqual(len(pr.titre_loi("l'ensemble de la proposition de loi " + "très long " * 40)), 151)

    def test_budget_trois_blocs_sources(self):
        blocs, src = pr.explication_loi(vote("la première partie du projet de loi de finances pour 2027 (première lecture).", "L'Assemblée nationale n'a pas adopté", 0, 458, 2, adopte=False))
        self.assertEqual(len(blocs), 3); self.assertIn("art. 34 et 42", src)
        self.assertIn("0 pour, 458 contre, 2 abstentions", blocs[2][1]); self.assertIn("première lecture", blocs[2][1])

    def test_texte_ordinaire_deux_blocs_nature_et_sort(self):
        blocs, src = pr.explication_loi(vote("l'ensemble de la proposition de loi visant à x (première lecture)"))
        self.assertEqual(len(blocs), 2); self.assertIn("déposé par des parlementaires", blocs[0][1]); self.assertIn("Constitution (art. 39)", src)
        blocs, _ = pr.explication_loi(vote("l'ensemble du projet de loi y"))
        self.assertIn("déposé par le Gouvernement", blocs[0][1])

    def test_le_sort_est_lu_dans_le_libelle_pas_dans_le_booleen(self):
        blocs, _ = pr.explication_loi(vote("l'ensemble de la proposition de loi x", "L'Assemblée nationale n'a pas adopté", adopte=True))   # booleen faux, libelle fait foi
        self.assertIn("Résultat : rejeté", blocs[-1][1])

    def test_selection_un_seul_texte_pas_de_doublon(self):
        a, b = vote("l'ensemble de la proposition de loi a", numero=10), vote("l'ensemble du projet de loi b", numero=11)
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a, b]), mock.patch.object(pr.generer_post_vote, 'charger_contours', lambda s: []), \
             mock.patch.object(pr, 'lire_etat_publication', lambda: {'lois_publiees': [10]}):
            c = pr.contenu_loi()
        self.assertEqual(c['numero_scrutin'], 11); self.assertEqual(c['valeur_etat'], [10, 11]); self.assertEqual(c['cle_etat'], 'lois_publiees')
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a, b]), mock.patch.object(pr, 'lire_etat_publication', lambda: {'lois_publiees': [10, 11]}):
            self.assertIsNone(pr.contenu_loi())

    def test_sort_illisible_ignore(self):
        a = vote("l'ensemble de la proposition de loi a", "Renvoyé en commission", numero=10)
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a]), mock.patch.object(pr, 'lire_etat_publication', lambda: {}):
            self.assertIsNone(pr.contenu_loi())


if __name__ == '__main__':
    unittest.main()
