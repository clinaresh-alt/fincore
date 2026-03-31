"""
Schemas Pydantic para blockchain.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class BlockchainNetworkEnum(str, Enum):
    """Redes blockchain soportadas."""
    POLYGON = "polygon"
    POLYGON_MUMBAI = "polygon_mumbai"
    ETHEREUM = "ethereum"
    ETHEREUM_SEPOLIA = "ethereum_sepolia"
    ARBITRUM = "arbitrum"
    BASE = "base"


class TokenTypeEnum(str, Enum):
    """Tipos de tokens."""
    INVESTMENT = "investment"
    PROJECT = "project"
    UTILITY = "utility"
    GOVERNANCE = "governance"


class TransactionStatusEnum(str, Enum):
    """Estados de transaccion."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REPLACED = "replaced"


# ==================== WALLET SCHEMAS ====================

class WalletCreate(BaseModel):
    """Crear wallet (externa - usuario proporciona address)."""
    address: str = Field(..., min_length=42, max_length=42, pattern=r'^0x[a-fA-F0-9]{40}$')
    wallet_type: str = Field(default="metamask")
    label: Optional[str] = None
    preferred_network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON


class CustodialWalletCreate(BaseModel):
    """Crear wallet custodial (FinCore genera y controla la llave)."""
    label: Optional[str] = Field(default=None, max_length=100)
    preferred_network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON


class WalletVerify(BaseModel):
    """Verificar ownership de wallet."""
    address: str
    message: str
    signature: str


class WalletResponse(BaseModel):
    """Respuesta de wallet."""
    id: UUID
    user_id: UUID
    address: str
    wallet_type: str
    label: Optional[str]
    is_primary: bool
    is_verified: bool
    is_custodial: bool = False
    verified_at: Optional[datetime]
    preferred_network: str
    created_at: datetime

    class Config:
        from_attributes = True


class WalletBalanceResponse(BaseModel):
    """Balance de wallet."""
    address: str
    native_balance: Decimal
    network: str
    tokens: List[dict] = []


# ==================== TOKEN SCHEMAS ====================

class TokenCreate(BaseModel):
    """Crear token para proyecto."""
    project_id: UUID
    token_name: str = Field(..., min_length=3, max_length=100)
    token_symbol: str = Field(..., min_length=2, max_length=10)
    total_supply: Decimal = Field(..., gt=0)
    price_per_token: Decimal = Field(..., gt=0)
    min_purchase: Decimal = Field(default=Decimal("1"))
    decimals: int = Field(default=18, ge=0, le=18)
    is_transferable: bool = True
    allows_fractional: bool = True
    dividend_frequency: Optional[str] = None
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON

    @field_validator('token_symbol')
    @classmethod
    def uppercase_symbol(cls, v):
        return v.upper()


class TokenResponse(BaseModel):
    """Respuesta de token."""
    id: UUID
    project_id: UUID
    token_symbol: str
    token_name: str
    token_type: str
    network: str
    token_address: Optional[str]
    total_supply: Decimal
    tokens_sold: Decimal
    tokens_available: Decimal
    price_per_token: Decimal
    min_purchase: Decimal
    decimals: int
    is_transferable: bool
    allows_fractional: bool
    dividend_frequency: Optional[str]
    is_active: bool
    launched_at: Optional[datetime]
    total_dividends_paid: Decimal
    last_dividend_date: Optional[datetime]
    percentage_sold: float
    created_at: datetime

    class Config:
        from_attributes = True


class TokenStatsResponse(BaseModel):
    """Estadisticas de token."""
    token_id: UUID
    token_symbol: str
    token_name: str
    network: str
    total_supply: float
    tokens_sold: float
    tokens_available: float
    price_per_token: float
    market_cap: float
    holders_count: int
    percentage_sold: float
    is_active: bool
    launched_at: Optional[str]
    total_dividends_paid: float
    last_dividend_date: Optional[str]


