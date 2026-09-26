"""
Reads settings from the .env file so nothing is hardcoded in the source code.
Import `settings` anywhere you need a config value, e.g:

    from app.config import settings
    print(settings.database_url)
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/sih26002"
    weather_api_base_url: str = "https://api.open-meteo.com/v1/forecast"

    ner_min_lat: float = 21.5
    ner_max_lat: float = 29.5
    ner_min_lon: float = 88.0
    ner_max_lon: float = 97.5

    class Config:
        env_file = ".env"


settings = Settings()
