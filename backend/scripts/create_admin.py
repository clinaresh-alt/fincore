"""
Script para crear usuario administrador.
Ejecutar: python scripts/create_admin.py

Opciones:
  - Sin argumentos: Genera contraseña aleatoria segura
  - ADMIN_PASSWORD env var: Usa la contraseña especificada
  - ADMIN_EMAIL env var: Usa el email especificado (default: admin@fincore.com)
"""
import sys
import os
import secrets
import string

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password


def generate_secure_password(length: int = 16) -> str:
    """
    Genera una contraseña segura que cumple con requisitos de complejidad.

    Requisitos:
    - Al menos una letra mayúscula
    - Al menos una letra minúscula
    - Al menos un dígito
    - Al menos un carácter especial
    - Longitud mínima de 16 caracteres
    """
    # Asegurar que tenemos al menos uno de cada tipo
    password_chars = [
        secrets.choice(string.ascii_uppercase),  # Mayúscula
        secrets.choice(string.ascii_lowercase),  # Minúscula
        secrets.choice(string.digits),           # Dígito
        secrets.choice("!@#$%^&*()_+-=[]{}|"),   # Especial
    ]

    # Completar con caracteres aleatorios
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|"
    remaining_length = length - len(password_chars)
    password_chars.extend(secrets.choice(all_chars) for _ in range(remaining_length))

    # Mezclar aleatoriamente
    secrets.SystemRandom().shuffle(password_chars)

    return ''.join(password_chars)


def create_admin():
    """Crea el usuario administrador con contraseña segura."""

    # Obtener email del admin (configurable via env)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@fincore.com")

    # Obtener o generar contraseña
    admin_password = os.getenv("ADMIN_PASSWORD")
    password_generated = False

    if not admin_password:
        admin_password = generate_secure_password(20)
        password_generated = True
        print("⚠️  No se especificó ADMIN_PASSWORD. Generando contraseña segura...")
    else:
        # Validar fortaleza de la contraseña proporcionada
        if len(admin_password) < 12:
            print("❌ Error: La contraseña debe tener al menos 12 caracteres")
            sys.exit(1)
        if not any(c.isupper() for c in admin_password):
            print("❌ Error: La contraseña debe contener al menos una mayúscula")
            sys.exit(1)
        if not any(c.islower() for c in admin_password):
            print("❌ Error: La contraseña debe contener al menos una minúscula")
            sys.exit(1)
        if not any(c.isdigit() for c in admin_password):
            print("❌ Error: La contraseña debe contener al menos un dígito")
            sys.exit(1)

    db = SessionLocal()
    try:
        # Verificar si ya existe
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            print(f"⚠️  Usuario admin ya existe: {admin_email}")
            print("   Use el panel de administración para cambiar la contraseña.")
            return

        # Crear admin
        admin = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
            rol=UserRole.ADMIN,
            email_verified=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("")
        print("=" * 60)
        print("✅ Usuario Administrador Creado Exitosamente")
        print("=" * 60)
        print(f"   Email:    {admin_email}")
        if password_generated:
            print(f"   Password: {admin_password}")
            print("")
            print("   ⚠️  IMPORTANTE: Guarde esta contraseña en un lugar seguro.")
            print("   ⚠️  Esta contraseña NO se volverá a mostrar.")
            print("   ⚠️  Cámbiela después del primer inicio de sesión.")
        else:
            print("   Password: [especificada via ADMIN_PASSWORD]")
        print(f"   Rol:      Admin")
        print("=" * 60)
        print("")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
