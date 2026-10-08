import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # check if is prod env
    ENV: str = Field(default="development", alias="ENV")

    APP_NAME: str = Field(default="CNLTHD API", alias="APP_NAME")
    DATABASE_URL: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    SECRET_KEY: str = Field(default="your-secret-key", alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    BIRD_API_KEY: str = Field(alias="BIRD_API_KEY", default="your-bird-api-key")
    BASE_URL: str = Field(alias="BASE_URL", default="http://localhost:8000")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


config = Config()
