import { api } from "../api.js";
import { boardCard, verdict } from "../board.js";
import { esc, status, time } from "../html.js";
import { poll } from "../life.js";
import { replay } from "../replay.js";

const KEYS = { ArrowLeft: "prev", ArrowRight: "next", Home: "start", End: "end", " ": "play" };

export async function matchView({ root, life, id, actions }) {
  let summary = null;
  let log = null;
  let step = 0;
  // Следим за последним выстрелом, пока пользователь не отмотал назад.
  let follow = true;
  let playing = false;
  let playToken = 0;

  root.innerHTML = `
    <nav aria-label="breadcrumb"><ul><li><a href="#/">Arena</a></li><li>Match</li></ul></nav>
    <div id="head"></div>
    <div class="player">
      <div role="group">
        <button class="secondary" data-act="start" title="First shot (Home)" aria-label="First shot">⏮</button>
        <button class="secondary" data-act="prev" title="Previous shot (←)" aria-label="Previous shot">‹</button>
        <button data-act="play" title="Play / pause (Space)" aria-label="Play">▶</button>
        <button class="secondary" data-act="next" title="Next shot (→)" aria-label="Next shot">›</button>
        <button class="secondary" data-act="end" title="Last shot (End)" aria-label="Last shot">⏭</button>
      </div>
      <input type="range" id="scrub" min="0" max="0" value="0" aria-label="Shot" />
      <span class="counter" id="counter"></span>
      <select id="speed" aria-label="Playback speed">
        <option value="2">Slow</option>
        <option value="5" selected>Normal</option>
        <option value="15">Fast</option>
      </select>
    </div>
    <div class="boards" id="boards"></div>
    <div class="legend">
      <span><i class="cell"></i>Water</span>
      <span><i class="cell ship"></i>Ship</span>
      <span><i class="cell miss"></i>Miss</span>
      <span><i class="cell hit"></i>Hit</span>
      <span><i class="cell sunk"></i>Sunk</span>
    </div>
    <h2>Shots</h2>
    <ol class="events" id="events"></ol>`;

  const $ = (selector) => root.querySelector(selector);
  const scrub = $("#scrub");
  const speed = $("#speed");
  const playButton = $('[data-act="play"]');

  const total = () => log?.events.length ?? 0;
  const finished = () => summary?.status === "finished";

  function goTo(target) {
    if (!log) return;
    step = Math.max(0, Math.min(total(), target));
    follow = step === total();
    renderStep();
  }

  function setPlaying(value) {
    playing = value;
    playButton.textContent = playing ? "⏸" : "▶";
    playButton.setAttribute("aria-label", playing ? "Pause" : "Play");
    if (!playing) return;
    if (step >= total() && finished()) goTo(0);
    const token = ++playToken;
    const tick = () => {
      if (!playing || token !== playToken) return;
      if (step < total()) goTo(step + 1);
      else if (finished()) return setPlaying(false);
      life.later(tick, 1000 / Number(speed.value));
    };
    life.later(tick, 1000 / Number(speed.value));
  }

  const controls = {
    start: () => goTo(0),
    prev: () => goTo(step - 1),
    next: () => goTo(step + 1),
    end: () => goTo(total()),
    play: () => setPlaying(!playing),
  };

  root.querySelectorAll("[data-act]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.act !== "play") setPlaying(false);
      controls[button.dataset.act]();
    });
  });
  scrub.addEventListener("input", () => {
    setPlaying(false);
    goTo(Number(scrub.value));
  });
  $("#events").addEventListener("click", (event) => {
    const button = event.target.closest("[data-step]");
    if (!button) return;
    setPlaying(false);
    goTo(Number(button.dataset.step));
  });

  life.onKey = (event) => {
    const action = KEYS[event.key];
    if (!action || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest("input, select, textarea, button")) return;
    event.preventDefault();
    if (action !== "play") setPlaying(false);
    controls[action]();
  };

  function renderHead() {
    const [first, second] = summary.players;
    const shots = summary.shots === 1 ? "1 shot" : `${summary.shots} shots`;
    const opener = summary.first_move ? ` · ${esc(summary.first_move)} moved first` : "";
    $("#head").innerHTML = `
      <hgroup>
        <h1>${esc(first.address)} vs ${esc(second.address)}</h1>
        <p>${status(summary.status)} · ${shots}${opener} · started ${time(summary.created_at)}</p>
      </hgroup>
      ${actions.match?.(summary) ?? ""}
      ${summary.result ? verdict(summary.result) : ""}`;
  }

  function renderStep() {
    const boards = replay(summary.players, log.ships, log.events, step);
    $("#boards").innerHTML = summary.players
      .map((player) => boardCard(player, boards[player.address], log.ships[player.address], summary.result))
      .join("");

    scrub.max = total();
    scrub.value = step;
    $("#counter").textContent = `Shot ${step} / ${total()}`;

    const events = $("#events");
    events.innerHTML = log.events.length
      ? log.events.map((event) => shotItem(event, step)).join("")
      : `<li class="empty">No shots were fired.</li>`;
    const current = events.querySelector(".current");
    if (current) events.scrollTop = current.offsetTop - events.clientHeight / 2;
  }

  await poll(life, async () => {
    // Сводка раньше лога: если матч уже закончен, лог гарантированно полный.
    const nextSummary = await api(`/match/${id}`);
    const nextLog = await api(`/match/${id}/log`);
    if (!life.alive) return false;
    summary = nextSummary;
    log = nextLog;
    if (follow && !playing) step = total();
    root.removeAttribute("aria-busy");
    renderHead();
    renderStep();
    return !finished();
  });
}

function shotItem(event, step) {
  const state = event.number === step ? "current" : event.number > step ? "future" : "";
  return `
    <li class="${state}">
      <button data-step="${event.number}">
        <span class="number">#${event.number}</span>
        <span>${esc(event.attacker)} → <strong>${esc(event.coordinate)}</strong></span>
        <span>${esc(event.result)}</span>
      </button>
    </li>`;
}
