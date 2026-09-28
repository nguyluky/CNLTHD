import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# APP_NAME = os.getenv("APP_NAME", "CNLTHD API")
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
# SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
# ALGORITHM = os.getenv("ALGORITHM", "HS256")
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")



class Config(BaseSettings):
    APP_NAME: str = Field(default="CNLTHD API", alias="APP_NAME")
    DATABASE_URL: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    SECRET_KEY: str = Field(default="your-secret-key", alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    BIRD_API_KEY: str = Field(alias="BIRD_API_KEY", default="your-bird-api-key")
    BASE_URL: str = Field(alias="BASE_URL", default="http://localhost:8000")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Config()
