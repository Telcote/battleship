# Морской бой: сервис, арена, турнир

* `service/` — игровой сервис: пять ручек контракта, состояние партий в PostgreSQL.
* `arena/` — арена: проводит партию между двумя сервисами, судит её и проводит турниры.
* `arena/rogue/` — игрок-жулик для проверки арены.

Всё запускается через Docker Compose. Нужны Docker с плагином `compose`.

```bash
cp .env.example .env
```

## Профили Compose

| Профиль | Сервисы | Для чего |
| --- | --- | --- |
| без профиля | `db`, `app` (:8000), `app2` (:8001), `arena` (:80) | два экземпляра сервиса и арена |
| `test` | `tests`, `arena-tests` | тесты сервиса и арены |
| `rogue` | `rogue` (:8200) | игрок-жулик для проверки арены |

Сервисы из профиля поднимаются, только если профиль указан явно (`--profile …`) или сервис
назван в команде по имени.

## Тесты

Тесты сервиса (нужна БД — `db` поднимется сам):

```bash
docker compose run --rm --build tests
```

Тесты арены (БД не нужна, игроки подменены заглушками):

```bash
docker compose run --rm --build arena-tests
```

Отдельный файл или тест — аргументами pytest. У сервиса команда по умолчанию сначала
накатывает миграции, поэтому при её замене `alembic upgrade head` нужно оставить:

```bash
docker compose run --rm tests sh -c "alembic upgrade head && pytest tests/integration/test_parallel_games.py"
docker compose run --rm arena-tests pytest -k tournament
```

## Сервис и арена

```bash
docker compose up -d --build
```

Миграции сервиса накатываются при старте. Проверка: `curl localhost:8000/health`,
`curl localhost/health`.

### Одна партия

```bash
curl -X POST localhost/match -H 'content-type: application/json' \
  -d '{"players": [{"base_url": "http://app:8000"}, {"base_url": "http://app2:8000"}]}'

curl localhost/match/<match_id>        # статус и итог
curl localhost/match/<match_id>/log    # все выстрелы по порядку
```

Адреса игроков арена разрешает из своего контейнера, поэтому внутри compose — имена
сервисов (`app`, `app2`), а не `localhost`.

### Турнир

Каждый с каждым, `games_per_pair` партий на пару; одновременно идёт не больше
`TOURNAMENT_PARALLEL` партий (по умолчанию 4).

```bash
curl -X POST localhost/tournament -H 'content-type: application/json' \
  -d '{"players": [{"base_url": "http://app:8000"}, {"base_url": "http://app2:8000"}],
       "games_per_pair": 5, "seed": 1}'

curl localhost/tournament/<tournament_id>   # прогресс и турнирная таблица
```

Турниры и партии хранятся в памяти арены: перезапуск контейнера их стирает.

## Проверка арены жуликом

Жулик — один контейнер, режим задаётся первым сегментом пути: `http://rogue:8200/liar`,
`http://rogue:8200/slow` и т.д. Список режимов — `curl localhost:8200/modes`.

```bash
docker compose --profile rogue up -d --build app arena rogue
docker compose exec arena python -m rogue.check
```

`rogue.check` играет честным сервисом против каждого режима и сверяет, что жулик проиграл
по своей причине (`lie`, `timeout`, `invalid_shot`, …). Код выхода 1 — что-то пошло не так.

Чужую арену или чужой сервис можно проверить, переопределив адреса:

```bash
docker compose exec -e ARENA_URL=http://<арена> -e HONEST_URL=http://<сервис> \
  arena python -m rogue.check
```

## Остановка

```bash
docker compose --profile rogue down        # остановить всё
docker compose --profile rogue down -v     # и удалить данные БД
```

## Если Docker не на этой машине

В devcontainer с Docker-outside-of-Docker опубликованные порты живут на хосте, и
`localhost` (порт 80) изнутри контейнера разработки недоступен. Запросы тогда шлются из
контейнера арены:

```bash
docker compose exec arena python -c "import httpx; print(httpx.get('http://localhost:8100/health').json())"
```
