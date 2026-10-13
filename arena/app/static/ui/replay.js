export const COLUMNS = "ABCDEFGHIJ";
export const BOARD_SIZE = 10;
export const COORDINATE = /^([A-J])(10|[1-9])$/;

// Повтор: состояние обоих полей после первых `step` выстрелов.
// Поле игрока — его корабли и выстрелы соперника по ним.
export function replay(players, ships, events, step) {
  const boards = {};
  for (const player of players) {
    boards[player.address] = {
      ships: new Set((ships[player.address] ?? []).flat()),
      shots: new Map(),
      sunk: new Set(),
      last: null,
    };
  }
  for (const event of events.slice(0, step)) {
    const defender = players.find((player) => player.address !== event.attacker);
    const board = defender && boards[defender.address];
    if (!board) continue;
    board.shots.set(event.coordinate, event.result);
    if (event.result === "killed") sink(board, event.coordinate);
  }
  const last = events[step - 1];
  const target = last && players.find((player) => player.address !== last.attacker);
  if (target) boards[target.address].last = last.coordinate;
  return boards;
}

// Корабли не касаются друг друга даже углами, поэтому потопленный корабль — это ровно
// связная по стороне группа попаданий вокруг добивающего выстрела.
function sink(board, start) {
  const stack = [start];
  while (stack.length) {
    const coordinate = stack.pop();
    if (board.sunk.has(coordinate)) continue;
    board.sunk.add(coordinate);
    for (const next of neighbours(coordinate)) {
      const result = board.shots.get(next);
      if (result === "hit" || result === "killed") stack.push(next);
    }
  }
}

function neighbours(coordinate) {
  const match = COORDINATE.exec(coordinate);
  if (!match) return [];
  const col = COLUMNS.indexOf(match[1]);
  const row = Number(match[2]) - 1;
  return [
    [col + 1, row],
    [col - 1, row],
    [col, row + 1],
    [col, row - 1],
  ]
    .map(([c, r]) => cellName(c, r))
    .filter(Boolean);
}

export function cellName(col, row) {
  if (col < 0 || col >= BOARD_SIZE || row < 0 || row >= BOARD_SIZE) return null;
  return `${COLUMNS[col]}${row + 1}`;
}
