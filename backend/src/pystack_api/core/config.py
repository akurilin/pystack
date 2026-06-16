from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Resolve .env whether the process runs from the repo root or backend/.
        env_file=("../.env", ".env"),
        env_prefix="PYSTACK_",
        extra="ignore",
    )

    app_name: str = "Pystack API"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://pystack:pystack@localhost:5432/pystack_dev"
    test_database_url: str = "postgresql://pystack:pystack@localhost:5432/pystack_test"
    cors_origins: list[str] = ["http://localhost:5173"]
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PYSTACK_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    )
    assistant_model: str = Field(
        default="openai/gpt-oss-20b:free",
        validation_alias=AliasChoices("PYSTACK_ASSISTANT_MODEL", "OPENROUTER_MODEL"),
    )

    def validate_assistant_config(self) -> None:
        if self.openrouter_api_key:
            return
        raise RuntimeError(
            "Assistant chat requires PYSTACK_OPENROUTER_API_KEY or OPENROUTER_API_KEY."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
