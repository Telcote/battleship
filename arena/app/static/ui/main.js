import { esc } from "./html.js";
import { lifecycle } from "./life.js";
import { homeView } from "./views/home.js";
import { matchView } from "./views/match.js";
import { tournamentView } from "./views/tournament.js";

const VIEWS = { match: matchView, tournament: tournamentView };

// `views` добавляет экраны, `actions` — кнопки на существующих: так панель управления
// достраивает просмотрщик, не трогая его файлы.
export function start({ views = {}, actions = {} } = {}) {
  const root = document.getElementById("app");
  const routes = { ...VIEWS, ...views };
  let view = null;

  const route = () => {
    view?.dispose();
    const life = (view = lifecycle((error) => fail(root, error)));
    const [, kind, id, query = ""] = location.hash.match(/^#\/(\w*)(?:\/([\w-]+))?(?:\?(.*))?$/) ?? [];
    const show = routes[kind] ?? homeView;
    root.setAttribute("aria-busy", "true");
    root.innerHTML = "";
    window.scrollTo(0, 0);
    show({ root, life, id, params: new URLSearchParams(query), actions }).catch(life.fail);
  };

  window.addEventListener("hashchange", route);
  document.addEventListener("keydown", (event) => view?.onKey?.(event));
  route();
}

function fail(root, error) {
  root.removeAttribute("aria-busy");
  root.innerHTML = `
    <article class="verdict error">
      <strong>Couldn't load this page</strong>
      <p>${esc(error.message)}</p>
    </article>
    <a href="#/">← Back to overview</a>`;
}
