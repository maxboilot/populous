"""Test des Reels (selection du jour + publication avec API Meta SIMULEE : rien n'est envoye). Lancer : python3 -m unittest carrousels.test_reel -v"""
import json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(RACINE / 'carrousels')); sys.path.insert(0, str(RACINE / 'carrousels' / 'moteur' / 'reel'))
import publier_reseaux as pr
import lecture, musique
from test_loi import vote


def rep(json_, statut=200):
    r = mock.Mock(); r.status_code = statut; r.json.return_value = json_; r.text = str(json_); return r


class TestReel(unittest.TestCase):
    def file_(self):
        return json.loads((RACINE / 'data' / 'reels_pedagogiques.json').read_text(encoding='utf-8'))['reels']

    def test_file_pedagogique_valide(self):
        ids = [r['id'] for r in self.file_()]
        self.assertEqual(len(ids), len(set(ids)))
        for r in self.file_():
            self.assertTrue(r['urls'] and r['source'] and r['scenes'], r['id'])
            self.assertIn('📚 Sources', r['legende']); self.assertLessEqual(r['legende'].count('#'), 5, r['id'])
            for s in r['scenes']:
                self.assertIn(s['type'], ('titre', 'texte', 'liste', 'etapes', 'compare', 'points', 'chiffre', 'mois', 'hemicycle'), r['id'])
                if s['type'] == 'hemicycle':                                                     # hemicycle d'un vrai scrutin (exemple) : le scrutin doit exister
                    self.assertTrue((RACINE / 'data' / 'scrutins' / f"{r['scrutin']}.json").exists(), r['id'])
                if s['type'] == 'points': self.assertLessEqual(sum(g['n'] for g in s['groupes']), 600, r['id'])
                if s['type'] == 'texte': self.assertLessEqual(len(s['texte']), 130, r['id'])      # lisible a l'ecran
                if s['type'] == 'liste': self.assertLessEqual(len(s['items']), 5, r['id'])

    def test_chaque_bandeau_apparait_une_fois_le_precedent_lu(self):
        for r in self.file_():
            for s in r['scenes']:
                if s['type'] not in ('cartes', 'liste', 'etapes', 'compare'): continue
                dl, fin = lecture.delais_items(s)
                self.assertEqual(dl, sorted(dl), r['id']); self.assertTrue(all(b - a >= 1.0 for a, b in zip(dl, dl[1:])), (r['id'], dl))
                self.assertGreaterEqual(lecture.duree_min(s), dl[-1] + 1.0, r['id'])             # le dernier a le temps d'etre lu

    def test_calage_sur_la_musique_pour_tous_les_reels(self):
        scenarios = [r['scenes'] for r in self.file_()]
        for sc in scenarios:
            sc2, n2, ne = musique.caler({'scenes': json.loads(json.dumps(sc))})
            cum = 0
            for x, x0 in zip(sc2['scenes'], sc):
                self.assertAlmostEqual(x['duree'] / musique.B, round(x['duree'] / musique.B), delta=0.01)      # chaque scene dure un nombre entier de temps
                self.assertGreaterEqual(x['duree'], lecture.duree_min(x) - 1e-6)                              # jamais moins que le temps de lecture
                cum += x['duree']
            self.assertAlmostEqual(cum, ne * musique.B, delta=0.01); self.assertTrue(4 <= n2 <= musique.MAX_N2)
            self.assertEqual((sc2['effet_fin'], sc2['pause_fin']), ('zoom', musique.PAUSE))

    def test_calage_du_reel_texte_vote(self):
        a = vote("l'ensemble de la proposition de loi a", numero=10)
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a]), mock.patch.object(pr.generer_post_vote, 'charger_contours', lambda s: []), \
             mock.patch.object(pr, 'lire_etat_publication', lambda: {}):
            c = pr.contenu_reel()
        sc2, n2, ne = musique.caler(c['scenario'])
        self.assertEqual(sc2['effet_fin'], 'zoom'); self.assertGreater(ne, n2)

    def test_reel_hors_limites_de_l_extrait_garde_la_bande_son_synthetisee(self):
        long_ = {'scenes': [{'type': 'titre', 'titre': 'x', 'duree': 3.4}, {'type': 'texte', 'texte': 'mot ' * 300, 'kicker': '', 'duree': 4}]}
        with self.assertRaises(ValueError): musique.caler(long_)                                   # groove plus long que l'extrait
        with self.assertRaises(ValueError): musique.caler({'scenes': [{'type': 'titre', 'titre': 'x', 'duree': 12}, {'type': 'texte', 'texte': 'a b', 'kicker': '', 'duree': 4}]})   # 1er visuel trop long

    def test_texte_vote_prioritaire(self):
        a = vote("l'ensemble de la proposition de loi a", numero=10)
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a]), mock.patch.object(pr.generer_post_vote, 'charger_contours', lambda s: []), \
             mock.patch.object(pr, 'lire_etat_publication', lambda: {}):
            c = pr.contenu_reel()
        self.assertEqual(c['type_reel'], 'loi'); self.assertEqual(c['scrutin'], 10); self.assertEqual(c['cle_etat'], 'lois_reel_publiees')
        self.assertEqual([s['type'] for s in c['scenario']['scenes']], ['titre', 'chiffres', 'cartes', 'hemicycle']); self.assertEqual(c['scenario']['scenes'][0]['tampon'], 'ADOPTÉ')

    def test_sinon_pedagogique_dans_l_ordre_puis_repart_du_debut(self):
        ids = [r['id'] for r in self.file_()]
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: []):
            with mock.patch.object(pr, 'lire_etat_publication', lambda: {}):
                c = pr.contenu_reel()
            self.assertEqual((c['type_reel'], c['id'], c['valeur_etat']), ('pedagogique', ids[0], [ids[0]]))
            with mock.patch.object(pr, 'lire_etat_publication', lambda: {'reels_pedagogiques_publies': ids[:3]}):
                self.assertEqual(pr.contenu_reel()['id'], ids[3])
            with mock.patch.object(pr, 'lire_etat_publication', lambda: {'reels_pedagogiques_publies': ids}):
                c = pr.contenu_reel()
            self.assertEqual((c['id'], c['valeur_etat']), (ids[0], [ids[0]]))

    def test_un_texte_deja_en_reel_n_est_pas_republie(self):
        a = vote("l'ensemble de la proposition de loi a", numero=10)
        with mock.patch.object(pr, '_scrutins_solennels_de_texte', lambda d: [a]), mock.patch.object(pr, 'lire_etat_publication', lambda: {'lois_reel_publiees': [10]}):
            self.assertEqual(pr.contenu_reel()['type_reel'], 'pedagogique')

    def test_publication_instagram_et_facebook(self):
        appels = []
        def post(url, data=None, headers=None, timeout=None, files=None):
            appels.append((url, dict(data) if isinstance(data, dict) else {'octets': len(data or b'')}))
            if url.endswith('/IG/media'): return rep({'id': 'C1', 'uri': 'https://rupload.facebook.com/x'})
            if 'rupload' in url or 'upload.example' in url: return rep({'success': True})
            if url.endswith('/media_publish'): return rep({'id': 'M1'})
            if url.endswith('/PAGE/video_reels') and (data or {}).get('upload_phase') == 'start': return rep({'video_id': 'V1', 'upload_url': 'https://upload.example/v1'})
            return rep({'success': True})
        def get(url, params=None, timeout=None):
            return rep({'status_code': 'FINISHED', 'status': {'video_status': 'ready'}})
        with tempfile.NamedTemporaryFile(suffix='.mp4') as f, mock.patch.object(pr.requests, 'post', post), mock.patch.object(pr.requests, 'get', get), \
             mock.patch.object(pr, 'time', mock.Mock(sleep=lambda s: None)):
            f.write(b'0' * 100); f.flush()
            pr.publier_reel_instagram('IG', 'TOK', f.name, 'legende'); pr.publier_reel_facebook('PAGE', 'TOK', f.name, 'legende')
        media = [d for u, d in appels if u.endswith('/IG/media')][0]
        self.assertEqual((media['media_type'], media['upload_type'], media['share_to_feed']), ('REELS', 'resumable', 'true'))
        self.assertTrue(any(d.get('upload_phase') == 'finish' and d.get('video_state') == 'PUBLISHED' for u, d in appels))
        self.assertTrue(any(u.endswith('/IG/media_publish') for u, d in appels))


    def test_publication_story_instagram_et_facebook(self):
        appels = []
        def post(url, data=None, headers=None, timeout=None, files=None):
            appels.append((url, dict(data) if isinstance(data, dict) else {'octets': len(data or b'')}))
            if url.endswith('/IG/media'): return rep({'id': 'C1', 'uri': 'https://rupload.facebook.com/x'})
            if 'rupload' in url or 'upload.example' in url: return rep({'success': True})
            if url.endswith('/media_publish'): return rep({'id': 'S1'})
            if url.endswith('/PAGE/video_stories') and (data or {}).get('upload_phase') == 'start': return rep({'video_id': 'V1', 'upload_url': 'https://upload.example/v1'})
            return rep({'success': True, 'post_id': 'P1'})
        def get(url, params=None, timeout=None): return rep({'status_code': 'FINISHED'})
        with tempfile.NamedTemporaryFile(suffix='.mp4') as f, mock.patch.object(pr.requests, 'post', post), mock.patch.object(pr.requests, 'get', get), \
             mock.patch.object(pr, 'time', mock.Mock(sleep=lambda s: None)):
            f.write(b'0' * 100); f.flush()
            pr.publier_story_instagram('IG', 'TOK', f.name); r = pr.publier_story_facebook('PAGE', 'TOK', f.name)
        media = [d for u, d in appels if u.endswith('/IG/media')][0]
        self.assertEqual((media['media_type'], media['upload_type']), ('STORIES', 'resumable')); self.assertNotIn('caption', media)
        self.assertTrue(any(u.endswith('/IG/media_publish') for u, d in appels))
        self.assertTrue(any(u.endswith('/PAGE/video_stories') and d.get('upload_phase') == 'finish' and d.get('video_id') == 'V1' for u, d in appels))
        self.assertEqual(r['video_id'], 'V1')

    def _story(self, etat, duree=30.0, plateformes='facebook,instagram', forcer=False):
        """Lance main_story avec un etat en memoire, le rendu et l'API simules. Renvoie (etat final, liste des plateformes publiees, nb de rendus)."""
        import argparse, datetime as dt
        pubs, rendus, mem = [], [], dict(etat)
        gen = lambda sc, dossier, scrutin=None: (rendus.append((sc, scrutin)) or {'reel': 'r.mp4', 'couverture': 'c.png', 'duree': duree})
        with mock.patch.object(pr, 'lire_etat_publication', lambda: dict(mem)), mock.patch.object(pr, 'ecrire_etat_publication', lambda e: mem.update(e)), \
             mock.patch.object(pr.generer_reel, 'generer', gen), mock.patch.object(pr, 'lire_env', lambda: {'IG_USER_ID': 'IG', 'FB_PAGE_TOKEN': 'T', 'FB_PAGE_ID': 'P'}), \
             mock.patch.object(pr, 'publier_story_instagram', lambda *a: pubs.append('instagram') or {'id': '1'}), mock.patch.object(pr, 'publier_story_facebook', lambda *a: pubs.append('facebook') or {'video_id': '2'}):
            pr.main_story(argparse.Namespace(publier=True, plateformes=plateformes, forcer=forcer))
        return mem, pubs, rendus

    def test_story_du_reel_du_jour(self):
        import datetime as dt
        auj = dt.date.today().isoformat(); dr = {'date': auj, 'type_reel': 'loi', 'scenario': {'scenes': []}, 'scrutin': 9759}
        mem, pubs, rendus = self._story({'dernier_reel': dr})
        self.assertEqual(sorted(pubs), ['facebook', 'instagram']); self.assertEqual(mem['story_du'], auj); self.assertEqual(rendus[0][1], 9759)      # meme Reel, meme scrutin

    def test_story_rien_a_faire(self):
        import datetime as dt
        auj = dt.date.today().isoformat(); hier = (dt.date.today() - dt.timedelta(days=1)).isoformat(); dr = {'date': auj, 'type_reel': 'pedagogique', 'scenario': {'scenes': []}, 'scrutin': None}
        for etat in ({}, {'dernier_reel': dict(dr, date=hier)}, {'dernier_reel': dr, 'story_du': auj}):       # pas de Reel, Reel d'hier, Story deja publiee
            mem, pubs, rendus = self._story(etat); self.assertEqual((pubs, rendus), ([], []))
        mem, pubs, rendus = self._story({'dernier_reel': dr, 'story_du': auj}, forcer=True); self.assertEqual(len(pubs), 2)          # --forcer republie

    def test_story_trop_longue_ou_une_seule_plateforme(self):
        import datetime as dt
        dr = {'date': dt.date.today().isoformat(), 'type_reel': 'loi', 'scenario': {'scenes': []}, 'scrutin': None}
        mem, pubs, rendus = self._story({'dernier_reel': dr}, duree=75.0); self.assertEqual(pubs, []); self.assertNotIn('story_du', mem)         # plus de 59 s : pas de Story
        mem, pubs, rendus = self._story({'dernier_reel': dr}, plateformes='instagram'); self.assertEqual(pubs, ['instagram'])

    def test_le_reel_memorise_pour_la_story(self):
        import argparse, datetime as dt
        sc = {'scenes': [{'type': 'titre', 'titre': 'x'}], 'fin': {'duree': 3.8}, 'source': 's'}
        c = {'type_reel': 'pedagogique', 'scenario': sc, 'scrutin': None, 'legende': 'L', 'cle_etat': 'reels_pedagogiques_publies', 'valeur_etat': ['a'], 'id': 'a'}
        mem = {}
        with mock.patch.object(pr, 'contenu_reel', lambda: c), mock.patch.object(pr, 'lire_etat_publication', lambda: dict(mem)), mock.patch.object(pr, 'ecrire_etat_publication', lambda e: mem.update(e)), \
             mock.patch.object(pr.generer_reel, 'generer', lambda *a, **k: {'reel': 'r.mp4', 'couverture': 'c.png', 'duree': 20.0}), mock.patch.object(pr, 'lire_env', lambda: {'IG_USER_ID': 'IG', 'FB_PAGE_TOKEN': 'T', 'FB_PAGE_ID': 'P'}), \
             mock.patch.object(pr, 'publier_reel_instagram', lambda *a, **k: {'id': '1'}), mock.patch.object(pr, 'publier_reel_facebook', lambda *a, **k: '2'):
            pr.main_reel(argparse.Namespace(publier=True, plateformes='facebook,instagram'))
        self.assertEqual(mem['dernier_reel'], {'date': dt.date.today().isoformat(), 'type_reel': 'pedagogique', 'scenario': sc, 'scrutin': None})


if __name__ == '__main__':
    unittest.main()
