"""
Modelos SQLAlchemy para FinCore.
Esquema optimizado para sistema financiero de alto nivel.
Arquitectura Bunker - Grado Militar.
"""
from app.models.user import User, UserProfile
from app.models.project import Project, FinancialEvaluation, RiskAnalysis, CashFlow
from app.models.investment import Investment, InvestmentTransaction
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.feasibility import (
    FeasibilityStudy, AlertConfig, Alert, SensitivityAnalysis
)
from app.models.ledger import ImmutableLedger, LedgerSnapshot, LedgerEntryType
from app.models.system_config import SystemConfig, ConfigCategory
from app.models.sector_metrics import SectorMetrics, SECTOR_INPUT_FIELDS, SECTOR_CALCULATED_INDICATORS
from app.models.company import Company, CompanyDocument, CompanyType, CompanyStatus, CompanyDocumentType
from app.models.blockchain import (
    BlockchainNetwork, TokenType, TransactionStatus, TransactionType,
    UserWallet, SmartContract, ProjectToken, TokenHolding,
    BlockchainTransaction, DividendDistribution, KYCBlockchainRecord
)
from app.models.compliance import (
    KYCLevel, KYCStatus, DocumentType, DocumentStatus,
    AlertType, AlertSeverity, AlertStatus, ReportType, RiskLevel,
    KYCProfile, KYCDocument, AMLAlert, AMLRule,
    RegulatoryReport, TransactionMonitor, SanctionsList, AssetValuation
)
from app.models.notification import (
    Notification, NotificationPreference, NotificationType, NotificationPriority
)
from app.models.remittance import (
    Remittance, RemittanceBlockchainTx, ReconciliationLog, RemittanceLimit,
    ExchangeRateHistory, RemittanceStatus, BlockchainRemittanceStatus,
    PaymentMethod, DisbursementMethod, Currency, Stablecoin
)
from app.models.bank_account import (
    BankAccount, BankTransaction, BankStatementImport, VirtualClabeAssignment,
    BankProvider, BankAccountType, BankAccountStatus, BankTransactionType,
    BankTransactionStatus, SpeiOperationType
)
from app.models.security import (
    WithdrawalWhitelist, UserDevice, UserSession, PasswordHistory,
    AccountFreeze, AntiPhishingPhrase, MFABackupCode,
    WithdrawalAddressType, WhitelistStatus, DeviceStatus, AccountFreezeReason
)
from app.models.marketplace import (
    TokenListing, TokenOrder, TokenTrade, MarketPrice, UserTradingStats,
    OrderSide, OrderType, OrderStatus, ListingStatus
)
from app.models.api_keys import (
    APIKey, APIKeyLog, APIRateLimit,
    APIKeyStatus, APIKeyPermission
)
from app.models.support import (
    SupportTicket, TicketMessage, StatusComponent, StatusIncident, StatusUpdate,
    TicketCategory, TicketPriority, TicketStatus, SystemStatus
)
from app.models.fincore_pay import (
    P2PTransfer, PaymentRequest, QRPayment, QRTransaction, ContactPayment,
    P2PTransferStatus, PaymentRequestStatus, QRPaymentType
)
from app.models.fincore_earn import (
    EarnProduct, EarnPosition, EarnTransaction, YieldDistribution, EarnPromotion,
    EarnProductType, EarnProductStatus, EarnPositionStatus, YieldDistributionStatus,
    EarnTransactionType
)
from app.models.debit_card import (
    DebitCard, CardTransaction, CardLimit, CardDispute, CardReward,
    CardStatus, CardType, CardNetwork, CardTransactionStatus, CardTransactionType
)
from app.models.lending import (
    LoanProduct, Loan, LoanCollateral, LoanPayment, LiquidationEvent, LoanOffer,
    LoanStatus, CollateralType, CollateralStatus, PaymentType
)

