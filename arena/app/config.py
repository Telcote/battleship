from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    player_timeout: float = 1.0

    match_history_limit: int = 100

    tournament_parallel: int = 4


settings = Settings()
