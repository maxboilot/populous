"""Test des textes de loi adoptes / rejetes SANS scrutin public (decisions_texte.json) : extraction depuis l'archive officielle (simulee), selection sans doublon
avec les scrutins, phrase « La suite » selon le stade, Reel (seul ou avec des textes a scrutin). Aucun reseau. Lancer : python3 carrousels/test_decisions.py"""
import argparse, datetime, io, json, sys, tempfile, types, unittest, zipfile
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(RACINE / 'carrousels')); sys.path.insert(0, str(RACINE / 'carrousels' / 'moteur' / 'reel'))
try:
    import requests  # noqa: F401
except ImportError:
    sys.modules['requests'] = types.ModuleType('requests')
import publier_reseaux as pr
import construire_decisions_texte as cd
from test_loi import vote


def acte(code, date, statut, vote_ref=None, texte='PIONANR5L17BTA0001', sous=None):
    return {'codeActe': code, 'dateActe': date + 'T00:00:00.000+02:00', 'statutConclusion': {'libelle': statut} if statut else None, 'voteRefs': {'voteRef': vote_ref} if vote_ref else None,
            'textesAssocies': {'texteAssocie': {'typeTexte': 'BTA', 'refTexteAssocie': texte}}, 'uid': f'U-{code}-{date}', 'actesLegislatifs': {'acteLegislatif': sous} if sous else None}


def dossier(uid, titre, procedure, hauts, legislature='17'):
    return {'dossierParlementaire': {'uid': uid, 'legislature': legislature, 'titreDossier': {'titre': titre}, 'procedureParlementaire': {'libelle': procedure},
                                      'actesLegislatifs': {'acteLegislatif': hauts}}}


def haut(code, decision):
    return {'codeActe': code, 'actesLegislatifs': {'acteLegislatif': [{'codeActe': code + '-DEBATS', 'actesLegislatifs': {'acteLegislatif': [decision]}}]}}


def archive(dossiers):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for d in dossiers: z.writestr(f"json/dossierParlementaire/{d['dossierParlementaire']['uid']}.json", json.dumps(d))
    b.seek(0); return b


def dec(**kw):
    base = {'id': 'U1', 'dossier': 'DL1', 'titre': 'Créer un corps de fonctionnaires', 'nature': 'proposition', 'organique': False, 'ratification': False, 'date': datetime.date.today().isoformat(),
            'lecture': 'premiere', 'statut': 'adoptée', 'adopte': True, 'sans_modification': False, 'premiere_assemblee': True, 'vote_ref': None, 'url': 'https://www.assemblee-nationale.fr/dyn/17/dossiers/DL1'}
    base.update(kw); return base


class TestExtraction(unittest.TestCase):
    def test_extraction_depuis_l_archive(self):
        D = [dossier('DL1', 'Créer un truc', 'Proposition de loi ordinaire', [haut('AN1', acte('AN1-DEBATS-DEC', '2026-10-29', 'adoptée'))]),
             dossier('DL2', 'Projet de loi autorisant l’approbation de l’accord X', 'Projet de ratification des traités et conventions',
                     [{'codeActe': 'SN1'}, haut('AN1', acte('AN1-DEBATS-DEC', '2026-10-07', 'adopté sans modification', texte='PRJLANR5L17BTA0002'))]),
             dossier('DL3', 'Une résolution', 'Résolution', [haut('ANLUNI', acte('ANLUNI-DEBATS-DEC', '2026-10-08', 'rejetée'))]),
             dossier('DL4', 'Texte organique', 'Projet ou proposition de loi organique', [haut('AN1', acte('AN1-DEBATS-DEC', '2026-10-13', 'rejeté', 'VTANR5L17V42', texte='PRJLANR5L17BTA0003'))]),
             dossier('DL5', 'Ancienne législature', 'Proposition de loi ordinaire', [haut('AN1', acte('AN1-DEBATS-DEC', '2026-10-29', 'adoptée'))], legislature='16'),
             dossier('DL6', 'Passé en force', 'Projet de loi ordinaire', [haut('ANNLEC', acte('ANNLEC-DEBATS-DEC', '2026-10-30', "considéré comme adopté par l'Assemblée nationale en application de l'article 49, alinéa 3 de la Constitution"))]),
             dossier('DL7', 'Trop ancien', 'Proposition de loi ordinaire', [haut('AN1', acte('AN1-DEBATS-DEC', '2026-01-05', 'adoptée'))]),
             dossier('DL8', 'Nouvelle lecture', 'Projet de loi ordinaire', [haut('AN1', acte('AN1-DEBATS-DEC', '2026-09-01', 'adopté')), haut('ANNLEC', acte('ANNLEC-DEBATS-DEC', '2026-10-20', 'adoptée'))])]
        r = {x['dossier']: x for x in cd.construire(archive(D), '2026-10-01')}
        self.assertEqual(sorted(r), ['DL1', 'DL2', 'DL4', 'DL8'])                    # ni resolution, ni autre legislature, ni 49.3, ni trop ancien
        self.assertTrue(r['DL1']['premiere_assemblee']); self.assertIsNone(r['DL1']['vote_ref']); self.assertEqual(r['DL1']['url'], cd.URL_PUBLIQUE + 'DL1')
        self.assertFalse(r['DL2']['premiere_assemblee']); self.assertTrue(r['DL2']['sans_modification']); self.assertTrue(r['DL2']['ratification'])       # Senat d'abord
        self.assertEqual((r['DL4']['nature'], r['DL4']['organique'], r['DL4']['adopte'], r['DL4']['vote_ref']), ('projet', True, False, 42))
        self.assertEqual(r['DL8']['lecture'], 'nouvelle')

    def test_sorts(self):
        self.assertEqual([cd.sort_normalise(x) for x in ('adopté', 'adoptée sans modification', 'modifiée', 'rejeté', 'rejetée', "considérée comme définitive en application de l'article 151-7", None)],
                         [True, True, True, False, False, None, None])


