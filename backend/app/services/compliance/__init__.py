"""
Sistema de Cumplimiento Regulatorio PLD/AML para FinCore.

Cumple con regulacion mexicana:
- LFPIORPI (Ley Federal para la Prevencion e Identificacion de Operaciones
  con Recursos de Procedencia Ilicita)
- Disposiciones de caracter general de la CNBV para activos virtuales
- Requisitos de la UIF (Unidad de Inteligencia Financiera)

Modulos:
- KYC Service: Verificacion de identidad (INE, CURP, domicilio)
- AML Service: Monitoreo de transacciones y deteccion de patrones
- Reporting Service: Generacion de reportes ROS, ROV para UIF

Uso:
    from app.services.compliance import (
        KYCService,
        AMLService,
        ReportingService,
    )

    # Verificacion KYC
    kyc = KYCService(db)
    profile = kyc.get_or_create_profile(user_id)
    kyc.verify_curp("CURP18CHARS")

    # Monitoreo AML
    aml = AMLService(db)
    alerts = aml.analyze_transaction(transaction_data)

    # Reportes UIF
    reports = ReportingService(db)
    rov = reports.generate_rov(period_start, period_end, user_id)
"""

from app.services.compliance.kyc_service import KYCService, VerificationResult
from app.services.compliance.aml_service import AMLService, TransactionData
from app.services.compliance.reporting_service import ReportingService

__all__ = [
    # Servicios
    "KYCService",
    "AMLService",
    "ReportingService",

    # Data classes
    "VerificationResult",
    "TransactionData",
]
