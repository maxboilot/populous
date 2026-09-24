# Planificateur externe (Cloudflare Workers)

Déclenche à l'heure exacte les workflows GitHub (`publier_reseaux.yml`,
`notifier_planifie.yml`) via l'API `workflow_dispatch`, parce que les crons
de GitHub ont 1 à 9 h de retard. Voir `worker.js` pour le tableau des
créneaux (heures de Paris, changement d'heure géré automatiquement).

| Heure (Paris)      | Action                                   |
|--------------------|------------------------------------------|
| 7h00               | Publication « fait du jour »              |
| 8h00               | Notification « Découvre le fait du jour » |
| Lundi 9h00         | Publication « à venir » + notification « cette semaine à l'Assemblée » |
| 12h00              | Collecte des sondages (sondages.yml), pour que la publication de 12h30 voie les nouveautés |
| 12h30              | Publication « actu présidentielle »       |
| 18h30              | Notification « vote solennel demain »     |
| 20h00, le 15       | Publication « boussole »                  |
| 21h00              | Publication « député du jour »            |

## Mise en place

1. Compte Cloudflare gratuit : https://dash.cloudflare.com/sign-up
2. `cd planificateur && npx wrangler login`
3. Jeton GitHub (fine-grained) : https://github.com/settings/personal-access-tokens/new
   dépôt `maxboilot/populous` uniquement, permission **Actions : Read and write**.
4. `npx wrangler secret put GITHUB_TOKEN` (coller le jeton)
5. `npx wrangler deploy`
6. Une fois actif, supprimer les blocs `schedule:` de `publier_reseaux.yml` et
   `notifier_planifie.yml` (sinon double publication).

Test de la logique horaire : `node test.mjs`. Logs : `npx wrangler tail`.
Le jeton GitHub expire (choisir la durée max) : penser à le renouveler.
