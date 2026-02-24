"""
Configuracion de PostgreSQL con SQLAlchemy.
Optimizado para transacciones ACID y alta concurrencia.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Engine con pool de conexiones optimizado para fintech
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verifica conexiones antes de usarlas
    pool_recycle=3600,   # Recicla conexiones cada hora
    echo=settings.DEBUG
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base para modelos
Base = declarative_base()


def get_db():
    """
    Dependency para obtener sesion de base de datos.
    Se cierra automaticamente al terminar la request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
