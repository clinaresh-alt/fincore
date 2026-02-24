"""
Modelos SQLAlchemy para FinCore.
Esquema optimizado para sistema financiero de alto nivel.
"""
from app.models.user import User, UserProfile
from app.models.project import Project, FinancialEvaluation, RiskAnalysis, CashFlow
from app.models.investment import Investment, InvestmentTransaction
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.feasibility import (
    FeasibilityStudy, AlertConfig, Alert, SensitivityAnalysis
)

__all__ = [
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
    "FeasibilityStudy",
    "AlertConfig",
    "Alert",
    "SensitivityAnalysis"
]