class TestSelection(unittest.TestCase):
    def avec_fichier(self, decisions, scrutins=()):
        d = Path(tempfile.mkdtemp()); (d / 'data').mkdir(); (d / 'data' / pr.FICHIER_DECISIONS).write_text(json.dumps({'decisions': decisions}))
        return mock.patch.object(pr, 'DOSSIER', d), mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda a: list(scrutins))

    def test_filtres(self):
        auj = datetime.date.today(); vieux = (auj - datetime.timedelta(days=9)).isoformat()
        scr = vote("l'ensemble de la proposition de loi apportant une réponse intégrale au phénomène des violences sexuelles", numero=77); scr['date'] = auj.isoformat()
        D = [dec(id='a', titre='Créer un corps de fonctionnaires'), dec(id='b', vote_ref=12), dec(id='c', titre='Apporter une réponse intégrale au phénomène des violences sexuelles'),
             dec(id='d', date=vieux), dec(id='e', ratification=True, titre='Projet de loi autorisant l’approbation de l’accord Z', nature='projet'), dec(id='f', adopte=None)]
        p1, p2 = self.avec_fichier(D, [scr])
        with p1, p2:
            self.assertEqual([x['id'] for x in pr._decisions_sans_scrutin(auj)], ['a', 'e'])        # b : scrutin cite ; c : meme texte qu'un scrutin ; d : hors fenetre ; f : sort illisible
            with mock.patch.object(pr, 'INCLURE_RATIFICATIONS', False):
                self.assertEqual([x['id'] for x in pr._decisions_sans_scrutin(auj)], ['a'])

    def test_sans_fichier_aucune_decision(self):
        with mock.patch.object(pr, 'DOSSIER', Path(tempfile.mkdtemp())):
            self.assertEqual(pr._decisions_sans_scrutin(datetime.date.today()), [])


class TestSuiteEtTitre(unittest.TestCase):
    def test_la_suite_selon_le_stade(self):
        s = lambda **kw: pr.suite_decision(dec(**kw))[0]
        self.assertIn('transmis au Sénat', s())                                                                       # Assemblee 1re assemblee saisie
        self.assertIn('définitivement adopté', s(premiere_assemblee=False, sans_modification=True)); self.assertIn('quinze jours', s(premiere_assemblee=False, sans_modification=True))
        self.assertIn('la navette continue', s(premiere_assemblee=False))                                            # Senat d'abord, texte modifie
        self.assertIn('nouvelle lecture', s(lecture='nouvelle')); self.assertIn('a statué définitivement', s(lecture='definitive'))
        self.assertIn('commission mixte', s(lecture='deuxieme')); self.assertIn('approuvé par les deux assemblées', s(lecture='cmp'))
        self.assertIn('mêmes termes', s(adopte=False)); self.assertNotIn('Sénat, qui', s(adopte=False))                 # rejet : seulement la regle generale
        self.assertIn('statuer définitivement', s(adopte=False, lecture='cmp'))
        self.assertIn('Conseil constitutionnel', s(organique=True)); self.assertNotIn('Conseil constitutionnel', s())
        self.assertNotIn('Conseil constitutionnel', s(organique=True, adopte=False))

    def test_titre_officiel_non_reformule(self):
        self.assertEqual(pr.titre_decision(dec(titre='Créer un corps de fonctionnaires.')), 'Proposition de loi : Créer un corps de fonctionnaires')
        self.assertEqual(pr.titre_decision(dec(titre='Projet de loi autorisant l’approbation de l’accord Z', nature='projet')), 'Projet de loi autorisant l’approbation de l’accord Z')
        self.assertEqual(pr.titre_decision(dec(titre='Adapter l’autorité judiciaire', nature='projet', organique=True)), 'Projet de loi organique : Adapter l’autorité judiciaire')
        self.assertLessEqual(len(pr.titre_decision(dec(titre='très long ' * 40))), 151)

    def test_cartes_sans_chiffres(self):
        blocs, src = pr.explication_decision(dec(date='2026-10-29'))
        self.assertEqual([b[0] for b in blocs], ['Ce que c’est', 'Ce vote', 'La suite'])
        self.assertIn('déposé par des parlementaires', blocs[0][1]); self.assertIn('première lecture', blocs[0][1]); self.assertIn('29 octobre 2026 : texte adopté', blocs[1][1])
        self.assertNotIn('pour', blocs[1][1]); self.assertIn('Constitution (art. 39', src); self.assertIn('dossier législatif', src)


