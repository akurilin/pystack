from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_prefix="PYSTACK_",
        extra="ignore",
    )

    app_name: str = "Pystack API"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://pystack:pystack@localhost:5432/pystack_dev"
    test_database_url: str = "postgresql://pystack:pystack@localhost:5432/pystack_test"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
