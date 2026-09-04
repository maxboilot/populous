# Populous — contexte du projet

## Ce qu'est Populous

Application web civique française qui rend visibles et lisibles les votes de
l'Assemblée nationale. Inspirée du Wahl-O-Mat allemand et d'Elyze. Double
ambition : outil viral et partageable pour le cycle électoral 2027, et socle
réutilisable pour d'autres scrutins, français ou étrangers.

Le succès se mesure à la portée organique, à la qualité des partages, et à une
réputation éditoriale irréprochable.

- Dépôt : `maxboilot/populous`
- En ligne : https://maxboilot.github.io/populous/ (GitHub Pages)
- Dossier local : `~/populous-app`

## Règles de collaboration — non négociables

1. **Jamais de `git push` sans accord explicite de Max.** Le déroulé est
   toujours : préparer, expliquer précisément ce qui part, attendre le feu
   vert, puis pousser.
2. **Montrer avant de faire.** Tout correctif ou diff est présenté avant d'être
   appliqué.
3. **Auditer avant de toucher.** En reprise de session, reconstruire l'état
   réel en comparant le dépôt local, `origin/main` et le site en ligne. Ces
   trois états divergent régulièrement.

## Garde-fous éditoriaux — non négociables

- **Aucune position politique fabriquée.** Jamais de prise de position
  attribuée à un député ou un candidat réel sans source vérifiable.
- **Aucune thèse de quiz générée automatiquement** depuis un texte législatif
  sans relecture humaine.
- **Aucun faux fil d'actualité** ni contenu simulé pour la section
  Présidentielle 2027. Le contenu provisoire est toujours étiqueté comme tel.
- **Vie privée par conception.** Les données d'accueil (pseudonyme, tranche
  d'âge, circonscription, marqueurs de mode de vie) restent exclusivement en
  localStorage. Aucune opinion politique n'est transmise à un serveur.

## Architecture

- **Carte** : Leaflet. Les 577 circonscriptions, contours encodés en binaire
  compact et embarqués dans la page. Coloration par vote, groupe, âge ou
  profession.
- **Onglets** : Accueil, Carte, Historique, À venir, Quiz, Présidentielle 2027.
- **Pipeline** : `ingest_scrutins.py`, exécuté par GitHub Actions. Écrit un
  JSON par scrutin dans `data/scrutins/`, plus `data/today.json` et
  `data/state.json`.
- **Front** : un seul fichier `index.html` d'environ 1,2 Mo. Charge les données
  avec no-store, privilégie `featured_numero` puis `last_featured_numero`, avec
  un numéro de secours en dernier recours.
- **Typographie** : Plus Jakarta Sans. Palette claire dite Jour, bleu d'accent
  tiré de l'icône.

## Sources de données

- Archive des scrutins : open data de l'Assemblée nationale (Licence Ouverte).
- Données des députés : projet quinousrepresente (MIT).
- Contours des circonscriptions : jmlahire/GeodataCirconscriptions (2022).

## Leçons acquises

- **Three.js a été abandonné au profit de Leaflet.** Instabilité persistante
  d'orientation et de rendu. Ne pas y revenir.
- **Le site en ligne n'est pas le dépôt local.** Vérifier ce qui est réellement
  déployé avec curl et grep sur la page publiée.
- **Mémoire de pipeline.** Un pipeline déployé en période creuse n'initialise
  jamais son état si celui-ci dépend d'un événement live. D'où
  `backfill_last_featured`, qui reconstruit la mémoire depuis l'archive.
- **La planification GitHub Actions n'est pas fiable.** Les retards observés
  sont allés de 35 minutes à 12 heures. D'où quatre tentatives quotidiennes,
  décalées de l'heure pile, plus un verrou de concurrence.
- **Tests Python en local** : `requests` n'est pas installé sur le Mac. Injecter
  un module factice via `sys.modules` plutôt que d'installer le paquet.

## Fichiers produits

Régénérés chaque matin par le pipeline :

- `data/scrutins/<numero>.json` — une fiche par scrutin, détail par circonscription.
- `data/today.json` — vote vedette du jour, ou mémoire du dernier vote connu.
- `data/state.json` — mémoire du pipeline.
- `data/historique.json` — les lois votées sur douze mois, format riche.
- `data/index.json` — **le fichier que lit réellement l'onglet Historique**.
- `data/agenda.json` — les textes inscrits à l'ordre du jour à venir.
- `data/themes.json` — table des libellés de thèmes pour l'interface.

Construit une fois, hors pipeline quotidien :

- `data/communes.json` — 34 857 communes et leurs circonscriptions (1,9 Mo,
  659 Ko compressés).

## Piège à connaître : historique.json contre index.json

L'onglet Historique cherche `data/index.json`, pas `historique.json`. Un
fichier produit sous le mauvais nom a laissé l'onglet vide en affichant
« L'archive complète arrive bientôt », sans erreur visible. Avant de produire
un fichier de données, vérifier dans `index.html` le nom réellement attendu.

## historique.json et index.json

Produits par `construire_historique.py`. Ne retient que les votes portant sur
un texte entier : sur une année, l'archive compte environ 5 400 scrutins dont
4 700 amendements, mais seulement 113 votes sur texte entier. Ce sont ces
derniers, et eux seuls, que le lecteur appelle des lois.

Aucun résumé n'est généré. Décision éditoriale explicite de Max : le titre
officiel nettoyé plus le lien vers la page du scrutin tiennent lieu de
description. `index.json` est trié du plus ancien au plus récent, car
l'interface applique elle-même un `reverse()`.

## agenda.json et l'onglet À venir

