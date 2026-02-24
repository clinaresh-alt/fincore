"""
Script para crear proyectos de ejemplo.
Ejecutar: python scripts/seed_projects.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.project import Project, ProjectStatus, ProjectSector


def seed_projects():
    db = SessionLocal()
    try:
        # Verificar si ya hay proyectos
        count = db.query(Project).count()
        if count > 0:
            print(f"Ya existen {count} proyectos en la base de datos")
            return

        projects = [
            Project(
                nombre="Plaza Comercial Reforma",
                descripcion="Desarrollo de centro comercial premium de 45,000 m2 en Av. Paseo de la Reforma. Incluye 120 locales comerciales, 3 anclas departamentales, food court y cine multiplex.",
                sector=ProjectSector.INMOBILIARIO,
                monto_solicitado=Decimal("15000000"),
                monto_financiado=Decimal("9000000"),
                monto_minimo_inversion=Decimal("50000"),
                plazo_meses=36,
                estado=ProjectStatus.FINANCIANDO,
                tasa_rendimiento_anual=Decimal("0.18"),
                empresa_solicitante="Grupo Inmobiliario Reforma S.A.",
                tiene_documentacion_completa=True,
            ),
            Project(
                nombre="Fintech Pagos Digitales",
                descripcion="Plataforma de pagos instantaneos para comercios PYME. Integracion con bancos, terminales punto de venta y apps moviles.",
                sector=ProjectSector.FINTECH,
                monto_solicitado=Decimal("5000000"),
                monto_financiado=Decimal("3500000"),
                monto_minimo_inversion=Decimal("25000"),
                plazo_meses=24,
                estado=ProjectStatus.FINANCIANDO,
                tasa_rendimiento_anual=Decimal("0.22"),
                empresa_solicitante="PayFlow Technologies",
                tiene_documentacion_completa=True,
            ),
            Project(
                nombre="Parque Solar Sonora",
                descripcion="Instalacion de 50MW de energia solar fotovoltaica en el desierto de Sonora. Contrato PPA a 20 anos con CFE.",
                sector=ProjectSector.ENERGIA,
                monto_solicitado=Decimal("25000000"),
                monto_financiado=Decimal("25000000"),
                monto_minimo_inversion=Decimal("100000"),
                plazo_meses=60,
                estado=ProjectStatus.FINANCIADO,
                tasa_rendimiento_anual=Decimal("0.14"),
                empresa_solicitante="Solar Norte S.A. de C.V.",
                tiene_documentacion_completa=True,
            ),
            Project(
                nombre="Agrotech Vertical Farms",
                descripcion="Red de granjas verticales con tecnologia hidroponica para produccion de hortalizas premium en zonas urbanas.",
                sector=ProjectSector.AGROTECH,
                monto_solicitado=Decimal("8000000"),
                monto_financiado=Decimal("2400000"),
                monto_minimo_inversion=Decimal("30000"),
                plazo_meses=30,
                estado=ProjectStatus.FINANCIANDO,
                tasa_rendimiento_anual=Decimal("0.16"),
                empresa_solicitante="AgriVertical MX",
                tiene_documentacion_completa=True,
            ),
            Project(
                nombre="Torre Corporativa Santa Fe",
                descripcion="Edificio de oficinas clase A+ de 35 pisos en Santa Fe. Certificacion LEED Platinum, amenidades premium.",
                sector=ProjectSector.INMOBILIARIO,
                monto_solicitado=Decimal("45000000"),
                monto_financiado=Decimal("0"),
                monto_minimo_inversion=Decimal("100000"),
                plazo_meses=48,
                estado=ProjectStatus.EN_EVALUACION,
                tasa_rendimiento_anual=Decimal("0.15"),
                empresa_solicitante="Desarrollos Corporativos SF",
                tiene_documentacion_completa=False,
            ),
            Project(
                nombre="Plataforma SaaS Logistica",
                descripcion="Software de gestion logistica para flotas de transporte. Rastreo GPS, optimizacion de rutas, facturacion automatica.",
                sector=ProjectSector.TECNOLOGIA,
                monto_solicitado=Decimal("3000000"),
                monto_financiado=Decimal("3000000"),
                monto_minimo_inversion=Decimal("15000"),
                plazo_meses=18,
                estado=ProjectStatus.EN_EJECUCION,
                tasa_rendimiento_anual=Decimal("0.25"),
                empresa_solicitante="LogiTech Solutions",
                tiene_documentacion_completa=True,
            ),
        ]

        for project in projects:
            db.add(project)

        db.commit()
        print("=" * 50)
        print(f"Creados {len(projects)} proyectos de ejemplo")
        print("=" * 50)
        for p in projects:
            print(f"  - {p.nombre} ({p.sector.value}) - {p.estado.value}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_projects()
