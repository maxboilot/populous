"""Test de la logique de publication (API Meta SIMULEE : rien n'est envoyé nulle part).
Lancer : python3 -m unittest carrousels.test_publication -v   (depuis la racine du dépôt)"""
import sys, tempfile, unittest
from pathlib import Path
from unittest import mock
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(RACINE / 'carrousels'))
import publier_reseaux as pr


class FausseApi:
    """Memorise les appels et repond comme le Graph API ; peut simuler divers echecs."""
    def __init__(self, echec_video=None, publish_pas_pret=0, erreur500=0):
        self.appels, self.echec_video, self.n, self.publish_pas_pret, self.erreur500 = [], echec_video, 0, publish_pas_pret, erreur500
        self.ids_video = set()

    def _rep(self, json_=None, statut=200):
        r = mock.Mock(); r.status_code = statut; r.json.return_value = json_ or {}; r.text = str(json_); r.raise_for_status.return_value = None
        if statut >= 400:
            import requests
            r.raise_for_status.side_effect = requests.exceptions.HTTPError(f'{statut}')
        return r

    def post(self, url, data=None, files=None, timeout=None, headers=None):
        nom = url.split('v21.0/')[1] if 'v21.0/' in url else url
        self.appels.append(('POST', nom, dict(data) if isinstance(data, dict) else {'octets': len(data or b'')}))
        self.n += 1
        if 'rupload' in url:
            return self._rep({'error': 'boom'}, 500) if self.echec_video == 'envoi' else self._rep({'success': True})
        if url.endswith('/media_publish') and self.publish_pas_pret > 0:
            self.publish_pas_pret -= 1
            return self._rep({'error': {'code': 9007, 'error_subcode': 2207027, 'message': 'Media ID is not available'}}, 400)
        if url.endswith('/media') and (data or {}).get('is_carousel_item') and self.erreur500 > 0 and (data or {}).get('image_url'):
            self.erreur500 -= 1
            return self._rep({'error': {'code': 1, 'message': 'An unknown error occurred'}}, 500)
        if url.endswith('/media') and (data or {}).get('media_type') == 'VIDEO' and self.echec_video == 'conteneur':
            return self._rep({'error': 'video refusee'}, 400)
        if url.endswith('/media') and (data or {}).get('upload_type') == 'resumable':
            self.ids_video.add(f'id{self.n}')
            return self._rep({'id': f'id{self.n}', 'uri': f'https://rupload.facebook.com/ig-api-upload/v26.0/id{self.n}'})
        return self._rep({'id': f'id{self.n}', 'post_id': f'p{self.n}'})

    def get(self, url, params=None, timeout=None):
        self.appels.append(('GET', url.split('v21.0/')[1], dict(params or {})))
        champs = (params or {}).get('fields', '')
        if champs == 'images':
            return self._rep({'images': [{'source': 'https://cdn.exemple/photo.jpg'}]})
        if self.echec_video == 'statut_erreur' and url.split('/')[-1] in self.ids_video:
            return self._rep({'status_code': 'ERROR', 'status': 'Error: Media upload has failed with error code 2207076'})
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
        publics = [a for a in api.appels if a[0] == 'POST' and a[1].endswith('media_publish')]
        fb_feed = [a for a in api.appels if a[0] == 'POST' and a[1] == 'PAGE/feed']
        return publics, fb_feed

    def enfants(self, api):
        return [a for a in api.appels if a[0] == 'POST' and a[1] == 'IG/media' and a[2].get('is_carousel_item')]

    def test_voie_video_directe_nominale(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(fb), 1); self.assertEqual(len(publics), 1)
        enf = self.enfants(api); self.assertEqual(len(enf), 5)
        self.assertTrue(all(e[2]['media_type'] == 'VIDEO' and e[2]['upload_type'] == 'resumable' for e in enf))
        self.assertEqual(len([a for a in api.appels if 'rupload' in a[1]]), 5)              # 5 envois d'octets directs
        self.assertFalse(any(a[1].endswith('/videos') for a in api.appels))                 # plus de video Facebook intermediaire
        self.assertEqual(sum(1 for k in fb[0][2] if k.startswith('attached_media')), 5)

    def test_repli_images_si_envoi_video_echoue(self):
        api = FausseApi('envoi'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1)                       # une seule publication Instagram, pas de doublon
        self.assertEqual(len([e for e in self.enfants(api) if 'image_url' in e[2]]), 5)

    def test_repli_images_si_conteneur_video_refuse(self):
        api = FausseApi('conteneur'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1); self.assertEqual(len([e for e in self.enfants(api) if 'image_url' in e[2]]), 5)

    def test_repli_images_si_instagram_rejette_la_video(self):      # cas reel du 1er nov. 2026 : statut ERROR 2207076
        api = FausseApi('statut_erreur'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1); self.assertEqual(len([e for e in self.enfants(api) if 'image_url' in e[2]]), 5)

    def test_nouvel_essai_sur_erreur_500(self):
        api = FausseApi('conteneur', erreur500=2)               # video refusee -> images ; 2 erreurs 500 puis succes
        publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len(publics), 1); self.assertGreaterEqual(len([e for e in self.enfants(api) if 'image_url' in e[2]]), 7)

    def test_nouvel_essai_si_contenu_pas_pret(self):
        api = FausseApi(publish_pas_pret=2)
        publics, fb = self.lancer(api, '--type', 'avenir', '--publier')
        tentatives = [a for a in api.appels if a[0] == 'POST' and a[1].endswith('media_publish')]
        self.assertEqual(len(tentatives), 3); self.assertEqual(len({a[2]['creation_id'] for a in tentatives}), 1)

    def test_pas_de_nouvel_essai_pour_une_autre_erreur(self):
        api = FausseApi(); orig = api.post
        def post(url, data=None, files=None, timeout=None, headers=None):
            if url.endswith('/media_publish'):
                api.appels.append(('POST', 'IG/media_publish', dict(data or {})))
                return api._rep({'error': 'autre'}, 400)
            return orig(url, data=data, files=files, timeout=timeout, headers=headers)
        api.post = post
        with self.assertRaises(Exception):
            self.lancer(api, '--type', 'avenir', '--publier')
        self.assertEqual(len([a for a in api.appels if a[1].endswith('media_publish')]), 1)

    def test_rattrapage_instagram_seul_ne_publie_pas_sur_facebook(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir', '--publier', '--plateformes', 'instagram')
        self.assertEqual(len(fb), 0); self.assertEqual(len(publics), 1)

    def test_rattrapage_instagram_seul_avec_repli_images_televerse_sans_publier(self):
        api = FausseApi('conteneur'); publics, fb = self.lancer(api, '--type', 'avenir', '--publier', '--plateformes', 'instagram')
        self.assertEqual(len(fb), 0); self.assertEqual(len(publics), 1)
        self.assertEqual(len([a for a in api.appels if a[0] == 'POST' and a[1] == 'PAGE/photos' and a[2].get('published') == 'false']), 5)

    def test_plateforme_inconnue_refusee(self):
        with self.assertRaises(SystemExit):
            self.lancer(FausseApi(), '--type', 'avenir', '--publier', '--plateformes', 'tiktok')

    def test_brouillon_ne_publie_rien(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir')
        self.assertEqual(api.appels, [])

    def test_option_sans_video(self):
        api = FausseApi(); publics, fb = self.lancer(api, '--type', 'avenir', '--publier', '--sans-video-instagram')
        self.assertFalse(any('rupload' in a[1] for a in api.appels)); self.assertEqual(len(publics), 1)


if __name__ == '__main__':
    unittest.main()
