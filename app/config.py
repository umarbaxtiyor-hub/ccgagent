from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
    database_url: str
    allowed_user_ids: str = ""

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Railway, Heroku, etc.) hand out
        # postgres:// / postgresql:// URLs; SQLAlchemy's async engine needs
        # the asyncpg driver explicitly in the scheme.
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    @property
    def allowed_user_id_set(self) -> set[int]:
        ids = {p.strip() for p in self.allowed_user_ids.split(",") if p.strip()}
        return {int(i) for i in ids}


settings = Settings()
