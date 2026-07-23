from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
    database_url: str
    allowed_user_ids: str = ""

    @property
    def allowed_user_id_set(self) -> set[int]:
        ids = {p.strip() for p in self.allowed_user_ids.split(",") if p.strip()}
        return {int(i) for i in ids}


settings = Settings()
