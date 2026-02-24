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
    # Feasibility
    "FeasibilityStudy",
    "AlertConfig",
    "Alert",
    "SensitivityAnalysis",
    # Bunker Security
    "ImmutableLedger",
    "LedgerSnapshot",
    "LedgerEntryType",
]
