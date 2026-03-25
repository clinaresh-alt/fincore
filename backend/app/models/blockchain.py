"""
Modelos Blockchain para FinCore.
Gestiona tokens, wallets, transacciones y smart contracts.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Numeric, Text, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class BlockchainNetwork(str, enum.Enum):
    """Redes blockchain soportadas."""
    POLYGON = "polygon"
    POLYGON_MUMBAI = "polygon_mumbai"  # Testnet
    ETHEREUM = "ethereum"
    ETHEREUM_SEPOLIA = "ethereum_sepolia"  # Testnet
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"


class TokenType(str, enum.Enum):
    """Tipos de tokens."""
    INVESTMENT = "investment"  # Token de inversión (ERC-721)
    PROJECT = "project"  # Token del proyecto (ERC-20 fraccional)
    UTILITY = "utility"  # Token de utilidad
    GOVERNANCE = "governance"  # Token de gobernanza


class TransactionStatus(str, enum.Enum):
    """Estados de transacción blockchain."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REPLACED = "replaced"


class TransactionType(str, enum.Enum):
    """Tipos de transacciones blockchain."""
    TOKEN_MINT = "token_mint"
    TOKEN_TRANSFER = "token_transfer"
    TOKEN_BURN = "token_burn"
    DIVIDEND_PAYMENT = "dividend_payment"
    CONTRACT_DEPLOY = "contract_deploy"
    INVESTMENT_RECORD = "investment_record"
    KYC_VERIFICATION = "kyc_verification"
    ESCROW_LOCK = "escrow_lock"
    ESCROW_RELEASE = "escrow_release"


class UserWallet(Base):
    """
    Wallet blockchain del usuario.
    Cada usuario puede tener múltiples wallets.
    Soporta wallets custodiales (FinCore controla la llave) y externas.
    """
    __tablename__ = "user_wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)

    # Wallet info
    address = Column(String(42), nullable=False, unique=True)  # 0x + 40 chars
    wallet_type = Column(String(50), nullable=False, default="metamask")  # metamask, walletconnect, custodial
    label = Column(String(100), nullable=True)  # "Mi wallet principal"

    # Llave privada encriptada (SOLO para wallets custodiales)
    # Encriptada con Fernet (AES-128-CBC). La master key debe estar en KMS.
    encrypted_private_key = Column(Text, nullable=True)
    is_custodial = Column(Boolean, default=False)  # True si FinCore controla la llave

    # Estado
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_signature = Column(Text, nullable=True)  # Firma de verificación

    # Red preferida
    preferred_network = Column(
        SQLEnum(BlockchainNetwork, name="blockchain_network_enum", create_type=False),
        default=BlockchainNetwork.POLYGON
    )

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", back_populates="wallets")
    token_holdings = relationship("TokenHolding", back_populates="wallet", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_wallet_user", "user_id"),
        Index("idx_wallet_address", "address"),
        CheckConstraint("address ~ '^0x[a-fA-F0-9]{40}$'", name="valid_eth_address"),
    )


class SmartContract(Base):
    """
    Registro de Smart Contracts desplegados.
    """
    __tablename__ = "smart_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificación
    name = Column(String(100), nullable=False)  # "FinCoreInvestment"
    version = Column(String(20), nullable=False, default="1.0.0")
    contract_type = Column(String(50), nullable=False)  # investment, token, escrow

    # Blockchain info
    network = Column(
        SQLEnum(BlockchainNetwork, name="blockchain_network_enum", create_type=False),
        nullable=False
    )
    address = Column(String(42), nullable=False)
    deployment_tx_hash = Column(String(66), nullable=False)
    deployment_block = Column(Integer, nullable=True)

    # ABI y código
    abi = Column(JSONB, nullable=False)
    bytecode_hash = Column(String(66), nullable=True)  # Hash del bytecode para verificación

    # Estado
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # Verificado en Polygonscan/Etherscan

    # Permisos
    owner_address = Column(String(42), nullable=False)
    operator_addresses = Column(JSONB, default=list)  # Lista de operadores autorizados

    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    project_tokens = relationship("ProjectToken", back_populates="contract")

    __table_args__ = (
        Index("idx_contract_network_address", "network", "address", unique=True),
        Index("idx_contract_type", "contract_type"),
    )


