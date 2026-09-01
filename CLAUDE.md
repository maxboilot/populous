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

## Fichiers produits par le pipeline

- `data/scrutins/<numero>.json` — une fiche par scrutin, avec le détail par
  circonscription.
- `data/today.json` — le vote vedette du jour, ou la mémoire du dernier vote
  vedette si l Assemblée ne siège pas.
- `data/historique.json` — les lois votées sur les douze derniers mois.
- `data/agenda.json` — les séances à venir. Vide à ce jour.
- `data/state.json` — mémoire du pipeline : scrutins vus, dernier vote vedette.

## historique.json

Produit par `construire_historique.py`, exécuté par le workflow juste après
l ingestion.

Ne retient que les votes portant sur un texte entier. C est le point clé : sur
une année l archive compte environ 5 400 scrutins, dont 4 700 amendements et
45 motions, mais seulement 113 votes sur texte entier. Ce sont ces derniers,
et eux seuls, que le lecteur appelle des lois. Afficher les amendements
rendrait l onglet illisible.

Chaque entrée porte : numéro, date, titre débarrassé du jargon, titre officiel
intégral, nature (projet ou proposition de loi, organique, constitutionnelle),
stade de lecture, caractère solennel, résultat et décompte, lien vers la page
de l Assemblée.

Aucun résumé n est généré. Décision éditoriale explicite de Max, conforme au
garde-fou sur le contenu auto-généré : le titre nettoyé et le lien vers le
dossier tiennent lieu de description.

## Agenda et onglet À venir

Ce qui a été établi le 1er septembre 2026, à ne pas refaire :

- Le CSV référencé dans le script (`seances_publique_excel.csv`) répond, mais
  ne contient qu un en-tête sans aucune ligne : rien n est programmé pendant
  la suspension. Son URL est en http et redirige, la passer en https.
- Une source bien plus riche existe et n est pas exploitée :
  `.../17/vp/reunions/Agenda.json.zip`, environ 8 Mo, 7 500 réunions. Chaque
  réunion porte son ordre du jour, avec l objet de chaque point et les
  références aux dossiers législatifs.
- Elle contient de vraies réunions futures — 34 au 1er septembre, avec leur
  état : Confirmé, Éventuel ou Annulé. Mais leur ordre du jour est
  intégralement vide. Le dernier ordre du jour renseigné date du 22 juillet.

Conclusion : l horizon réel est de deux à trois semaines, pas un an. L ordre
du jour est arrêté par la Conférence des présidents à l approche de la séance.
L ingestion peut être écrite dès maintenant, elle ne produira du contenu qu à
la rentrée. L onglet doit afficher honnêtement l absence de programmation
plutôt que de laisser croire à une panne.

## Anti-bruit de commits

`verif_changement_utile.py` empêche les quatre exécutions quotidiennes de
committer des fichiers dont seul l horodatage a bougé. Tout nouveau fichier
généré portant un horodatage doit être ajouté au dictionnaire VOLATILES, sinon
le bruit revient.

## État au 1er septembre 2026

- Pipeline fonctionnel, archive complète de 8 434 scrutins.
- Dernier vote réel : scrutin 8434 du 21 juillet 2026. Aucun vote depuis,
  suspension des travaux. Vérifié à la source : le scrutin 8435 n existe pas.
- Mémoire du dernier vote vedette amorcée, déployée, visible sur l accueil.
- Workflow fiabilisé, validé par une exécution manuelle réussie.
- `historique.json` produit et branché dans le pipeline.

## Chantier suivant

1. **Interface de l onglet Historique** : afficher les 113 lois depuis
   `data/historique.json`, avec une recherche par mot-clé. Les données sont
   prêtes, rien à récupérer.
2. **Onglet À venir** : écrire l ingestion depuis `Agenda.json.zip`, sachant
   qu elle ne produira rien avant la rentrée.
3. **Quiz et partage social** : reconstruire dans `index.html` le carrousel
   façon Wahl-O-Mat, l image de résultat générée en canvas, le Web Share API
   et les balises Open Graph. Ces fonctions avaient été développées puis
   perdues avant d être publiées.

Point de vigilance à la rentrée : au premier vote, vérifier à quelle heure le
commit de données apparaît et si l accueil bascule bien sur le vote de la
veille. Le délai de publication de l open data de l Assemblée reste inconnu.
