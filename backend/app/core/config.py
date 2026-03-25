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

    # Network Chain IDs
    POLYGON_CHAIN_ID: int = 137
    POLYGON_AMOY_CHAIN_ID: int = 80002
    ETHEREUM_CHAIN_ID: int = 1
    ETHEREUM_SEPOLIA_CHAIN_ID: int = 11155111
    ARBITRUM_CHAIN_ID: int = 42161
    BASE_CHAIN_ID: int = 8453

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar variables extra en .env


settings = Settings()
