"""
Fixtures compartidas para tests de FinCore.
"""
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Configurar event loop para tests async
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== BLOCKCHAIN FIXTURES ====================

@pytest.fixture
def mock_web3():
    """Mock de Web3 para tests sin conexion a red real."""
    mock = MagicMock()
    mock.is_connected.return_value = True
    mock.eth.chain_id = 137  # Polygon
    mock.eth.block_number = 50000000
    mock.eth.gas_price = 30000000000  # 30 Gwei
    mock.eth.get_balance.return_value = 1000000000000000000  # 1 ETH/MATIC
    mock.eth.get_transaction_count.return_value = 10
    mock.eth.max_priority_fee = 2000000000  # 2 Gwei

    # Mock para fee_history
    mock.eth.fee_history.return_value = {
        'baseFeePerGas': [20000000000],
        'gasUsedRatio': [0.5],
        'reward': [[2000000000]]
    }

    return mock


@pytest.fixture
def mock_account():
    """Mock de cuenta Ethereum."""
    account = MagicMock()
    account.address = "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
    account.key = b'\x00' * 32
    account.sign_transaction.return_value = MagicMock(
        raw_transaction=b'\x00' * 100
    )
    return account


@pytest.fixture
def sample_contract_abi():
    """ABI de ejemplo para tests."""
    return [
        {
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"type": "uint8"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]


@pytest.fixture
def sample_tx_receipt():
    """Recibo de transaccion de ejemplo."""
    return {
        'status': 1,
        'transactionHash': '0x' + '1' * 64,
        'blockNumber': 50000001,
        'gasUsed': 21000,
        'logs': []
    }


@pytest.fixture
def sample_wallet_address():
    """Direccion de wallet de ejemplo."""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"


@pytest.fixture
def sample_contract_address():
    """Direccion de contrato de ejemplo."""
    return "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC Polygon


# ==================== AUDIT FIXTURES ====================

@pytest.fixture
def sample_vulnerability():
    """Vulnerabilidad de ejemplo para tests de auditoria."""
    return {
        "id": str(uuid4()),
        "type": "reentrancy",
        "severity": "high",
        "title": "Reentrancy vulnerability in withdraw function",
        "description": "The withdraw function is vulnerable to reentrancy attacks",
        "location": {
            "file": "Contract.sol",
            "line": 45,
            "function": "withdraw"
        },
        "recommendation": "Use ReentrancyGuard or checks-effects-interactions pattern"
    }


@pytest.fixture
def sample_audit_result():
    """Resultado de auditoria de ejemplo."""
    return {
        "contract_path": "/contracts/Test.sol",
        "timestamp": datetime.utcnow().isoformat(),
        "security_score": 75,
        "vulnerabilities_count": {
            "high": 1,
            "medium": 2,
            "low": 3,
            "informational": 5
        },
        "high_severity_issues": [
            {
                "type": "reentrancy",
                "description": "Reentrancy in withdraw()",
                "location": "line 45"
            }
        ],
        "recommendations": [
            "Implement ReentrancyGuard",
            "Use SafeMath for arithmetic operations",
            "Add input validation"
        ]
    }


@pytest.fixture
def sample_transaction_data():
    """Datos de transaccion para analisis."""
    return {
        "tx_hash": "0x" + "a" * 64,
        "from_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
        "to_address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "value": Decimal("1000.00"),
        "gas_price": 30000000000,
        "input_data": "0xa9059cbb",  # transfer signature
        "network": "polygon"
    }


@pytest.fixture
def sample_alert():
    """Alerta de ejemplo."""
    return {
        "id": str(uuid4()),
        "type": "high_value_transfer",
        "severity": "medium",
        "title": "High value transfer detected",
        "description": "Transfer of 1000 USDC detected",
        "transaction_hash": "0x" + "a" * 64,
        "contract_address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "timestamp": datetime.utcnow()
    }


@pytest.fixture
def sample_incident():
    """Incidente de ejemplo."""
    return {
        "id": str(uuid4()),
        "title": "Suspicious activity detected",
        "description": "Multiple high-value transfers from same address",
        "severity": "sev2",
        "status": "investigating",
        "detected_at": datetime.utcnow(),
        "affected_contracts": ["0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"],
        "related_transactions": ["0x" + "a" * 64, "0x" + "b" * 64]
    }


# ==================== USER FIXTURES ====================

@pytest.fixture
def sample_user():
    """Usuario de ejemplo para tests."""
    return {
        "id": uuid4(),
        "email": "test@fincore.mx",
        "rol": "Admin",
        "is_active": True,
        "mfa_enabled": False
    }


@pytest.fixture
def sample_investor():
    """Inversionista de ejemplo."""
    return {
        "id": uuid4(),
        "email": "investor@example.com",
        "rol": "Inversionista",
        "is_active": True,
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
    }


# ==================== DATABASE FIXTURES ====================

@pytest.fixture
def mock_db_session():
    """Mock de sesion de base de datos."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.query = MagicMock()
    session.execute = AsyncMock()
    return session


# ==================== NOTIFICATION FIXTURES ====================

@pytest.fixture
def sample_notification():
    """Notificacion de ejemplo."""
    return {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "notification_type": "audit_completed",
        "priority": "high",
        "title": "Auditoria completada",
        "message": "La auditoria del contrato ha finalizado con riesgo ALTO",
        "data": {
            "audit_id": str(uuid4()),
            "risk_level": "HIGH",
            "findings_count": 5
        },
        "is_read": False,
        "created_at": datetime.utcnow().isoformat()
    }


# ==================== HELPERS ====================

@pytest.fixture
def assert_decimal_equal():
    """Helper para comparar Decimals con tolerancia."""
    def _assert(a: Decimal, b: Decimal, tolerance: Decimal = Decimal("0.0001")):
        assert abs(a - b) < tolerance, f"{a} != {b} (tolerance: {tolerance})"
    return _assert