class TestReel(unittest.TestCase):
    def contenu(self, scrutins, decisions, etat=None):
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: list(scrutins)), mock.patch.object(pr, '_decisions_sans_scrutin', lambda d: list(decisions)), \
             mock.patch.object(pr.generer_post_vote, 'charger_contours', lambda s: []), mock.patch.object(pr, 'lire_etat_publication', lambda: dict(etat or {})), \
             mock.patch.object(pr, '_tient_dans_la_musique', lambda sc: True):
            return pr.contenu_reel()

    def test_un_seul_texte_sans_scrutin(self):
        c = self.contenu([], [dec()])
        self.assertEqual((c['type_reel'], c['scrutin']), ('loi_sans_scrutin', None)); self.assertEqual([s['type'] for s in c['scenario']['scenes']], ['titre', 'cartes'])
        self.assertEqual(c['scenario']['scenes'][0]['tampon'], 'ADOPTÉ'); self.assertEqual(c['etat_plus'], {'decisions_reel_publiees': ['U1']}); self.assertEqual(c['valeur_etat'], [])
        self.assertIn('Dossier législatif : https://www.assemblee-nationale.fr/dyn/17/dossiers/DL1', c['legende']); self.assertLessEqual(c['legende'].count('#'), 5)

    def test_scrutin_et_texte_sans_scrutin_dans_un_seul_reel(self):
        a = vote("l'ensemble du projet de loi b", numero=11); a['date'] = datetime.date.today().isoformat()
        c = self.contenu([a], [dec(id='U2', rejete=None, adopte=False, statut='rejetée')])
        self.assertEqual(c['type_reel'], 'lois'); sc = c['scenario']['scenes']
        self.assertEqual([s['type'] for s in sc], ['titre', 'loi_resume', 'loi_resume']); self.assertEqual(sc[1]['chiffres']['pour'], 300); self.assertIsNone(sc[2]['chiffres'])
        self.assertEqual((sc[1]['tampon'], sc[2]['tampon']), ('ADOPTÉ', 'REJETÉ')); self.assertEqual(c['valeur_etat'], [11]); self.assertEqual(c['etat_plus'], {'decisions_reel_publiees': ['U2']})
        self.assertIn('Scrutin public n°11', c['legende']); self.assertIn('Dossier législatif', c['legende']); self.assertIn('(dossier législatif)', c['scenario']['source'])

    def test_deja_presente_n_est_pas_republie_et_repli_pedagogique(self):
        self.assertEqual(self.contenu([], [dec()], {'decisions_reel_publiees': ['U1']})['type_reel'], 'pedagogique')

    def test_main_reel_memorise_les_decisions_presentees(self):
        mem = {}; c = self.contenu([], [dec()])
        with mock.patch.object(pr, 'contenu_reel', lambda: c), mock.patch.object(pr, 'lire_etat_publication', lambda: dict(mem)), mock.patch.object(pr, 'ecrire_etat_publication', lambda e: mem.update(e)), \
             mock.patch.object(pr.generer_reel, 'generer', lambda *a, **k: {'reel': 'r.mp4', 'couverture': 'c.png', 'duree': 20.0}), mock.patch.object(pr, 'lire_env', lambda: {'IG_USER_ID': 'IG', 'FB_PAGE_TOKEN': 'T', 'FB_PAGE_ID': 'P'}), \
             mock.patch.object(pr, 'publier_reel_instagram', lambda *a, **k: {'id': '1'}), mock.patch.object(pr, 'publier_reel_facebook', lambda *a, **k: '2'):
            pr.main_reel(argparse.Namespace(publier=True, plateformes='facebook,instagram'))
        self.assertEqual(mem['decisions_reel_publiees'], ['U1']); self.assertEqual(mem['dernier_reel']['type_reel'], 'loi_sans_scrutin')


