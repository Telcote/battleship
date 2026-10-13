import { esc } from "/ui/html.js";
import { newTournamentView } from "./new.js";

export const views = { new: newTournamentView };

// Повтор открывает ту же форму, заполненную заранее: перед запуском её можно поправить.
export const actions = {
  tournament: (item) =>
    newTournamentLink(
      item.players.map((player) => player.base_url),
      item.games_per_pair,
      "Run again",
    ),
  match: (summary) =>
    newTournamentLink(
      summary.players.map((player) => player.base_url),
      1,
      "Rematch",
    ),
};

function newTournamentLink(baseUrls, rounds, label) {
  const params = new URLSearchParams();
  baseUrls.forEach((url) => params.append("player", url));
  params.set("rounds", rounds);
  return `<p><a href="#/new?${esc(params)}" role="button" class="secondary outline">${label}</a></p>`;
}
