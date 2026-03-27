"""
Router principal de la API v1.
Agrupa todos los endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, projects, investor, admin, sector_metrics, companies, blockchain, audit, compliance, deployments, notifications, analytics, remittances, reconciliation, stp, jobs, webhooks, dashboard

api_router = APIRouter()

# Incluir routers de cada modulo
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(investor.router)
api_router.include_router(admin.router)
api_router.include_router(sector_metrics.router)
api_router.include_router(companies.router)
api_router.include_router(blockchain.router)
api_router.include_router(audit.router, prefix="/audit", tags=["Smart Contract Audit"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance PLD/AML"])
api_router.include_router(deployments.router, prefix="/admin", tags=["Smart Contract Deployment"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics Dashboard"])
api_router.include_router(remittances.router)
api_router.include_router(reconciliation.router, prefix="/admin", tags=["Reconciliation"])
api_router.include_router(stp.router)
api_router.include_router(jobs.router, prefix="/admin", tags=["Job Queue"])
api_router.include_router(webhooks.router)
api_router.include_router(dashboard.router)
