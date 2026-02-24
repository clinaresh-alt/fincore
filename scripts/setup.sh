#!/bin/bash
# FinCore - Script de Setup Inicial

set -e

echo "================================================"
echo "  FinCore - Setup Inicial"
echo "================================================"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verificar Python
echo -e "${YELLOW}Verificando Python...${NC}"
python3 --version || { echo "Python 3 no encontrado"; exit 1; }

# Crear entorno virtual
echo -e "${YELLOW}Creando entorno virtual...${NC}"
cd backend
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
echo -e "${YELLOW}Instalando dependencias...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Copiar .env si no existe
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creando archivo .env...${NC}"
    cp .env.example .env
    echo -e "${GREEN}Edita el archivo .env con tus credenciales${NC}"
fi

# Crear tablas en la base de datos
echo -e "${YELLOW}Inicializando base de datos...${NC}"
python -c "
from app.core.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('Tablas creadas exitosamente')
"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Setup completado exitosamente!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Para iniciar el servidor:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Documentacion API: http://localhost:8000/docs"
