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

    # Auto-learn: automatically save high-confidence detections as new photos
    AUTO_LEARN_ENABLED: bool = True
    AUTO_LEARN_MIN_CONFIDENCE: float = 0.55  # Only auto-learn above this threshold
    AUTO_LEARN_MAX_PHOTOS: int = 20  # Max photos per student
    AUTO_LEARN_COOLDOWN_HOURS: int = 24  # Only auto-learn once per student per day

    # School Settings
    SCHOOL_START_TIME: str = "08:00"
    LATE_THRESHOLD_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
