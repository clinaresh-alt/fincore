"""
Script para crear las tablas faltantes en la base de datos.
Usa SQLAlchemy para crear las tablas definidas en los modelos.
"""
import sys
sys.path.insert(0, '/Users/ciro/Dev/fincore/backend')

from app.core.database import engine, Base
from app.models.project import SectorIndicators

def create_sector_indicators_table():
    """Crea la tabla indicadores_sector si no existe."""
    print("Creando tabla indicadores_sector...")

    # Crear solo la tabla SectorIndicators
    SectorIndicators.__table__.create(engine, checkfirst=True)

    print("Tabla indicadores_sector creada exitosamente.")

if __name__ == "__main__":
    create_sector_indicators_table()
