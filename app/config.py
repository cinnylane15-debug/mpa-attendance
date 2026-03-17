from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://mpa_admin:MpaSecure2026x@localhost:5432/mpa_attendance"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "MpaRedis2026x"

    # JWT
    SECRET_KEY: str = "change-me-to-a-secure-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Face recognition
    FACE_RECOGNITION_TOLERANCE: float = 0.6

    # File uploads
    UPLOAD_DIR: str = "/opt/mpa-app/uploads"

    # App
    APP_NAME: str = "MPA Face Recognition Attendance System"
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