# ==================== TOKEN PURCHASE SCHEMAS ====================

class TokenPurchase(BaseModel):
    """Comprar tokens."""
    token_id: UUID
    wallet_id: UUID
    amount: Decimal = Field(..., gt=0)
    record_on_chain: bool = False


class TokenTransfer(BaseModel):
    """Transferir tokens."""
    token_id: UUID
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount: Decimal = Field(..., gt=0)


class TokenPurchaseResponse(BaseModel):
    """Respuesta de compra de tokens."""
    success: bool
    holding_id: Optional[UUID]
    tokens_purchased: Decimal
    total_cost: Decimal
    tx_hash: Optional[str]
    error: Optional[str]


# ==================== HOLDING SCHEMAS ====================

class TokenHoldingResponse(BaseModel):
    """Respuesta de holding de tokens."""
    wallet_id: UUID
    wallet_address: Optional[str]
    user_id: Optional[UUID]
    balance: float
    locked_balance: float
    available_balance: float
    total_invested: float
    average_cost: float
    unclaimed_dividends: float
    total_dividends: float


class PortfolioTokenResponse(BaseModel):
    """Token en portfolio."""
    token_id: UUID
    token_symbol: str
    token_name: str
    project_id: UUID
    balance: float
    available_balance: float
    average_cost: float
    current_price: float
    total_invested: float
    current_value: float
    unrealized_pnl: float
    unclaimed_dividends: float
    total_dividends: float


# ==================== DIVIDEND SCHEMAS ====================

class DividendCreate(BaseModel):
    """Crear distribucion de dividendos."""
    project_token_id: UUID
    total_amount: Decimal = Field(..., gt=0)
    period_start: datetime
    period_end: datetime
    description: str
    record_on_chain: bool = False


class DividendDistributionResponse(BaseModel):
    """Respuesta de distribucion."""
    id: UUID
    project_token_id: UUID
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    amount_per_token: Decimal
    is_distributed: bool
    distributed_at: Optional[datetime]
    merkle_root: Optional[str]
    claims_count: int
    claimed_amount: Decimal
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DividendCalculation(BaseModel):
    """Calculo de dividendos por holder."""
    wallet_id: UUID
    wallet_address: Optional[str]
    user_id: Optional[UUID]
    token_balance: float
    dividend_amount: float
    percentage: float


class ClaimDividendsRequest(BaseModel):
    """Reclamar dividendos."""
    wallet_id: UUID
    token_id: UUID


# ==================== TRANSACTION SCHEMAS ====================

class BlockchainTransactionResponse(BaseModel):
    """Respuesta de transaccion blockchain."""
    id: UUID
    tx_type: str
    network: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    from_address: str
    to_address: Optional[str]
    value: Decimal
    token_amount: Optional[Decimal]
    token_address: Optional[str]
    status: str
    confirmations: int
    gas_used: Optional[int]
    gas_price: Optional[Decimal]
    error_message: Optional[str]
    method_name: Optional[str]
    description: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== KYC SCHEMAS ====================

class KYCBlockchainCreate(BaseModel):
    """Registrar KYC en blockchain."""
    user_id: UUID
    document_type: str
    verification_level: str = Field(..., pattern=r'^(basic|standard|enhanced)$')
    record_on_chain: bool = True


class KYCBlockchainResponse(BaseModel):
    """Respuesta de KYC blockchain."""
    id: UUID
    user_id: UUID
    kyc_hash: str
    verification_level: str
    network: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    is_verified: bool
    verified_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== NETWORK SCHEMAS ====================

class NetworkInfoResponse(BaseModel):
    """Informacion de red blockchain."""
    network: str
    name: str
    chain_id: int
    currency_symbol: str
    block_explorer: str
    is_testnet: bool
    is_connected: bool
    current_block: Optional[int]


