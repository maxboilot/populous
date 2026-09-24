import { creneauxDus } from "./worker.js";
const cas = [
  ["2026-09-25T05:00:00Z","été 7h"], ["2026-09-25T06:00:00Z","été 8h"], ["2026-09-28T07:00:00Z","lundi 9h été"],
  ["2026-09-25T10:30:00Z","12h30"], ["2026-09-25T16:30:00Z","18h30"], ["2026-10-15T18:00:00Z","15 oct 20h"],
  ["2026-09-25T19:00:00Z","21h"], ["2026-11-02T08:00:00Z","lundi 9h hiver"], ["2026-11-03T06:00:00Z","7h hiver"],
  ["2026-09-25T10:00:00Z","12h00 sondages"], ["2026-09-25T09:00:00Z","11h (rien)"], ["2026-09-25T07:00:00Z","9h mardi (rien)"], ["2026-10-14T18:00:00Z","14 oct 20h (rien)"],
];
for (const [iso, nom] of cas) console.log(nom.padEnd(20), creneauxDus(Date.parse(iso)).map(c=>c.workflow.split("_")[0]+":"+c.type).join(", ") || "—");