class TestCarrousel(unittest.TestCase):
    def contenu(self, scrutins, decisions, etat=None):
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: list(scrutins)), mock.patch.object(pr, '_decisions_sans_scrutin', lambda d: list(decisions)), \
             mock.patch.object(pr.generer_post_vote, 'charger_contours', lambda s: []), mock.patch.object(pr, 'lire_etat_publication', lambda: dict(etat or {})):
            return pr.contenu_loi()

    def test_texte_sans_scrutin_donne_un_carrousel_a_3_slides(self):
        c = self.contenu([], [dec(date='2026-10-29')])
        self.assertEqual((c['type_rendu'], c['cle_etat'], c['valeur_etat']), ('decision', 'decisions_carrousel_publiees', ['U1']))
        d = c['decision']; self.assertEqual((d['adopte'], d['date_fr']), (True, '29 octobre 2026')); self.assertEqual([b[0] for b in d['explication']], ['Ce que c’est', 'Ce vote', 'La suite'])
        self.assertIn('Dossier législatif', c['legende']); self.assertEqual(pr.parametres_carrousel('loi', c), {'decision': d})

    def test_les_scrutins_passent_avant_et_l_etat_est_separe_de_celui_des_reels(self):
        a = vote("l'ensemble du projet de loi b", numero=11); a['date'] = datetime.date.today().isoformat()
        self.assertEqual(self.contenu([a], [dec()])['numero_scrutin'], 11)
        self.assertEqual(self.contenu([], [dec()], {'decisions_reel_publiees': ['U1']})['type_rendu'], 'decision')        # deja en Reel : le carrousel reste a faire
        self.assertIsNone(self.contenu([], [dec()], {'decisions_carrousel_publiees': ['U1']}))
        self.assertEqual(self.contenu([], [dec(), dec(id='U2')], {'decisions_carrousel_publiees': ['U1']})['valeur_etat'], ['U1', 'U2'])

    def test_main_publie_3_slides_et_memorise(self):
        mem = {}; c = self.contenu([], [dec()]); rendu = {}
        def generer(type_, sortie, **kw):
            rendu.update(type_=type_, **kw); return {'slides_mp4': ['1.mp4', '2.mp4', '3.mp4'], 'slides_png': ['1.png', '2.png', '3.png'], 'apercu': 'a.mp4'}
        envoyes = {}
        with mock.patch.object(pr, 'CHOIX', {'loi': lambda: c}), mock.patch.object(pr.generer_carrousel, 'generer', generer), mock.patch.object(pr, 'lire_etat_publication', lambda: dict(mem)), \
             mock.patch.object(pr, 'ecrire_etat_publication', lambda e: mem.update(e)), mock.patch.object(pr, 'lire_env', lambda: {'IG_USER_ID': 'IG', 'FB_PAGE_TOKEN': 'T', 'FB_PAGE_ID': 'P'}), \
             mock.patch.object(pr, 'publier_diaporama_facebook', lambda p, t, imgs, leg: ({'id': 'f'}, ['a', 'b', 'c'])), \
             mock.patch.object(pr, 'preparer_carrousel_instagram', lambda u, t, el, leg: envoyes.update(n=len(el)) or 'parent'), mock.patch.object(pr, 'publier_conteneur_instagram', lambda *a: {'id': 'ig'}), \
             mock.patch.object(sys, 'argv', ['publier_reseaux.py', '--type', 'loi', '--publier']):
            pr.main()
        self.assertEqual(rendu['type_'], 'decision'); self.assertEqual(rendu['decision']['titre'], c['decision']['titre']); self.assertEqual(envoyes['n'], 3)
        self.assertEqual(mem['decisions_carrousel_publiees'], ['U1'])


class TestMoteur(unittest.TestCase):
    def test_cartes_auto_tiennent_dans_la_zone(self):
        sys.path.insert(0, str(RACINE / 'carrousels' / 'moteur' / 'commun'))
        import carrousel
        court = [['Ce que c’est', 'a ' * 20], ['Ce vote', 'b ' * 20], ['La suite', 'c ' * 20]]
        long_ = [['Ce que c’est', 'a' * 90], ['Ce vote', 'b' * 80], ['La suite', 'c' * 260]]
        for expl in (court, long_, long_[:2]):
            html, fin = carrousel.cartes_auto(expl, y0=330)
            self.assertLessEqual(fin, 330 + 790); self.assertEqual(html.count('class="ex"'), len(expl))
        self.assertIn('font-size:35px', carrousel.cartes_auto(court)[0]); self.assertNotIn('font-size:35px', carrousel.cartes_auto(long_)[0])

    def test_nombre_de_slides_par_defaut_inchange(self):
        sys.path.insert(0, str(RACINE / 'carrousels' / 'moteur' / 'commun'))
        import carrousel
        self.assertEqual(carrousel.NB, 5); self.assertEqual(carrousel.progres(0).count('class="pg"'), 5); self.assertIn('left:187px', carrousel.progres(0))


if __name__ == '__main__':
    unittest.main()
