const POLL_MS = 1500;

// Таймеры экрана живут, пока на нём пользователь: уход по ссылке их гасит.
export function lifecycle(onError) {
  const timers = new Set();
  const life = {
    alive: true,
    onKey: null,
    later(fn, ms) {
      if (!life.alive) return;
      const timer = setTimeout(() => {
        timers.delete(timer);
        if (life.alive) fn();
      }, ms);
      timers.add(timer);
    },
    fail(error) {
      if (life.alive) onError(error);
    },
    dispose() {
      life.alive = false;
      timers.forEach(clearTimeout);
    },
  };
  return life;
}

// `load` возвращает true, пока данные ещё могут измениться.
export async function poll(life, load) {
  if (!(await load()) || !life.alive) return;
  life.later(() => poll(life, load).catch(life.fail), POLL_MS);
}
