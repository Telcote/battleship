import { api } from "../api.js";
import { empty, esc, matchTable, reason, status, table, time } from "../html.js";
import { poll } from "../life.js";

export async function tournamentView({ root, life, id, actions }) {
  await poll(life, async () => {
    const item = await api(`/tournament/${id}`);
    if (!life.alive) return false;
    root.removeAttribute("aria-busy");
    const games = item.games_per_pair === 1 ? "1 game" : `${item.games_per_pair} games`;
    root.innerHTML = `
      <nav aria-label="breadcrumb"><ul><li><a href="#/">Arena</a></li><li>Tournament</li></ul></nav>
      <hgroup>
        <h1>Tournament ${status(item.status)}</h1>
        <p>${item.players.length} players · ${games} per pair · started ${time(item.created_at)}</p>
      </hgroup>
      ${actions.tournament?.(item) ?? ""}
      <progress value="${item.matches_finished}" max="${item.matches_total}"></progress>
      <p><small>${item.matches_finished} of ${item.matches_total} matches played</small></p>
      <h2>Standings</h2>
      ${table(
        ["#", "Player", "Played", "Won", "Lost", "Drawn", "Technical losses"],
        item.standings.map((row, index) => [
          index + 1,
          `<span title="${esc(row.base_url)}">${esc(row.address)}</span>`,
          row.played,
          `<strong>${row.wins}</strong>`,
          row.losses,
          row.draws,
          faults(row.faults),
        ]),
      )}
      <h2>Matches</h2>
      ${item.matches.length ? matchTable(item.matches) : empty("No matches started yet.")}`;
    return item.status !== "finished";
  });
}

function faults(counts) {
  const entries = Object.entries(counts);
  if (!entries.length) return "—";
  return entries.map(([key, count]) => `${reason(key)} ×${count}`).join(" ");
}
