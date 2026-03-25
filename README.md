# FinCore

Plataforma de tokenizacion de activos financieros para el mercado mexicano. Permite a empresas emitir tokens respaldados por activos reales y a inversionistas participar en proyectos de inversion de manera regulada.

## Arquitectura

```
fincore/
├── backend/          # API FastAPI (Python 3.12)
├── frontend/         # Aplicacion Next.js (React + TypeScript)
├── database/         # Scripts y migraciones PostgreSQL
├── docs/             # Documentacion adicional
├── scripts/          # Scripts de utilidad
├── monitoring/       # Configuracion de monitoreo
├── nginx/            # Configuracion de proxy reverso
├── vault/            # Configuracion de HashiCorp Vault
└── docker-compose.bunker.yml
```

## Tecnologias

### Backend
- **Framework**: FastAPI con Python 3.12
- **Base de datos**: PostgreSQL + SQLAlchemy
- **Autenticacion**: JWT con refresh tokens
- **Blockchain**: Web3.py para integracion con Polygon/Ethereum
- **Seguridad**: Cifrado AES-256, PBKDF2 para derivacion de claves

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript + Tailwind CSS
- **Componentes**: shadcn/ui + Radix UI
- **Estado**: Zustand
- **Blockchain**: RainbowKit + wagmi + viem

### Infraestructura
- Docker + Docker Compose
- Nginx como reverse proxy
- HashiCorp Vault para secretos

## Modulos Principales

### Tokenizacion
- Emision de tokens ERC-20 respaldados por activos
- Contratos inteligentes auditados (OpenZeppelin v5)
- Soporte multi-red: Polygon, Ethereum, Arbitrum, Base

### Compliance (PLD/AML)
- Verificacion KYC con niveles (INE, CURP, comprobante domicilio)
- Monitoreo AML segun LFPIORPI
- Reportes regulatorios automaticos
- Verificacion PEP (Personas Expuestas Politicamente)

### Motor Financiero
- Calculo de VAN, TIR, ROI, Payback
- Credit scoring con formula: S = (C × 0.40) + (H × 0.35) + (G × 0.25)
- Analisis de sensibilidad
- Evaluacion de riesgo automatizada

### Auditoria de Smart Contracts
- Integracion con Slither para analisis estatico
- Monitoreo de transacciones en tiempo real
- Respuesta ante incidentes (IRP basado en NIST SP 800-61)
- Deteccion de patrones sospechosos

### Analytics
- Dashboard de metricas de plataforma
- Distribucion sectorial de inversiones
- Performance de proyectos
- Indicadores de seguridad

## Requisitos

### Backend
- Python 3.12+
- PostgreSQL 15+
- Redis (opcional, para cache)

### Frontend
- Node.js 18+
- npm o pnpm

## Instalacion

### Backend

```bash
cd backend

# Crear entorno virtual
python3.12 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# Ejecutar migraciones
alembic upgrade head

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env.local
# Editar .env.local con tus configuraciones

# Iniciar servidor de desarrollo
npm run dev
```

La aplicacion estara disponible en:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Documentacion API: http://localhost:8000/docs

## Variables de Entorno

### Backend (.env)

```env
# Base de datos
DATABASE_URL=postgresql://user:password@localhost:5432/fincore

# Seguridad
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# Blockchain
POLYGON_RPC_URL=https://polygon-rpc.com
BLOCKCHAIN_OPERATOR_KEY=0x...

# AWS (para DocumentVault)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your-project-id
```

## Testing

### Backend

```bash
cd backend
source venv/bin/activate

# Ejecutar todos los tests
pytest

# Ejecutar con cobertura
pytest --cov=app --cov-report=html

# Ejecutar tests especificos
pytest tests/test_financial_engine.py -v
pytest -m unit  # Solo tests unitarios
pytest -m audit  # Solo tests de auditoria
```

### Frontend

```bash
cd frontend

# Ejecutar tests
npm test

# Ejecutar en modo watch
npm run test:watch
```

## Estructura del Backend

```
backend/
├── app/
│   ├── api/v1/endpoints/    # Endpoints REST
│   ├── core/                # Configuracion, seguridad, DB
│   ├── models/              # Modelos SQLAlchemy
│   ├── schemas/             # Schemas Pydantic
│   └── services/            # Logica de negocio
│       ├── analytics_service.py
│       ├── financial_engine.py
│       ├── risk_engine.py
│       ├── blockchain_service.py
│       ├── notification_service.py
│       ├── audit/           # Slither, monitoreo, incidentes
│       └── compliance/      # KYC, AML, reportes
└── tests/                   # Tests unitarios e integracion
```

## Estructura del Frontend

```
frontend/
├── src/
│   ├── app/                 # App Router (Next.js 14)
│   ├── components/
│   │   ├── ui/              # Componentes base (shadcn)
│   │   └── ...              # Componentes de negocio
│   ├── hooks/               # Custom hooks
│   ├── lib/                 # Utilidades
│   └── stores/              # Estado global (Zustand)
└── src/__tests__/           # Tests
```

## API Endpoints Principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Autenticacion |
| POST | `/api/v1/auth/register` | Registro de usuario |
| GET | `/api/v1/projects` | Listar proyectos |
| POST | `/api/v1/projects` | Crear proyecto |
| GET | `/api/v1/analytics/overview` | Metricas de plataforma |
| POST | `/api/v1/compliance/kyc/start` | Iniciar verificacion KYC |
| POST | `/api/v1/blockchain/deploy` | Desplegar contrato |
| GET | `/api/v1/audit/reports` | Reportes de auditoria |

## Seguridad

- Autenticacion JWT con refresh tokens
- Cifrado de datos sensibles (AES-256)
- Rate limiting en endpoints criticos
- Validacion de entrada con Pydantic
- Sanitizacion de outputs
- CORS configurado apropiadamente
- Headers de seguridad (CSP, HSTS, etc.)

## Compliance

La plataforma cumple con:
- **LFPIORPI**: Ley Federal para la Prevencion e Identificacion de Operaciones con Recursos de Procedencia Ilicita
- **Disposiciones CNBV**: Comision Nacional Bancaria y de Valores
- **KYC/AML**: Verificacion de identidad y prevencion de lavado de dinero

## Licencia

Propietario - Todos los derechos reservados.

## Contacto

Para mas informacion, contactar al equipo de desarrollo.
