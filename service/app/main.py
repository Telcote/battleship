from fastapi import FastAPI

from app.api.routes import router
from app.errors import register_exception_handlers

app = FastAPI(title="battleship")
register_exception_handlers(app)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
