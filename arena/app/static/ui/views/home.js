import { api } from "../api.js";
import { empty, matchTable, status, table, time } from "../html.js";
import { poll } from "../life.js";

export async function homeView({ root, life }) {
  await poll(life, async () => {
    const [tournaments, matches] = await Promise.all([api("/tournament"), api("/match")]);
    if (!life.alive) return false;
    root.removeAttribute("aria-busy");
    root.innerHTML = `
      <hgroup>
        <h1>Arena</h1>
        <p>Tournaments and recent matches. Updates live.</p>
      </hgroup>
      <h2>Tournaments</h2>
      ${tournaments.length ? tournamentTable(tournaments) : empty("No tournaments yet.")}
      <h2>Recent matches</h2>
      ${matches.length ? matchTable(matches) : empty("No matches yet.")}`;
    // Новые матчи и турниры могут появиться в любой момент.
    return true;
  });
}

function tournamentTable(tournaments) {
  return table(
    ["Started", "Status", "Players", "Played"],
    tournaments.map((item) => [
      `<a href="#/tournament/${item.tournament_id}">${time(item.created_at)}</a>`,
      status(item.status),
      item.players.length,
      `${item.matches_finished} / ${item.matches_total}`,
    ]),
  );
}