class ProjectToken(Base):
    """
    Token de un proyecto (tokenización de activo).
    Representa la fraccionamiento de un proyecto en tokens.
    """
    __tablename__ = "project_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("proyectos.id", ondelete="CASCADE"), nullable=False, unique=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("smart_contracts.id"), nullable=True)

    # Token info
    token_symbol = Column(String(10), nullable=False)  # "PROJ001"
    token_name = Column(String(100), nullable=False)  # "FinCore Project 001 Token"
    token_type = Column(
        SQLEnum(TokenType, name="token_type_enum", create_type=False),
        default=TokenType.PROJECT
    )

    # Blockchain
    network = Column(
        SQLEnum(BlockchainNetwork, name="blockchain_network_enum", create_type=False),
        nullable=False,
        default=BlockchainNetwork.POLYGON
    )
    token_address = Column(String(42), nullable=True)  # Dirección del token ERC-20
    deployment_tx_hash = Column(String(66), nullable=True)

    # Tokenomics
    total_supply = Column(Numeric(28, 8), nullable=False)  # Total de tokens
    tokens_sold = Column(Numeric(28, 8), default=0)
    tokens_available = Column(Numeric(28, 8), nullable=False)
    price_per_token = Column(Numeric(18, 8), nullable=False)  # Precio en USDC/MXN
    min_purchase = Column(Numeric(18, 8), default=1)  # Mínimo de tokens por compra

    # Configuración
    decimals = Column(Integer, default=18)
    is_transferable = Column(Boolean, default=True)  # Si se puede transferir entre usuarios
    allows_fractional = Column(Boolean, default=True)  # Si permite compras fraccionadas

    # Dividendos
    dividend_frequency = Column(String(20), nullable=True)  # monthly, quarterly, yearly
    last_dividend_date = Column(DateTime(timezone=True), nullable=True)
    total_dividends_paid = Column(Numeric(18, 2), default=0)

    # Estado
    is_active = Column(Boolean, default=False)
    launched_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    project = relationship("Project", back_populates="token_info")
    contract = relationship("SmartContract", back_populates="project_tokens")
    holdings = relationship("TokenHolding", back_populates="project_token", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_project_token_symbol", "token_symbol"),
        Index("idx_project_token_address", "token_address"),
        CheckConstraint("total_supply > 0", name="positive_supply"),
        CheckConstraint("price_per_token > 0", name="positive_price"),
    )

    @property
    def percentage_sold(self) -> float:
        """Porcentaje de tokens vendidos."""
        if self.total_supply == 0:
            return 0
        return float(self.tokens_sold / self.total_supply * 100)


class TokenHolding(Base):
    """
    Holdings de tokens por wallet.
    Registro de cuántos tokens tiene cada wallet.
    """
    __tablename__ = "token_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("user_wallets.id", ondelete="CASCADE"), nullable=False)
    project_token_id = Column(UUID(as_uuid=True), ForeignKey("project_tokens.id", ondelete="CASCADE"), nullable=False)

    # Holdings
    balance = Column(Numeric(28, 8), nullable=False, default=0)
    locked_balance = Column(Numeric(28, 8), default=0)  # Tokens en escrow/vesting

    # Costo base para cálculo de P&L
    average_cost_basis = Column(Numeric(18, 8), nullable=True)  # Precio promedio de compra
    total_invested = Column(Numeric(18, 2), default=0)

    # Dividendos
    total_dividends_received = Column(Numeric(18, 2), default=0)
    last_dividend_claim = Column(DateTime(timezone=True), nullable=True)
    unclaimed_dividends = Column(Numeric(18, 2), default=0)

    # Timestamps
    first_purchase_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    wallet = relationship("UserWallet", back_populates="token_holdings")
    project_token = relationship("ProjectToken", back_populates="holdings")

    __table_args__ = (
        Index("idx_holding_wallet_token", "wallet_id", "project_token_id", unique=True),
        CheckConstraint("balance >= 0", name="non_negative_balance"),
        CheckConstraint("locked_balance >= 0", name="non_negative_locked"),
    )

    @property
    def available_balance(self) -> float:
        """Balance disponible (no bloqueado)."""
        return float(self.balance - self.locked_balance)

    @property
    def unrealized_pnl(self) -> float:
        """P&L no realizado basado en precio actual del token."""
        if not self.average_cost_basis or not self.project_token:
            return 0
        current_value = float(self.balance * self.project_token.price_per_token)
        cost = float(self.total_invested)
        return current_value - cost


