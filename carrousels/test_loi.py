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
        self.assertEqual([b[0] for b in blocs], ["Ce que c’est", "Ce vote", "La suite"]); self.assertIn("LOLF (art. 34 et 42)", src)
        self.assertIn("0 pour, 458 contre, 2 abstentions", blocs[1][1]); self.assertIn("première lecture", blocs[1][1])
        self.assertIn("ne peut pas être discutée tant que la première partie n’est pas adoptée", blocs[2][1])

    def test_texte_ordinaire_trois_blocs_nature_sort_suite(self):
        blocs, src = pr.explication_loi(vote("l'ensemble de la proposition de loi visant à x (première lecture)"))
        self.assertEqual(len(blocs), 3); self.assertIn("déposé par des parlementaires", blocs[0][1]); self.assertIn("Constitution (art. 39", src)
        self.assertEqual(blocs[2][0], "La suite"); self.assertIn("mêmes termes par l’Assemblée nationale et par le Sénat", blocs[2][1])
        blocs, _ = pr.explication_loi(vote("l'ensemble du projet de loi y"))
        self.assertIn("déposé par le Gouvernement", blocs[0][1])

    def test_la_suite_phrases_validees_par_cas(self):
        def suite(objet, adopte=True):
            return pr.suite_loi(vote(objet, "l'Assemblée nationale a adopté" if adopte else "L'Assemblée nationale n'a pas adopté", adopte=adopte))
        self.assertIn("mêmes termes", suite("l'ensemble du projet de loi y (première lecture)")[0])
        self.assertIn("commission mixte paritaire (7 députés et 7 sénateurs)", suite("l'ensemble de la proposition de loi x (deuxième lecture)")[0])
        self.assertIn("nouvelle lecture", suite("l'ensemble de la proposition de loi x (nouvelle lecture)")[0])
        self.assertIn("a statué définitivement", suite("l'ensemble de la proposition de loi x (lecture définitive)")[0])
        self.assertIn("quinze jours", suite("l'ensemble de la proposition de loi x (lecture définitive)")[0])
        self.assertIn("approuvé par les deux assemblées", suite("l'ensemble du projet de loi x (texte de la commission mixte paritaire)")[0])
        self.assertIn("peut maintenant être mise en discussion", suite("la première partie du projet de loi de finances pour 2027 (première lecture).")[0])
        self.assertIn("demander à l’Assemblée nationale de statuer définitivement", suite("l'ensemble du projet de loi x (texte de la commission mixte paritaire)", False)[0])
        self.assertIn("ne peut pas être discutée", suite("la première partie du projet de loi de finances pour 2027 (première lecture).", False)[0])
        for objet in ("l'ensemble du projet de loi y (première lecture)", "l'ensemble de la proposition de loi x (nouvelle lecture)", "l'ensemble de la proposition de loi x (lecture définitive)"):
            self.assertNotIn("passer au Sénat", suite(objet, False)[0]); self.assertIn("mêmes termes", suite(objet, False)[0])      # rejet : seulement la regle generale, rien d'invente
        phrase, source = suite("l'ensemble de la proposition de loi organique x (première lecture)")
        self.assertIn("contrôle du Conseil constitutionnel", phrase); self.assertIn("art. 46 et 61", source)                     # loi organique
        self.assertNotIn("contrôle du Conseil constitutionnel", suite("l'ensemble de la proposition de loi x (première lecture)")[0])
        self.assertIsNone(pr.suite_loi(vote("l'ensemble de la proposition de loi x", "Renvoyé en commission")))

    def test_fusion_des_sources(self):
        self.assertEqual(pr._fusionner_sources(["Constitution (art. 39)", "Constitution (art. 45) · assemblee-nationale.fr (fiche n°46)", "Sources : Constitution (art. 10, 45 et 61) · assemblee-nationale.fr"]),
                         "Sources : Constitution (art. 10, 39, 45 et 61) · assemblee-nationale.fr (fiche n°46)")
        self.assertEqual(pr._fusionner_sources(["LOLF (art. 42)", "Constitution (art. 39)"]), "Sources : LOLF (art. 42) · Constitution (art. 39)")

    def test_selection_scrutins_ordinaires_inclus_amendements_exclus(self):
        import json, tempfile
        d = Path(tempfile.mkdtemp()); (d / 'data' / 'scrutins').mkdir(parents=True)
        auj = datetime.date.today().isoformat(); (d / 'data' / 'today.json').write_text(json.dumps({'featured_numero': 4}))
        for n, objet, sol in ((1, "l'ensemble de la proposition de loi a (première lecture)", False), (2, "l'amendement n° 12 à l'article 3 de la proposition de loi a", False),
                              (3, "l'ensemble du projet de loi b", True), (4, "la motion de censure", True)):
            v = vote(objet, numero=n); v['date'] = auj; v['solennel'] = sol; (d / 'data' / 'scrutins' / f'{n}.json').write_text(json.dumps(v))
        with mock.patch.object(pr, 'DOSSIER', d):
            self.assertEqual([v['numero'] for v in pr._scrutins_solennels_de_texte(datetime.date.today())], [1, 3])        # ordinaire + solennel ; ni amendement ni motion

    def test_le_sort_est_lu_dans_le_libelle_pas_dans_le_booleen(self):
        blocs, _ = pr.explication_loi(vote("l'ensemble de la proposition de loi x", "L'Assemblée nationale n'a pas adopté", adopte=True))   # booleen faux, libelle fait foi
        self.assertIn("Résultat : rejeté", blocs[1][1])

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
