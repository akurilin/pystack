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
    # Clerk handles all authentication. Every board is private — the only surface a
    # signed-out visitor can reach is the sign-in landing page. The secret key
    # verifies session tokens server-side, so it accepts Clerk's conventional
    # CLERK_SECRET_KEY name in addition to the PYSTACK_ prefix.
    clerk_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PYSTACK_CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
    )
    # Origins permitted to present session tokens, checked during verification to
    # reject tokens minted for a different frontend. Mirrors the dev frontend URL.
    clerk_authorized_parties: list[str] = ["http://localhost:5173"]
    # Sentry error monitoring. Optional: when unset (local dev, tests) the SDK is
    # never initialized, so it stays a no-op. Accepts Sentry's conventional
    # SENTRY_DSN name in addition to the PYSTACK_ prefix.
    sentry_dsn: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PYSTACK_SENTRY_DSN", "SENTRY_DSN"),
    )
    # Tags events in Sentry so production errors are distinguishable from local
    # ones. Render sets this to "production"; defaults to "development" otherwise.
    environment: str = "development"

    def validate_assistant_config(self) -> None:
        if self.openrouter_api_key:
            return
        raise RuntimeError(
            "Assistant chat requires PYSTACK_OPENROUTER_API_KEY or OPENROUTER_API_KEY."
        )

    def validate_clerk_config(self) -> None:
        if self.clerk_secret_key:
            return
        raise RuntimeError("Authentication requires PYSTACK_CLERK_SECRET_KEY or CLERK_SECRET_KEY.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
