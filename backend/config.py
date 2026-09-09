from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    google_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    rapidapi_key: str
    firecrawl_api_key: str
    data_dir: str = "./data/sessions"


def get_settings() -> Settings:
    return Settings()
