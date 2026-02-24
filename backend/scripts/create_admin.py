"""
Script para crear usuario administrador.
Ejecutar: python scripts/create_admin.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password


def create_admin():
    db = SessionLocal()
    try:
        # Verificar si ya existe
        existing = db.query(User).filter(User.email == "admin@fincore.com").first()
        if existing:
            print("Usuario admin ya existe")
            print(f"Email: admin@fincore.com")
            return

        # Crear admin
        admin = User(
            email="admin@fincore.com",
            password_hash=hash_password("AdminPass123"),
            rol=UserRole.ADMIN,
            email_verified=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("=" * 50)
        print("Usuario Administrador Creado")
        print("=" * 50)
        print(f"Email:    admin@fincore.com")
        print(f"Password: AdminPass123")
        print(f"Rol:      Admin")
        print("=" * 50)

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
