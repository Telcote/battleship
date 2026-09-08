# Стадии:
#   base    — интерпретатор и зависимости из pyproject
#   source  — код сервиса и миграции
#   runtime — прод-образ: alembic upgrade head + uvicorn  (target по умолчанию)
#   test    — то же плюс pytest и tests/

# 3.13, а не 3.14: под 3.14 нет колёс asyncpg 0.30, сборка ушла бы в компиляцию из исходников.
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 app

# Список зависимостей берём из pyproject, чтобы не заводить второй источник истины
# в requirements.txt. Сам пакет не устанавливаем: в app/ нет __init__.py, модули
# импортируются из WORKDIR — так же, как при локальном запуске.
COPY pyproject.toml ./
RUN python - <<'PY'
import pathlib, tomllib

project = tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]
pathlib.Path("/tmp/requirements.txt").write_text("\n".join(project["dependencies"]))
pathlib.Path("/tmp/requirements-test.txt").write_text(
    "\n".join(project["optional-dependencies"]["test"])
)
PY
RUN pip install --no-cache-dir -r /tmp/requirements.txt


FROM base AS source

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app


FROM source AS runtime

USER app
EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Миграции накатываются до старта uvicorn: контейнер сам приводит схему к head.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]


FROM source AS test

RUN pip install --no-cache-dir -r /tmp/requirements-test.txt
COPY tests ./tests

USER app

CMD ["sh", "-c", "alembic upgrade head && exec pytest"]
