"""
Configuracion central del sistema financiero FinCore.
Seguridad de grado bancario con cifrado AES-256.
"""
from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "FinCore - Sistema Financiero"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5433
    DB_NAME: str = "finance_system"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis (Sessions & MFA)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # JWT Configuration
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas de trabajo
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MFA Configuration
    MFA_ISSUER_NAME: str = "FinCore"
    MFA_VALIDITY_SECONDS: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # Encryption (AES-256)
    ENCRYPTION_KEY: str = secrets.token_urlsafe(32)

    # AWS S3 (Document Vault)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "fincore-vault"

    # Tax API Integration
    TAX_API_URL: str = ""
    TAX_API_KEY: str = ""

    # AI Analysis (Claude API)
    ANTHROPIC_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Audit Trail
    ENABLE_AUDIT_LOG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