class BlockchainTransaction(Base):
    """
    Registro de todas las transacciones blockchain.
    Incluye transacciones pendientes, confirmadas y fallidas.
    """
    __tablename__ = "blockchain_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Referencias internas
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    investment_id = Column(UUID(as_uuid=True), ForeignKey("inversiones.id"), nullable=True)
    project_token_id = Column(UUID(as_uuid=True), ForeignKey("project_tokens.id"), nullable=True)

    # Tipo de transacción
    tx_type = Column(
        SQLEnum(TransactionType, name="blockchain_tx_type_enum", create_type=False),
        nullable=False
    )

    # Blockchain info
    network = Column(
        SQLEnum(BlockchainNetwork, name="blockchain_network_enum", create_type=False),
        nullable=False
    )
    tx_hash = Column(String(66), nullable=True, unique=True)  # Puede ser null si está pending
    block_number = Column(Integer, nullable=True)
    block_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Direcciones
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42), nullable=True)
    contract_address = Column(String(42), nullable=True)

    # Valores
    value = Column(Numeric(28, 18), default=0)  # Valor en token nativo (ETH/MATIC)
    token_amount = Column(Numeric(28, 8), nullable=True)  # Cantidad de tokens
    token_address = Column(String(42), nullable=True)  # Token transferido

    # Gas
    gas_limit = Column(Integer, nullable=True)
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(Numeric(18, 9), nullable=True)  # En Gwei
    effective_gas_price = Column(Numeric(18, 9), nullable=True)
    max_fee_per_gas = Column(Numeric(18, 9), nullable=True)
    max_priority_fee = Column(Numeric(18, 9), nullable=True)

    # Estado
    status = Column(
        SQLEnum(TransactionStatus, name="blockchain_tx_status_enum", create_type=False),
        default=TransactionStatus.PENDING
    )
    confirmations = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Datos adicionales
    method_name = Column(String(100), nullable=True)  # "createInvestment"
    method_params = Column(JSONB, nullable=True)  # Parámetros del método
    logs = Column(JSONB, nullable=True)  # Event logs

    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", backref="blockchain_transactions")
    investment = relationship("Investment", backref="blockchain_transactions")
    project_token = relationship("ProjectToken", backref="blockchain_transactions")

    __table_args__ = (
        Index("idx_blockchain_tx_hash", "tx_hash"),
        Index("idx_blockchain_tx_user", "user_id"),
        Index("idx_blockchain_tx_status", "status"),
        Index("idx_blockchain_tx_network", "network"),
        Index("idx_blockchain_tx_type", "tx_type"),
        Index("idx_blockchain_tx_created", "created_at"),
    )

    @property
    def gas_cost_native(self) -> float:
        """Costo de gas en token nativo (ETH/MATIC)."""
        if self.gas_used and self.effective_gas_price:
            return float(self.gas_used * self.effective_gas_price) / 1e9
        return 0


class DividendDistribution(Base):
    """
    Registro de distribuciones de dividendos.
    """
    __tablename__ = "dividend_distributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_token_id = Column(UUID(as_uuid=True), ForeignKey("project_tokens.id", ondelete="CASCADE"), nullable=False)

    # Distribución
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    total_amount = Column(Numeric(18, 2), nullable=False)  # Monto total a distribuir
    amount_per_token = Column(Numeric(18, 8), nullable=False)  # Dividendo por token

    # Blockchain
    distribution_tx_hash = Column(String(66), nullable=True)
    merkle_root = Column(String(66), nullable=True)  # Para distribuciones grandes (Merkle Airdrop)

    # Estado
    is_distributed = Column(Boolean, default=False)
    distributed_at = Column(DateTime(timezone=True), nullable=True)
    claims_count = Column(Integer, default=0)
    claimed_amount = Column(Numeric(18, 2), default=0)

    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    project_token = relationship("ProjectToken", backref="dividend_distributions")

    __table_args__ = (
        Index("idx_dividend_token", "project_token_id"),
        Index("idx_dividend_period", "period_start", "period_end"),
    )


class KYCBlockchainRecord(Base):
    """
    Registro de verificaciones KYC en blockchain.
    Hash de datos KYC registrado on-chain para prueba de verificación.
    """
    __tablename__ = "kyc_blockchain_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Hash de datos KYC (sin datos personales)
    kyc_hash = Column(String(66), nullable=False)  # SHA-256 de datos KYC
    verification_level = Column(String(20), nullable=False)  # basic, standard, enhanced

    # Blockchain
    network = Column(
        SQLEnum(BlockchainNetwork, name="blockchain_network_enum", create_type=False),
        nullable=False,
        default=BlockchainNetwork.POLYGON
    )
    tx_hash = Column(String(66), nullable=True)
    block_number = Column(Integer, nullable=True)
    contract_address = Column(String(42), nullable=True)

    # Estado
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="kyc_blockchain_record")

    __table_args__ = (
        Index("idx_kyc_user", "user_id"),
        Index("idx_kyc_hash", "kyc_hash"),
    )
