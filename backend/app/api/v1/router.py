"""
Router principal de la API v1.
Agrupa todos los endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, projects, investor, admin, sector_metrics, companies

api_router = APIRouter()

# Incluir routers de cada modulo
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(investor.router)
api_router.include_router(admin.router)
api_router.include_router(sector_metrics.router)
api_router.include_router(companies.router)
