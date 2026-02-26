"""
Script para agregar valores de enum faltantes a PostgreSQL.
Ejecutar: python scripts/add_audit_enum_values.py
"""
import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine

def add_enum_values():
    """Agrega valores de enum faltantes a audit_action_enum."""
    enum_values_to_add = [
        'PROJECT_MODIFIED',
        'PROJECT_DELETED',
    ]

    with engine.connect() as conn:
        # Verificar valores existentes
        result = conn.execute(text("""
            SELECT unnest(enum_range(NULL::audit_action_enum))::text as value
        """))
        existing_values = {row[0] for row in result}
        print(f"Valores existentes: {existing_values}")

        # Agregar valores faltantes
        for value in enum_values_to_add:
            if value not in existing_values:
                try:
                    conn.execute(text(f"ALTER TYPE audit_action_enum ADD VALUE '{value}'"))
                    conn.commit()
                    print(f"Agregado: {value}")
                except Exception as e:
                    print(f"Error agregando {value}: {e}")
            else:
                print(f"Ya existe: {value}")

        print("Completado!")

if __name__ == "__main__":
    add_enum_values()
