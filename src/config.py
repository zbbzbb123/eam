"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "mysql+pymysql://root:password@localhost:3306/eam"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # External APIs (optional for MVP)
    tushare_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