Produit par `construire_agenda.py` depuis `Agenda.json.zip` (7 500 réunions).

Le point clé : le libellé d'un point d'ordre du jour est générique
(« Discussion », « Examen du texte »). Il n'a de sens qu'associé au titre du
dossier législatif visé. On résout donc chaque `dossierRef` via
`Dossiers_Legislatifs.json.zip`. Sans ce croisement, l'onglet est illisible.

Sont écartés : les réunions annulées, et les points de type Nomination,
Audition ou Rapport d'information — ils portent une référence de dossier mais
n'intéressent pas le grand public.

L'horizon réel est de deux à trois semaines : la Conférence des présidents
arrête l'ordre du jour à l'approche. Une liste vide pendant une suspension est
normale, pas une panne.

## Thèmes et filtres

`categories.py` classe chaque texte par mots-clés appliqués au titre officiel.
Volontairement rustique : déterministe, reproductible, corrigeable en une
ligne. Aucun classement par modèle, qui serait une interprétation non
reproductible attribuée à de vraies lois.

**Convention à respecter** : `'mot'` = mot entier (pluriels tolérés),
`'mot*'` = préfixe. Cette distinction n'est pas cosmétique. Une recherche de
simple sous-chaîne produit des absurdités en français : « visa » capture
« visant à » qui ouvre la moitié des titres de loi, « port » capture
« portant », « eau » capture « nouveau ». Un premier essai classait ainsi
61 lois sur 113 en Immigration.

Seize thèmes. L'interface n'affiche que ceux réellement présents dans les
données, triés par nombre décroissant, plus « Tous » et « Non classé ».

## communes.json et la recherche de circonscription

Construit par `construire_communes.py`, sans dépendance externe, à partir de
deux sources en Licence Ouverte :

- INSEE `circo_composition.xlsx` — seule autorité sur le rattachement
  commune / circonscription. Une commune peut relever de plusieurs
  circonscriptions : 130 sont dans ce cas.
- API Géo de l'État — noms, codes postaux, population (qui sert à trier par
  pertinence).

Format d'une entrée : `[nom, clé de recherche, codes postaux, clés de
circonscription, population]`. Les clés sont au format `département|numéro`,
par exemple `69|3`, identique à celui des élus dans `DATA`.

**Deux limites connues.** Paris ressort avec ses 18 circonscriptions,
Marseille avec 7 : il faudrait indexer les arrondissements municipaux, qui ont
leurs propres codes INSEE. Et le fichier ne doit être chargé qu'à l'ouverture
de la recherche, jamais au démarrage, sous peine d'annuler tout le gain de
rapidité de l'accueil.

## Police d'écriture

SF Pro, la police du site d'Apple, **ne peut pas être distribuée sur le web** :
sa licence la réserve aux maquettes destinées aux systèmes Apple. On utilise
donc la pile système recommandée par Apple — `-apple-system`,
`BlinkMacSystemFont`, `system-ui` — avec Inter en repli pour Android et
Windows. Rendu SF Pro natif sur Mac et iPhone, en toute légalité. Ne pas
« corriger » ceci en embarquant un fichier de police.

## Performance de l'accueil

Trois lignes d'`index.html` pèsent 1,12 Mo de contours et de députés embarqués.
Deux correctifs sont en place : un préchargement du vote lancé dès l'en-tête,
et surtout un appel à `renderAccueil()` à la fin de `loadVote()` — sans lui, le
cadre restait bloqué sur « Chargement du dernier vote » jusqu'à ce que
l'utilisateur change d'onglet. C'était la vraie cause de la lenteur perçue.

Le chantier de fond reste de sortir ces 1,12 Mo du fichier.

## Anti-bruit de commits

`verif_changement_utile.py` empêche les quatre exécutions quotidiennes de
committer des fichiers dont seul l'horodatage a bougé. Tout nouveau fichier
généré portant un horodatage doit être ajouté au dictionnaire `VOLATILES`.

## État au 4 septembre 2026

- Pipeline fonctionnel, archive de 8 434 scrutins, quatre exécutions par matinée.
- Dernier vote réel : scrutin 8434 du 21 juillet 2026. Suspension des travaux
  depuis ; reprise attendue à la rentrée.
- Six onglets alimentés par des données réelles. Historique et À venir
  filtrables par thème.
- Dates au format français partout, via la fonction `dateFR`.
- Présidentielle 2027 en tête de l'accueil, sur fond marine.
- Icône Populous installée sur le lanceur du Bureau.

## Chantier suivant

1. **Profil consultable et modifiable.** Aujourd'hui, cliquer sur le profil
   relance la création comme s'il n'existait pas. Il faut afficher les
   informations enregistrées et permettre de les modifier.
2. **Avatar.** À l'inscription, choisir entre une photo, une illustration ou
   une silhouette vide. L'afficher **en haut à gauche** de l'application, et
   non plus en bas à droite.
3. **Recherche par ville ou code postal** dans l'inscription, branchée sur
   `data/communes.json`. La recherche actuelle n'indexe que les noms de
   députés et les départements.
4. Plus loin : le Quiz et la section Présidentielle 2027, où le contenu reste
   un exemple pédagogique étiqueté. Terrain éditorialement délicat.

## Note de méthode

Les modifications d'`index.html` par le canal `osascript` passent par des
scripts de remplacement transférés en base64. Ce canal est fragile : un
transfert de 34 Ko a produit un fichier valide mais **différent de la source**,
sans erreur apparente. Toujours vérifier l'empreinte MD5 après un transfert de
fichier. AppleScript interprète aussi les antislashs et les guillemets doubles
dans les chaînes : les éviter, ou passer par base64.
