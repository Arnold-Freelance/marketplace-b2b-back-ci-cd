from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = Field(default="MarketPlace B2B")
    # Base de données — obligatoire, à définir dans .env
    DATABASE_URL: str = Field(...)
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Sécurité JWT — obligatoire, à définir dans .env
    SECRET_KEY: str = Field(...)
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # CORS — liste d'origines séparées par des virgules, ou "*" pour tout autoriser
    CORS_ORIGINS: str = Field(default="*")
    ENVIRONMENT: str = Field(default="development")

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5

    # Pagination
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100

    # Email (optionnel — désactivé si non fourni)
    SMTP_HOST: Optional[str] = Field(default="smtp.gmail.com")
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    EMAIL_FROM: Optional[str] = Field(default=None)

    # Frontend URL (pour liens dans emails)
    FRONTEND_URL: str = "http://localhost:3000"
    MOBILE_DEEP_LINK_SCHEME: str = "marketplace"

    # Stockage des fichiers : "local" (disque, dev) ou "supabase" (Supabase Storage, prod)
    STORAGE_BACKEND: str = Field(default="local")
    SUPABASE_URL: Optional[str] = Field(default=None)
    SUPABASE_SERVICE_KEY: Optional[str] = Field(default=None)
    SUPABASE_BUCKET: str = Field(default="uploads")

    # Uploads
    UPLOAD_DIR: str = "uploads"
    MAX_IMAGE_SIZE_MB: int = 5
    MAX_DOCUMENT_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ALLOWED_DOCUMENT_EXTENSIONS: list = [".pdf", ".doc", ".docx", ".xls", ".xlsx"]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS ('*' ou liste séparée par des virgules) en liste."""
        raw = self.CORS_ORIGINS.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    class Config:
        env_file = ".env"

settings = Settings()