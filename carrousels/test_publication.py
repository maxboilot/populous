"""Test de la logique de publication (API Meta SIMULEE : rien n'est envoyé nulle part).
Lancer : python3 -m unittest carrousels.test_publication -v   (depuis la racine du dépôt)"""
import sys, tempfile, unittest
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(RACINE / 'carrousels'))
import publier_reseaux as pr


class FausseApi:
    """Mémorise les appels et répond comme le Graph API ; peut simuler un échec de la voie vidéo."""
    def __init__(self, echec_video=None, publish_pas_pret=0):
        self.appels, self.echec_video, self.n, self.publish_pas_pret = [], echec_video, 0, publish_pas_pret

    def _rep(self, json_=None, statut=200):
        r = mock.Mock(); r.status_code = statut; r.json.return_value = json_ or {}; r.text = str(json_); r.raise_for_status.return_value = None
        if statut >= 400:
            import requests
            r.raise_for_status.side_effect = requests.exceptions.HTTPError(f'{statut}')
        return r

    def post(self, url, data=None, files=None, timeout=None):
        self.appels.append(('POST', url.split('v21.0/')[1], dict(data or {})))
        self.n += 1
        if url.endswith('/media_publish') and self.publish_pas_pret > 0:
            self.publish_pas_pret -= 1
            return self._rep({'error': {'code': 9007, 'error_subcode': 2207027, 'message': 'Media ID is not available'}}, 400)
        if url.endswith('/videos') and self.echec_video == 'televersement':
            return self._rep({'error': 'boom'}, 500)
        if url.endswith('/media') and (data or {}).get('media_type') == 'VIDEO' and self.echec_video == 'conteneur':
            return self._rep({'error': 'video refusee'}, 400)
        return self._rep({'id': f'id{self.n}', 'post_id': f'p{self.n}'})

    def get(self, url, params=None, timeout=None):
        self.appels.append(('GET', url.split('v21.0/')[1], dict(params or {})))
        champs = (params or {}).get('fields', '')
        if champs == 'images':
            return self._rep({'images': [{'source': 'https://cdn.exemple/photo.jpg'}]})
        if champs == 'source,status':
            return self._rep({'source': 'https://cdn.exemple/video.mp4', 'status': {'video_status': 'ready'}})
        return self._rep({'status_code': 'FINISHED'})


def faux_carrousel(type_, sortie, **k):
    d = Path(tempfile.mkdtemp(prefix='faux-carrousel-')); d.mkdir(parents=True, exist_ok=True); r = {'slides_mp4': [], 'slides_png': [], 'apercu': d / 'apercu_swipe.mp4'}
    for i in range(1, 6):
        for ext, cle in (('mp4', 'slides_mp4'), ('png', 'slides_png')):
            p = d / f'slide_{i}.{ext}'; p.write_bytes(b'x' * 3000); r[cle].append(p)
    r['apercu'].write_bytes(b'x' * 3000); return r


class TestPublication(unittest.TestCase):
    def lancer(self, api, *argv):
        with mock.patch.object(pr.requests, 'post', api.post), mock.patch.object(pr.requests, 'get', api.get), \
             mock.patch.object(pr.generer_carrousel, 'generer', faux_carrousel), mock.patch.object(pr, 'lire_env', lambda: {'FB_PAGE_ID': 'PAGE', 'FB_PAGE_TOKEN': 'TOK', 'IG_USER_ID': 'IG'}), \
             mock.patch.object(pr, 'time', mock.Mock(sleep=lambda s: None, time=__import__('time').time)), \
             mock.patch.object(pr, 'ecrire_etat_publication', lambda e: None), mock.patch.object(sys, 'argv', ['publier_reseaux.py', *argv]):
            pr.main()
        publics = [a for a in api.appels if a[0] == 'POST' and a[1].endswith('media_publish') and not a[2].get('_refuse')]
        fb_feed = [a for a in api.appels if a[0] == 'POST' and a[1] == 'PAGE/feed']
        return publics, fb_feed

    def test_voie_video_nominale(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(fb), 1); self.assertEqual(len(publics), 1)
        enfants = [a for a in api.appels if a[0] == 'POST' and a[1] == 'IG/media' and a[2].get('is_carousel_item')]
        self.assertEqual(len(enfants), 5); self.assertTrue(all(e[2]['media_type'] == 'VIDEO' for e in enfants))
        self.assertEqual(sum(1 for a in fb[0][2] if a.startswith('attached_media')), 5)

    def test_repli_images_si_televersement_video_echoue(self):
        api = FausseApi('televersement'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1)                       # une seule publication Instagram, pas de doublon
        enfants = [a for a in api.appels if a[0] == 'POST' and a[1] == 'IG/media' and a[2].get('is_carousel_item')]
        self.assertEqual(len(enfants), 5); self.assertTrue(all('image_url' in e[2] for e in enfants))

    def test_repli_images_si_conteneur_video_refuse(self):
        api = FausseApi('conteneur'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1)
        derniers = [a for a in api.appels if a[0] == 'POST' and a[1] == 'IG/media' and a[2].get('image_url')]
        self.assertEqual(len(derniers), 5)

    def test_nouvel_essai_si_contenu_pas_pret(self):
        api = FausseApi(publish_pas_pret=2)                     # 2 refus 2207027 puis succes
        publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        tentatives = [a for a in api.appels if a[0] == 'POST' and a[1].endswith('media_publish')]
        self.assertEqual(len(tentatives), 3)                    # 2 refus + 1 succes, meme conteneur
        self.assertEqual(len({a[2]['creation_id'] for a in tentatives}), 1)

    def test_pas_de_nouvel_essai_pour_une_autre_erreur(self):
        api = FausseApi()
        orig = api.post
        def post(url, data=None, files=None, timeout=None):
            if url.endswith('/media_publish'):
                api.appels.append(('POST', url.split('v21.0/')[1], dict(data or {})))
                return api._rep({'error': 'autre'}, 400)
            return orig(url, data=data, files=files, timeout=timeout)
        api.post = post
        with self.assertRaises(Exception):
            self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len([a for a in api.appels if a[1].endswith('media_publish')]), 1)

    def test_brouillon_ne_publie_rien(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir')
        self.assertEqual(api.appels, [])

    def test_option_sans_video(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir', '--publier', '--sans-video-instagram')
        self.assertFalse(any(a[1].endswith('/videos') for a in api.appels)); self.assertEqual(len(publics), 1)


if __name__ == '__main__':
    unittest.main()
