from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/battleship"
    arena_url: str = "http://arena:8080"
    arena_timeout_seconds: float = 1.0


settings = Settings()