__all__ = [
    # Core
    "User",
    "UserProfile",
    "Project",
    "FinancialEvaluation",
    "RiskAnalysis",
    "CashFlow",
    "Investment",
    "InvestmentTransaction",
    "Document",
    "AuditLog",
    # Companies
    "Company",
    "CompanyDocument",
    "CompanyType",
    "CompanyStatus",
    "CompanyDocumentType",
    # Feasibility
    "FeasibilityStudy",
    "AlertConfig",
    "Alert",
    "SensitivityAnalysis",
    # Bunker Security
    "ImmutableLedger",
    "LedgerSnapshot",
    "LedgerEntryType",
    # System Config
    "SystemConfig",
    "ConfigCategory",
    # Sector Metrics
    "SectorMetrics",
    "SECTOR_INPUT_FIELDS",
    "SECTOR_CALCULATED_INDICATORS",
    # Blockchain
    "BlockchainNetwork",
    "TokenType",
    "TransactionStatus",
    "TransactionType",
    "UserWallet",
    "SmartContract",
    "ProjectToken",
    "TokenHolding",
    "BlockchainTransaction",
    "DividendDistribution",
    "KYCBlockchainRecord",
    # Notifications
    "Notification",
    "NotificationPreference",
    "NotificationType",
    "NotificationPriority",
    # Remittances
    "Remittance",
    "RemittanceBlockchainTx",
    "ReconciliationLog",
    "RemittanceLimit",
    "ExchangeRateHistory",
    "RemittanceStatus",
    "BlockchainRemittanceStatus",
    "PaymentMethod",
    "DisbursementMethod",
    "Currency",
    "Stablecoin",
    # Bank Accounts
    "BankAccount",
    "BankTransaction",
    "BankStatementImport",
    "VirtualClabeAssignment",
    "BankProvider",
    "BankAccountType",
    "BankAccountStatus",
    "BankTransactionType",
    "BankTransactionStatus",
    "SpeiOperationType",
    # Security
    "WithdrawalWhitelist",
    "UserDevice",
    "UserSession",
    "PasswordHistory",
    "AccountFreeze",
    "AntiPhishingPhrase",
    "MFABackupCode",
    "WithdrawalAddressType",
    "WhitelistStatus",
    "DeviceStatus",
    "AccountFreezeReason",
    # Marketplace
    "TokenListing",
    "TokenOrder",
    "TokenTrade",
    "MarketPrice",
    "UserTradingStats",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "ListingStatus",
    # API Keys
    "APIKey",
    "APIKeyLog",
    "APIRateLimit",
    "APIKeyStatus",
    "APIKeyPermission",
    # Support
    "SupportTicket",
    "TicketMessage",
    "StatusComponent",
    "StatusIncident",
    "StatusUpdate",
    "TicketCategory",
    "TicketPriority",
    "TicketStatus",
    "SystemStatus",
    # Fincore Pay
    "P2PTransfer",
    "PaymentRequest",
    "QRPayment",
    "QRTransaction",
    "ContactPayment",
    "P2PTransferStatus",
    "PaymentRequestStatus",
    "QRPaymentType",
    # Fincore Earn
    "EarnProduct",
    "EarnPosition",
    "EarnTransaction",
    "YieldDistribution",
    "EarnPromotion",
    "EarnProductType",
    "EarnProductStatus",
    "EarnPositionStatus",
    "YieldDistributionStatus",
    "EarnTransactionType",
    # Debit Card
    "DebitCard",
    "CardTransaction",
    "CardLimit",
    "CardDispute",
    "CardReward",
    "CardStatus",
    "CardType",
    "CardNetwork",
    "CardTransactionStatus",
    "CardTransactionType",
    # Lending
    "LoanProduct",
    "Loan",
    "LoanCollateral",
    "LoanPayment",
    "LiquidationEvent",
    "LoanOffer",
    "LoanStatus",
    "CollateralType",
    "CollateralStatus",
    "PaymentType",
]
