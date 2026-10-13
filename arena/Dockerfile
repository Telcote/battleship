FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 app

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

COPY app ./app
COPY rogue ./rogue


FROM source AS runtime

USER app
EXPOSE 8100

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]


FROM source AS test

RUN pip install --no-cache-dir -r /tmp/requirements-test.txt
COPY tests ./tests

USER app

CMD ["pytest"]
