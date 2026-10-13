from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.errors import register_exception_handlers

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="battleship-arena")
register_exception_handlers(app)
app.include_router(router)

app.mount("/ui", StaticFiles(directory=STATIC / "ui", html=True), name="ui")

app.mount("/admin", StaticFiles(directory=STATIC / "admin", html=True), name="admin")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse("/ui/")