class GasEstimateResponse(BaseModel):
    """Estimacion de gas."""
    gas_limit: int
    gas_price_gwei: Decimal
    max_fee_gwei: Decimal
    priority_fee_gwei: Decimal
    estimated_cost_native: Decimal
    estimated_cost_usd: Decimal


# ==================== WITHDRAWAL SCHEMAS ====================

class WithdrawalRequest(BaseModel):
    """Solicitud de retiro de crypto."""
    wallet_id: UUID  # Wallet origen (custodial del usuario)
    to_address: str = Field(..., min_length=42, max_length=42, pattern=r'^0x[a-fA-F0-9]{40}$')
    amount: Decimal = Field(..., gt=0)
    token_address: Optional[str] = Field(
        default=None,
        description="Dirección del token ERC-20. None para token nativo (MATIC/ETH)"
    )
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON
    mfa_code: Optional[str] = Field(
        default=None,
        description="Código MFA requerido para retiros > $100 USD"
    )

    @field_validator('to_address')
    @classmethod
    def lowercase_address(cls, v):
        return v.lower()


class WithdrawalResponse(BaseModel):
    """Respuesta de solicitud de retiro."""
    success: bool
    transaction_id: Optional[UUID] = None
    tx_hash: Optional[str] = None
    status: str  # pending, submitted, confirmed, failed
    amount: Decimal
    fee: Decimal
    net_amount: Decimal  # amount - fee
    to_address: str
    estimated_confirmation_time: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class WithdrawalFeeEstimate(BaseModel):
    """Estimación de fees para retiro."""
    network_fee: Decimal  # Gas fee
    platform_fee: Decimal  # Fee de FinCore
    total_fee: Decimal
    net_amount: Decimal  # Monto que recibirá el usuario
    fee_currency: str  # MATIC, ETH, etc.
    estimated_usd: Decimal


# ==================== DEPOSIT SCHEMAS ====================

class DepositAddressResponse(BaseModel):
    """Dirección de depósito del usuario."""
    address: str
    network: str
    currency_symbol: str  # MATIC, ETH, USDC, etc.
    qr_code_base64: Optional[str] = None
    minimum_deposit: Decimal
    confirmations_required: int
    warning: Optional[str] = None  # "Solo envía [TOKEN] en la red [NETWORK]"


class DepositHistoryItem(BaseModel):
    """Item del historial de depósitos."""
    id: UUID
    tx_hash: str
    amount: Decimal
    token_symbol: str
    token_address: Optional[str]
    network: str
    status: str
    confirmations: int
    confirmations_required: int
    from_address: str
    created_at: datetime
    confirmed_at: Optional[datetime]


class DepositHistoryResponse(BaseModel):
    """Historial de depósitos."""
    deposits: List[DepositHistoryItem]
    total: int
    pending_count: int
    total_deposited_usd: Decimal


# ==================== CONSOLIDATED BALANCE SCHEMAS ====================

class TokenBalance(BaseModel):
    """Balance de un token específico."""
    symbol: str
    name: str
    contract_address: Optional[str]
    balance: Decimal
    balance_usd: Decimal
    price_usd: Decimal
    change_24h: Optional[Decimal] = None
    logo_url: Optional[str] = None


class WalletConsolidatedBalance(BaseModel):
    """Balance consolidado de una wallet."""
    wallet_id: UUID
    wallet_address: str
    wallet_label: Optional[str]
    is_custodial: bool
    network: str
    native_balance: Decimal
    native_balance_usd: Decimal
    tokens: List[TokenBalance]
    total_balance_usd: Decimal


class ConsolidatedBalanceResponse(BaseModel):
    """Respuesta de balances consolidados del usuario."""
    total_balance_usd: Decimal
    change_24h_usd: Optional[Decimal] = None
    change_24h_percent: Optional[Decimal] = None
    wallets: List[WalletConsolidatedBalance]
    top_assets: List[TokenBalance]  # Top 5 por valor
    last_updated: datetime
