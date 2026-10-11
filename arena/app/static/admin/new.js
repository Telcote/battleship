import { api } from "/ui/api.js";
import { esc } from "/ui/html.js";

const MIN_PLAYERS = 2;
const MAX_ROUNDS = 100;
const RECENT_KEY = "arena:recent-players";
const RECENT_LIMIT = 20;

export async function newTournamentView({ root, params }) {
  const initial = params.getAll("player");
  while (initial.length < MIN_PLAYERS) initial.push("");
  const rounds = Number(params.get("rounds")) || 1;

  root.removeAttribute("aria-busy");
  root.innerHTML = `
    <nav aria-label="breadcrumb"><ul><li><a href="#/">Arena</a></li><li>New tournament</li></ul></nav>
    <hgroup>
      <h1>New tournament</h1>
      <p>Every player plays every other player. A 1 vs 1 match is a tournament of two.</p>
    </hgroup>
    <form id="form" novalidate>
      <fieldset>
        <legend>Players</legend>
        <div id="players"></div>
        <button type="button" class="secondary outline" id="add">+ Add player</button>
      </fieldset>
      <div class="grid">
        <label>
          Rounds per pair
          <input type="number" id="rounds" min="1" max="${MAX_ROUNDS}" step="1" value="${rounds}" />
        </label>
        <label>
          Seed <small>(optional)</small>
          <input type="number" id="seed" step="1" placeholder="random" />
        </label>
      </div>
      <p id="summary"></p>
      <p id="error" class="form-error" role="alert" hidden></p>
      <button type="submit" id="submit">Start tournament</button>
    </form>
    <datalist id="recent">${recent().map((url) => `<option value="${esc(url)}"></option>`).join("")}</datalist>`;

  const $ = (selector) => root.querySelector(selector);
  const list = $("#players");
  const error = $("#error");
  // Пустые и кривые адреса подсвечиваем только после первой попытки отправить форму.
  let submitted = false;

  const entries = () => [...list.querySelectorAll(".entry")];
  const urls = () => entries().map((entry) => entry.querySelector("input").value.trim());

  function addPlayer(value = "") {
    list.insertAdjacentHTML("beforeend", playerEntry(value));
    refresh();
  }

  function refresh() {
    const values = urls();
    const counts = new Map();
    for (const url of values) if (url) counts.set(normalize(url), (counts.get(normalize(url)) ?? 0) + 1);

    let valid = true;
    entries().forEach((entry, index) => {
      const url = values[index];
      let problem = "";
      if (counts.get(normalize(url)) > 1) problem = "This player is already in the list.";
      else if (submitted && !url) problem = "Enter the player's base URL.";
      else if (submitted && !/^https?:\/\/[^\s/]+/i.test(url)) problem = "Must start with http:// or https://";
      if (!url || problem) valid = false;
      setProblem(entry, problem);
      entry.querySelector(".remove").disabled = values.length <= MIN_PLAYERS;
    });

    const roundsInput = $("#rounds");
    const roundsValue = Number(roundsInput.value);
    const roundsOk = Number.isInteger(roundsValue) && roundsValue >= 1 && roundsValue <= MAX_ROUNDS;
    if (roundsOk) roundsInput.removeAttribute("aria-invalid");
    else roundsInput.setAttribute("aria-invalid", "true");

    const players = values.length;
    const pairs = (players * (players - 1)) / 2;
    $("#summary").innerHTML = roundsOk
      ? `${players} players · ${plural(pairs, "pair")} · ${plural(roundsValue, "round")} each =
         <strong>${plural(pairs * roundsValue, "match", "matches")}</strong>`
      : `Rounds per pair must be between 1 and ${MAX_ROUNDS}.`;
    return valid && roundsOk;
  }

  // Ошибку сервера показываем у того игрока, о котором она: в ней процитирован его адрес или хост.
  function showServerError(detail) {
    let placed = false;
    entries().forEach((entry, index) => {
      const url = urls()[index];
      if (url && [url, hostOf(url)].some((part) => part && detail.includes(`'${part}'`))) {
        setProblem(entry, detail);
        placed = true;
      }
    });
    error.textContent = placed ? "" : detail;
    error.hidden = placed;
  }

  $("#add").addEventListener("click", () => {
    addPlayer();
    list.lastElementChild.querySelector("input").focus();
  });
  list.addEventListener("click", (event) => {
    const button = event.target.closest(".remove");
    if (!button) return;
    button.closest(".entry").remove();
    refresh();
  });
  $("#form").addEventListener("input", () => {
    error.hidden = true;
    refresh();
  });
  $("#form").addEventListener("submit", async (event) => {
    event.preventDefault();
    submitted = true;
    if (!refresh()) return;

    const players = urls();
    const body = {
      players: players.map((base_url) => ({ base_url })),
      games_per_pair: Number($("#rounds").value),
    };
    const seed = $("#seed").value.trim();
    if (seed !== "") body.seed = Number(seed);

    const submit = $("#submit");
    submit.disabled = true;
    submit.setAttribute("aria-busy", "true");
    try {
      const created = await api("/tournament", body);
      remember(players);
      location.hash = `#/tournament/${created.tournament_id}`;
    } catch (failure) {
      showServerError(failure.message);
    } finally {
      submit.disabled = false;
      submit.removeAttribute("aria-busy");
    }
  });

  initial.forEach(addPlayer);
}

function playerEntry(value) {
  return `
    <div class="entry">
      <div role="group">
        <input type="url" list="recent" placeholder="http://host:port" value="${esc(value)}"
               aria-label="Player base URL" autocomplete="off" />
        <button type="button" class="secondary outline remove" aria-label="Remove player">✕</button>
      </div>
      <small></small>
    </div>`;
}

function setProblem(entry, problem) {
  const input = entry.querySelector("input");
  if (problem) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
  entry.querySelector("small").textContent = problem;
}

function normalize(url) {
  return url.trim().toLowerCase().replace(/\/+$/, "");
}

function hostOf(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function plural(count, one, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`;
}

// Недавние адреса — подсказки в полях. Хранилище браузера может быть недоступно: тогда без них.
function recent() {
  try {
    const stored = JSON.parse(localStorage.getItem(RECENT_KEY));
    return Array.isArray(stored) ? stored : [];
  } catch {
    return [];
  }
}

function remember(players) {
  try {
    const merged = [...new Set([...players, ...recent()])].slice(0, RECENT_LIMIT);
    localStorage.setItem(RECENT_KEY, JSON.stringify(merged));
  } catch {
    // без подсказок форма работает так же
  }
}
