// Planificateur externe (Cloudflare Workers) : déclenche à l'heure exacte
// les workflows GitHub Actions de publication et de notification. Les
// crons de GitHub subissent 1 à 9 h de retard (constaté sur 30 exécutions,
// septembre 2026) ; celui de Cloudflare part à la minute près.
//
// Le cron Cloudflare est en UTC ; on se réveille donc toutes les 30 min et
// on compare à l'heure de Paris (Intl, Europe/Paris) : les changements
// d'heure été/hiver n'exigent aucune modification.

const DEPOT = "maxboilot/populous";
const BRANCHE = "main";

// h/m : heure de Paris. jourSemaine : 1 = lundi … 7 = dimanche. jourMois : 1-31.
const CRENEAUX = [
  // Collecte des sondages 30 min avant la publication présidentielle : les
  // crons GitHub de sondages.yml sont retardés de plusieurs heures, un
  // sondage sorti le matin pouvait donc attendre le lendemain.
  { h: 12, m: 0,  workflow: "sondages.yml", sansInputs: true },
  { h: 7,  m: 0,  workflow: "publier_reseaux.yml",   type: "fait" },
  { h: 8,  m: 0,  workflow: "notifier_planifie.yml", type: "fait" },
  { h: 9,  m: 0,  jourSemaine: 1, workflow: "publier_reseaux.yml",   type: "avenir" },
  { h: 9,  m: 0,  jourSemaine: 1, workflow: "notifier_planifie.yml", type: "semaine" },
  { h: 12, m: 30, workflow: "publier_reseaux.yml",   type: "presidentiel" },
  { h: 18, m: 30, workflow: "notifier_planifie.yml", type: "solennel" },
  { h: 20, m: 0,  jourMois: 15, workflow: "publier_reseaux.yml", type: "boussole" },
  { h: 21, m: 0,  workflow: "publier_reseaux.yml",   type: "depute" },
];

const JOURS = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };

export function heureParis(ms) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit", day: "2-digit",
      weekday: "short", hourCycle: "h23",
    }).formatToParts(new Date(ms)).map(x => [x.type, x.value])
  );
  return { h: +p.hour, m: +p.minute, jourMois: +p.day, jourSemaine: JOURS[p.weekday] };
}

export function creneauxDus(ms) {
  const t = heureParis(ms);
  return CRENEAUX.filter(c =>
    c.h === t.h && c.m === t.m &&
    (c.jourSemaine === undefined || c.jourSemaine === t.jourSemaine) &&
    (c.jourMois === undefined || c.jourMois === t.jourMois));
}

async function declencher(c, jeton) {
  const inputs = c.sansInputs ? {} : { type: c.type };
  if (c.workflow === "notifier_planifie.yml") inputs.dry_run = "false";
  const url = `https://api.github.com/repos/${DEPOT}/actions/workflows/${c.workflow}/dispatches`;
  for (let essai = 1; essai <= 3; essai++) {
    const r = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jeton}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "populous-planificateur",
      },
      body: JSON.stringify({ ref: BRANCHE, inputs }),
    });
    if (r.status === 204) { console.log(`OK ${c.workflow} ${c.type || ""}`); return true; }
    console.log(`Échec ${c.workflow} ${c.type} (essai ${essai}) : ${r.status} ${await r.text()}`);
    await new Promise(res => setTimeout(res, 2000 * essai));
  }
  return false;
}

export default {
  async scheduled(event, env, ctx) {
    const dus = creneauxDus(event.scheduledTime);
    console.log(`Réveil ${new Date(event.scheduledTime).toISOString()} : ${dus.length} déclenchement(s)`);
    ctx.waitUntil(Promise.all(dus.map(c => declencher(c, env.GITHUB_TOKEN))));
  },
  async fetch() {
    return new Response("Populous planificateur", { status: 200 });
  },
};
