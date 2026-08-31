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

## État au 31 août 2026

- Pipeline fonctionnel, archive complète de 8 434 scrutins.
- Dernier vote réel : scrutin 8434 du 21 juillet 2026. Suspension des travaux
  depuis. Reprise attendue à la rentrée.
- Mémoire du dernier vote vedette amorcée et déployée.
- Workflow fiabilisé, validé par une exécution manuelle réussie.

## Chantier suivant

Reconstruire dans `index.html` le carrousel de quiz façon Wahl-O-Mat, le
partage social (image de résultat générée en canvas, Web Share API, secours
X/WhatsApp/presse-papiers) et les balises Open Graph. Ces fonctions avaient été
développées puis perdues avant d'être publiées : elles sont à refaire.

Point de vigilance à la rentrée : vérifier au premier vote à quelle heure le
commit de données apparaît et si l'accueil affiche bien le vote de la veille.
Le délai de publication de l'open data de l'Assemblée est encore inconnu.
