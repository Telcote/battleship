from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    player_timeout: float = 1.0

    match_history_limit: int = 100

    tournament_parallel: int = 4

    # Где искать игроков в Docker-сети арены (см. services/discovery.py) и как часто.
    discovery_ports: str = "80,8000-8010,8080,8200"
    discovery_interval: float = 30.0


settings = Settings()
