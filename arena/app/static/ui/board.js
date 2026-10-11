import { REASONS, esc, reason } from "./html.js";
import { BOARD_SIZE, COLUMNS, COORDINATE, cellName } from "./replay.js";

export function verdict(result) {
  const [, kind] = REASONS[result.reason] ?? [result.reason, "neutral"];
  const title = result.winner ? `${esc(result.winner)} wins` : "No winner";
  return `
    <article class="verdict ${kind}">
      <strong>${title}</strong> ${reason(result.reason)}
      <p>${esc(result.detail)}</p>
    </article>`;
}

export function boardCard(player, board, ships, result) {
  const sunk = (ships ?? []).filter((ship) => ship.length && ship.every((c) => board.sunk.has(c))).length;
  const role =
    result?.winner === player.address ? `<span class="badge win">winner</span>`
    : result?.loser === player.address ? `<span class="badge">loser</span>`
    : "";
  const invalid = (ships ?? []).flat().filter((coordinate) => !COORDINATE.test(coordinate));
  let note = "";
  if (!ships) note = `<p class="invalid">No placement received.</p>`;
  else if (invalid.length) note = `<p class="invalid">Off the board: ${invalid.map(esc).join(", ")}</p>`;
  if (ships && result?.reason === "invalid_placement" && result.loser === player.address) {
    note += `<p class="invalid">Placement as sent:<br />${ships.map((ship) => esc(ship.join(" "))).join("<br />")}</p>`;
  }

  return `
    <article>
      <header>
        <strong>${esc(player.address)}</strong>
        <span>${role} <small>${sunk} / ${ships?.length ?? 0} sunk</small></span>
      </header>
      ${grid(board)}
      ${note}
    </article>`;
}

function grid(board) {
  const cells = [`<span></span>`, ...[...COLUMNS].map((column) => `<span class="label">${column}</span>`)];
  for (let row = 0; row < BOARD_SIZE; row++) {
    cells.push(`<span class="label">${row + 1}</span>`);
    for (let col = 0; col < BOARD_SIZE; col++) {
      const coordinate = cellName(col, row);
      const result = board.shots.get(coordinate);
      const classes = ["cell"];
      if (board.ships.has(coordinate)) classes.push("ship");
      if (board.sunk.has(coordinate)) classes.push("sunk");
      else if (result) classes.push(result === "miss" ? "miss" : "hit");
      if (board.last === coordinate) classes.push("last");
      const label = result ? `${coordinate}: ${result}` : coordinate;
      cells.push(`<span class="${classes.join(" ")}" title="${label}"></span>`);
    }
  }
  return `<div class="board" role="img" aria-label="Board">${cells.join("")}</div>`;
}
