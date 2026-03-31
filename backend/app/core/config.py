"""
Configuracion central del sistema financiero FinCore.
Seguridad de grado bancario con cifrado AES-256.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
import secrets
import logging
import os

logger = logging.getLogger(__name__)


def _get_jwt_secret() -> str:
    """
    Obtiene JWT_SECRET_KEY de variables de entorno.
    En desarrollo genera una clave temporal con advertencia.
    """
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        if len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
        return secret

    # Solo permitir generación dinámica en desarrollo
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    if not debug_mode:
        raise ValueError(
            "JWT_SECRET_KEY es OBLIGATORIO en producción. "
            "Configure la variable de entorno JWT_SECRET_KEY con al menos 32 caracteres."
        )

    # Modo desarrollo: generar clave temporal
    logger.warning(
        "⚠️ JWT_SECRET_KEY no configurado. Usando clave temporal. "
        "Las sesiones se invalidarán al reiniciar. NO USAR EN PRODUCCIÓN."
    )
    return secrets.token_urlsafe(32)


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

    # JWT Configuration - DEBE configurarse en producción
    JWT_SECRET_KEY: str = ""  # Se valida en __init__
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Reducido de 480 a 30 minutos (más seguro)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    def __init__(self, **kwargs):
        # Pre-cargar JWT_SECRET_KEY si no se proporciona
        if "JWT_SECRET_KEY" not in kwargs or not kwargs["JWT_SECRET_KEY"]:
            kwargs["JWT_SECRET_KEY"] = _get_jwt_secret()
        super().__init__(**kwargs)

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

    # ==================== BLOCKCHAIN ====================
    BLOCKCHAIN_DEFAULT_NETWORK: str = "polygon"
    BLOCKCHAIN_OPERATOR_KEY: str = ""
    ENCRYPTION_MASTER_KEY: str = ""  # Para encriptar llaves privadas custodiales

    # RPC URLs - Redes de produccion
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"
    ETHEREUM_RPC_URL: str = "https://eth.llamarpc.com"
    ARBITRUM_RPC_URL: str = "https://arb1.arbitrum.io/rpc"
    BASE_RPC_URL: str = "https://mainnet.base.org"

    # RPC URLs - Testnets
    POLYGON_AMOY_RPC_URL: str = "https://rpc-amoy.polygon.technology"
    ETHEREUM_SEPOLIA_RPC_URL: str = "https://rpc.sepolia.org"

    # Block Explorer API Keys
    POLYGONSCAN_API_KEY: str = ""
    ETHERSCAN_API_KEY: str = ""
    ARBISCAN_API_KEY: str = ""
    BASESCAN_API_KEY: str = ""

    # Contract Addresses (configurar despues del deploy)
    FINCORE_INVESTMENT_CONTRACT: str = ""
    FINCORE_KYC_CONTRACT: str = ""
    FINCORE_DIVIDENDS_CONTRACT: str = ""
    FINCORE_TOKEN_FACTORY_CONTRACT: str = ""

    # USDC Token Addresses por red (direcciones oficiales)
    USDC_POLYGON: str = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC nativo Polygon
    USDC_POLYGON_BRIDGED: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e bridged
    USDC_ETHEREUM: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    USDC_ARBITRUM: str = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC nativo
    USDC_BASE: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    USDC_POLYGON_AMOY: str = "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582"  # Testnet
    USDC_SEPOLIA: str = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Testnet

    # Gas Configuration
    GAS_PRICE_MULTIPLIER: float = 1.1
    MAX_GAS_PRICE_GWEI: int = 500

    # ==================== COMPLIANCE / PLD ====================
    # Chainalysis API (analisis on-chain)
    CHAINALYSIS_API_KEY: str = ""
    CHAINALYSIS_API_URL: str = "https://api.chainalysis.com/api"
    CHAINALYSIS_KYT_URL: str = "https://api.chainalysis.com/api/kyt/v2"
    CHAINALYSIS_SANCTIONS_URL: str = "https://api.chainalysis.com/api/sanctions/v1"
    CHAINALYSIS_TIMEOUT: int = 30

    # Elliptic API (alternativa/failover)
    ELLIPTIC_API_KEY: str = ""
    ELLIPTIC_API_URL: str = "https://aml-api.elliptic.co/v2"

    # Screening Thresholds
    SCREENING_AUTO_APPROVE_MAX_SCORE: int = 30
    SCREENING_REVIEW_MIN_SCORE: int = 31
    SCREENING_AUTO_REJECT_MIN_SCORE: int = 70
    SCREENING_BLOCK_MIN_SCORE: int = 90
    SCREENING_ENHANCED_AMOUNT_USD: float = 3000.0
    SCREENING_AUTO_REPORT_AMOUNT_USD: float = 10000.0

    # Compliance Notifications
    COMPLIANCE_ALERT_EMAIL: str = ""
    COMPLIANCE_WEBHOOK_URL: str = ""

    # ==================== EMAIL (SendGrid) ====================
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@fincore.com"
    SENDGRID_FROM_NAME: str = "FinCore"
    # URL base del frontend para links en emails
    FRONTEND_URL: str = "http://localhost:3001"

    # ==================== STP (SPEI) ====================
    # Configuracion de STP para transferencias SPEI
    STP_API_URL: str = "https://demo.stpmex.com/speiws/rest"
    STP_API_URL_PROD: str = "https://prod.stpmex.com/speiws/rest"
    STP_USE_PRODUCTION: bool = False
    STP_EMPRESA: str = ""  # Codigo de empresa asignado por STP
    STP_PRIVATE_KEY_PATH: str = ""  # Ruta al archivo .pem de firma
    STP_PRIVATE_KEY_PASSWORD: str = ""  # Password de la llave privada
    STP_CLABE_CONCENTRADORA: str = ""  # CLABE de cuenta concentradora
    STP_TIMEOUT: int = 30
    STP_WEBHOOK_SECRET: str = ""  # Secret para verificar webhooks

    # ==================== BITSO (Exchange Cripto-Fiat) ====================
    # Credenciales de API (obtener en https://bitso.com/api_info)
    BITSO_API_KEY: str = ""
    BITSO_API_SECRET: str = ""
    BITSO_USE_PRODUCTION: bool = False  # False = sandbox

    # URLs de API
    BITSO_API_URL: str = "https://api.bitso.com"
    BITSO_SANDBOX_URL: str = "https://api-dev.bitso.com"

    # Configuracion de trading
    BITSO_DEFAULT_BOOK: str = "usdc_mxn"  # Libro por defecto
    BITSO_TIMEOUT: int = 30  # Timeout en segundos

    # Limites de conversion
    BITSO_MIN_USDC_CONVERSION: float = 1.0  # Minimo 1 USDC
    BITSO_MAX_USDC_CONVERSION: float = 50000.0  # Maximo 50k USDC por tx

    # Cache de tasas (segundos)
    BITSO_RATE_CACHE_TTL: int = 30

    # Webhook
    BITSO_WEBHOOK_SECRET: str = ""

    # Network Chain IDs
    POLYGON_CHAIN_ID: int = 137
    POLYGON_AMOY_CHAIN_ID: int = 80002
    ETHEREUM_CHAIN_ID: int = 1
    ETHEREUM_SEPOLIA_CHAIN_ID: int = 11155111
    ARBITRUM_CHAIN_ID: int = 42161
    BASE_CHAIN_ID: int = 8453

    # ==================== INFRASTRUCTURE ====================
    # Environment
    ENVIRONMENT: str = "development"  # development, staging, production

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text

    # AWS Secrets Manager
    AWS_SECRETS_MANAGER_ENABLED: bool = False
    SECRETS_BACKEND: str = "env"  # env, aws, vault
    SECRETS_CACHE_TTL: int = 300
    SECRETS_PREFIX: str = "fincore"

    # HashiCorp Vault (alternativa a AWS)
    VAULT_ADDR: str = ""
    VAULT_TOKEN: str = ""
    VAULT_MOUNT: str = "secret"

    # Cloudflare WAF
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ZONE_ID: str = ""
    WAF_VERIFY_CF_IP: bool = True
    WAF_REQUIRE_CF_HEADERS: bool = True
    WAF_ALLOW_PRIVATE_IPS: bool = True  # True for development
    WAF_RATE_LIMIT_REQUESTS: int = 100
    WAF_RATE_LIMIT_WINDOW: int = 60
    WAF_BLOCKED_COUNTRIES: str = ""  # Comma-separated country codes

    # PagerDuty Alerting
    PAGERDUTY_ROUTING_KEY: str = ""
    SLACK_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_URL: str = ""

    # Circuit Breaker defaults
    CB_FAILURE_THRESHOLD: int = 5
    CB_SUCCESS_THRESHOLD: int = 3
    CB_TIMEOUT_SECONDS: int = 30

    # Degraded Mode
    DEGRADED_MODE_THRESHOLD: int = 2
    EMERGENCY_MODE_THRESHOLD: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar variables extra en .env


settings = Settings()
