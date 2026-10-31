import os
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    # Dùng exclude=True để ẩn khỏi model_dump, repr=False để ẩn khỏi print()
    POSTGRES_USER: str = Field(
        default="postgres", alias="POSTGRES_USER", exclude=True, repr=False
    )
    POSTGRES_PASSWORD: str = Field(
        default="postgres", alias="POSTGRES_PASSWORD", exclude=True, repr=False
    )
    POSTGRES_DB: str = "cnlthd"
    POSTGRES_HOST: str = Field(
        default="db", alias="POSTGRES_HOST", exclude=True, repr=False
    )
    POSTGRES_PORT: str = Field(
        default="5432", alias="POSTGRES_PORT", exclude=True, repr=False
    )

    # Đổi tên alias hoặc biến gốc để tránh trùng với tên computed_field
    DEFAULT_DATABASE_URL: str = Field(
        default="sqlite:///./app.db", alias="DATABASE_URL", exclude=True, repr=False
    )

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


class RedisConfig(BaseSettings):
    DEFAULT_REDIS_URL: str = Field(
        default="redis://localhost:6379/0", alias="REDIS_URL", exclude=True, repr=False
    )

    REDIS_HOST: str = Field(
        default="redis", alias="REDIS_HOST", exclude=True, repr=False
    )
    REDIS_PORT: str = Field(
        default="6379", alias="REDIS_PORT", exclude=True, repr=False
    )
    REDIS_DB: str = Field(default="0", alias="REDIS_DB", exclude=True, repr=False)

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        # return self.DEFAULT_REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class Config(DatabaseConfig, RedisConfig):
    ENV: str = Field(default="development", alias="ENV")
    APP_NAME: str = Field(default="CNLTHD API", alias="APP_NAME")
    SECRET_KEY: str = Field(default="your-secret-key", alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    BIRD_API_KEY: str = Field(default="your-bird-api-key", alias="BIRD_API_KEY")
    BASE_URL: str = Field(default="http://localhost:8000", alias="BASE_URL")

    # Cấu hình chung cho toàn bộ app, tự động tìm file .env tại thư mục gốc chạy code
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Bỏ qua các biến thừa trong file .env nếu có
    )


configEnv = Config()

if __name__ == "__main__":
    # Test kết quả
    print("DATABASE:", configEnv.DATABASE_URL)
    print("REDIS:", configEnv.REDIS_URL)
    print(
        "DUMP:", configEnv.model_dump()
    )  # Sẽ chỉ xuất hiện các field chính và các @computed_field

print("DUMP:", configEnv.model_dump())
