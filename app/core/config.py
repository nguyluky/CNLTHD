import os

APP_NAME = os.getenv("APP_NAME", "CNLTHD API")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
