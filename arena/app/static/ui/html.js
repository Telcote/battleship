export const REASONS = {
  fleet_destroyed: ["fleet destroyed", "win"],
  shot_limit: ["shot limit", "neutral"],
  unavailable: ["unavailable", "fault"],
  timeout: ["timeout", "fault"],
  invalid_placement: ["invalid placement", "fault"],
  invalid_shot: ["invalid shot", "fault"],
  lie: ["lie", "fault"],
  arena_error: ["arena error", "error"],
};

export function table(headers, rows) {
  return `
    <div class="overflow-auto">
      <table class="striped">
        <thead><tr>${headers.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
      </table>
    </div>`;
}

export function matchTable(matches) {
  return table(
    ["Players", "Result", "Shots", "Started"],
    matches.map((item) => [
      `<a href="#/match/${item.match_id}">${versus(item)}</a>`,
      item.result ? reason(item.result.reason) : status(item.status),
      item.shots,
      time(item.created_at),
    ]),
  );
}

function versus(item) {
  return item.players
    .map((player) => {
      const role =
        item.result?.winner === player.address ? "winner"
        : item.result?.loser === player.address ? "loser"
        : "";
      return `<span class="${role}">${esc(player.address)}</span>`;
    })
    .join(" vs ");
}

export function reason(key) {
  const [label, kind] = REASONS[key] ?? [key, "neutral"];
  return `<span class="badge ${kind}">${esc(label)}</span>`;
}

export function status(value) {
  return `<span class="badge status-${esc(value)}">${esc(value)}</span>`;
}

export function empty(text) {
  return `<p class="empty">${esc(text)}</p>`;
}

export function time(iso) {
  return esc(new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "medium" }));
}

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);
}
