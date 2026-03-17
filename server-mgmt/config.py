from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    admin_username: str = "admin"
    admin_password: str = "changeme"
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    api_port: int = 8443
    ssl_cert: str = "cert.pem"
    ssl_key: str = "key.pem"
    db_path: str = "mgmt.db"
    stacks_dir: str = "stacks"
    allowed_ips: str = ""
    rate_limit: int = 100

    @property
    def stacks_path(self) -> Path:
        return Path(self.stacks_dir)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
