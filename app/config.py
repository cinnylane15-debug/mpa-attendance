from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/mpa_attendance"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    # JWT
    SECRET_KEY: str = "change-this-to-a-secure-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Face Recognition
    FACE_RECOGNITION_TOLERANCE: float = 0.4
    INSIGHTFACE_MODEL: str = "buffalo_sc"

    # File Uploads
    UPLOAD_DIR: str = "uploads/photos"

    # RTSP Settings
    RTSP_FRAME_INTERVAL: float = 2.0
    RTSP_COOLDOWN_MINUTES: int = 30
    RTSP_RECONNECT_DELAY: float = 5.0

    # School Settings
    SCHOOL_START_TIME: str = "08:00"
    LATE_THRESHOLD_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
