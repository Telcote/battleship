from fastapi import FastAPI

app = FastAPI(title="battleship")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
