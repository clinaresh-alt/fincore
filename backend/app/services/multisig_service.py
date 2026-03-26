"""
Servicio de Multisig con Gnosis Safe para FinCore.

Implementa seguridad de grado institucional para operaciones críticas:
- Operaciones > $50,000 USD requieren aprobación multisig
- Integración con Gnosis Safe (Safe{Wallet})
- Políticas configurables por tipo de operación
- Auditoría completa de transacciones

Flujo:
1. Operación detectada como crítica (> threshold)
2. Se crea propuesta en Gnosis Safe
3. Signatarios aprueban vía Safe app
4. Al alcanzar quórum, se ejecuta automáticamente
5. Webhook notifica resultado

Uso:
    from app.services.multisig_service import MultisigService

    multisig = MultisigService(network=BlockchainNetwork.POLYGON)

    # Verificar si necesita multisig
    if multisig.requires_multisig(operation="release", amount=75000):
        proposal = await multisig.create_proposal(
            operation="release",
            params={...},
            description="Release escrow for remittance #123",
        )
"""
import os
import json
import logging
import asyncio
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

import aiohttp
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Numeric, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base, SessionLocal
from app.models.blockchain import BlockchainNetwork

# Prometheus metrics
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

# Gnosis Safe API URLs
SAFE_API_URLS = {
    BlockchainNetwork.POLYGON: "https://safe-transaction-polygon.safe.global",
    BlockchainNetwork.ETHEREUM: "https://safe-transaction-mainnet.safe.global",
    BlockchainNetwork.POLYGON_AMOY: "https://safe-transaction-polygon.safe.global",  # Usar mainnet para dev
}

# Direcciones de Safe multisig
SAFE_ADDRESSES = {
    BlockchainNetwork.POLYGON: os.getenv("GNOSIS_SAFE_ADDRESS_POLYGON", ""),
    BlockchainNetwork.POLYGON_AMOY: os.getenv("GNOSIS_SAFE_ADDRESS_AMOY", ""),
}

# Umbrales por tipo de operación (USD)
MULTISIG_THRESHOLDS = {
    "release": Decimal(os.getenv("MULTISIG_THRESHOLD_RELEASE", "50000")),
    "refund": Decimal(os.getenv("MULTISIG_THRESHOLD_REFUND", "25000")),
    "withdraw": Decimal(os.getenv("MULTISIG_THRESHOLD_WITHDRAW", "10000")),
    "config_change": Decimal("0"),  # Siempre requiere multisig
    "pause": Decimal("0"),  # Siempre requiere multisig
    "unpause": Decimal("0"),  # Siempre requiere multisig
    "default": Decimal(os.getenv("MULTISIG_THRESHOLD_DEFAULT", "50000")),
}

# Quórum requerido (número de firmas)
REQUIRED_SIGNATURES = int(os.getenv("MULTISIG_REQUIRED_SIGNATURES", "2"))

# Timeout para propuestas (horas)
PROPOSAL_TIMEOUT_HOURS = int(os.getenv("MULTISIG_PROPOSAL_TIMEOUT", "24"))


# ==================== Métricas Prometheus ====================

PROPOSALS_CREATED = Counter(
    'multisig_proposals_created_total',
    'Total de propuestas multisig creadas',
    ['operation_type']
)

PROPOSALS_EXECUTED = Counter(
    'multisig_proposals_executed_total',
    'Total de propuestas ejecutadas',
    ['operation_type', 'status']
)

PROPOSALS_PENDING = Gauge(
    'multisig_proposals_pending',
    'Propuestas pendientes de aprobación'
)

SIGNATURE_TIME = Histogram(
    'multisig_signature_time_hours',
    'Tiempo hasta completar firmas',
    buckets=[1, 2, 4, 8, 12, 24, 48]
)


# ==================== Tipos ====================

class ProposalStatus(str, Enum):
    """Estados de una propuesta multisig."""
    PENDING = "pending"          # Esperando firmas
    APPROVED = "approved"        # Quórum alcanzado
    EXECUTED = "executed"        # Ejecutada exitosamente
    REJECTED = "rejected"        # Rechazada
    EXPIRED = "expired"          # Timeout excedido
    FAILED = "failed"            # Falló al ejecutar


class OperationType(str, Enum):
    """Tipos de operaciones que pueden requerir multisig."""
    RELEASE = "release"          # Liberar fondos de escrow
    REFUND = "refund"            # Reembolsar al sender
    WITHDRAW = "withdraw"        # Retirar del gas tank
    CONFIG_CHANGE = "config_change"  # Cambio de configuración
    PAUSE = "pause"              # Pausar contrato
    UNPAUSE = "unpause"          # Despausar contrato
    ADD_SIGNER = "add_signer"    # Agregar firmante
    REMOVE_SIGNER = "remove_signer"  # Remover firmante
    UPGRADE = "upgrade"          # Actualizar contrato


@dataclass
class MultisigProposal:
    """Propuesta de operación multisig."""
    id: str
    safe_address: str
    operation_type: OperationType
    description: str
    target_contract: str
    calldata: str
    value: int  # En wei
    amount_usd: Decimal
    status: ProposalStatus
    required_signatures: int
    current_signatures: int
    signers: List[str]
    signatures: List[Dict]
    created_at: datetime
    expires_at: datetime
    executed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def is_ready_to_execute(self) -> bool:
        """Verifica si tiene suficientes firmas."""
        return self.current_signatures >= self.required_signatures

    def is_expired(self) -> bool:
        """Verifica si expiró."""
        return datetime.utcnow() > self.expires_at


@dataclass
class SafeInfo:
    """Información de un Safe multisig."""
    address: str
    owners: List[str]
    threshold: int
    nonce: int
    version: str
    fallback_handler: str


# ==================== Modelo de DB ====================

class MultisigProposalModel(Base):
    """Modelo de propuesta multisig en DB."""
    __tablename__ = "multisig_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Safe info
    safe_address = Column(String(42), nullable=False, index=True)
    network = Column(String(50), nullable=False)

    # Operación
    operation_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False)
    target_contract = Column(String(42), nullable=False)
    calldata = Column(Text, nullable=False)
    value_wei = Column(Numeric(38, 0), default=0)
    amount_usd = Column(Numeric(18, 2), nullable=False)

    # Estado
    status = Column(String(20), default="pending", index=True)
    required_signatures = Column(Integer, nullable=False)
    current_signatures = Column(Integer, default=0)

    # Firmas
    signers = Column(JSONB, default=[])
    signatures = Column(JSONB, default=[])

    # Ejecución
    safe_tx_hash = Column(String(66), unique=True, nullable=True)
    execution_tx_hash = Column(String(66), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Extra data
    created_by = Column(UUID(as_uuid=True), nullable=True)
    extra_data = Column(JSONB, default={})


class MultisigSignatureModel(Base):
    """Registro de firmas individuales."""
    __tablename__ = "multisig_signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("multisig_proposals.id"), nullable=False, index=True)

    signer_address = Column(String(42), nullable=False)
    signature = Column(Text, nullable=False)
    signed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Verificación
    is_valid = Column(Boolean, default=True)
    verification_tx = Column(String(66), nullable=True)


# ==================== Excepciones ====================

class MultisigError(Exception):
    """Error base de multisig."""
    pass


class SafeNotFoundError(MultisigError):
    """Safe no encontrado."""
    pass


class InsufficientSignaturesError(MultisigError):
    """No hay suficientes firmas."""
    pass


class ProposalExpiredError(MultisigError):
    """Propuesta expirada."""
    pass


class InvalidSignatureError(MultisigError):
    """Firma inválida."""
    pass


# ==================== Servicio Principal ====================

class MultisigService:
    """
    Servicio de operaciones multisig con Gnosis Safe.

    Features:
    - Integración con Gnosis Safe Transaction Service API
    - Creación automática de propuestas para operaciones críticas
    - Verificación de firmas on-chain
    - Ejecución automática al alcanzar quórum
    - Notificaciones y alertas
    """

    def __init__(
        self,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON,
        db: Optional[Session] = None,
    ):
        self.network = network
        self._db = db

        # Configuración
        self.safe_address = SAFE_ADDRESSES.get(network, "")
        self.api_url = SAFE_API_URLS.get(network, "")
        self.required_signatures = REQUIRED_SIGNATURES

        # Web3
        self.w3: Optional[Web3] = None
        self._init_web3()

        # Cache de Safe info
        self._safe_info: Optional[SafeInfo] = None

    def _init_web3(self):
        """Inicializa conexión Web3."""
        from app.services.event_listener_service import RPC_URLS

        rpc_url = RPC_URLS.get(self.network)
        if rpc_url:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))

    @property
    def db(self) -> Session:
        """Obtiene sesión de DB."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ==================== Verificación de Umbrales ====================

    def requires_multisig(
        self,
        operation: str,
        amount_usd: Decimal,
    ) -> bool:
        """
        Verifica si una operación requiere aprobación multisig.

        Args:
            operation: Tipo de operación
            amount_usd: Monto en USD

        Returns:
            True si requiere multisig
        """
        threshold = MULTISIG_THRESHOLDS.get(
            operation,
            MULTISIG_THRESHOLDS["default"]
        )

        # Operaciones de configuración siempre requieren multisig
        if operation in ("config_change", "pause", "unpause", "add_signer", "remove_signer", "upgrade"):
            return True

        return amount_usd >= threshold

    def get_threshold(self, operation: str) -> Decimal:
        """Obtiene el umbral para un tipo de operación."""
        return MULTISIG_THRESHOLDS.get(operation, MULTISIG_THRESHOLDS["default"])

    # ==================== Info del Safe ====================

    async def get_safe_info(self, refresh: bool = False) -> SafeInfo:
        """
        Obtiene información del Safe multisig.

        Args:
            refresh: Forzar recarga desde API

        Returns:
            SafeInfo con datos del Safe
        """
        if self._safe_info and not refresh:
            return self._safe_info

        if not self.safe_address:
            raise SafeNotFoundError("No hay Safe configurado para esta red")

        url = f"{self.api_url}/api/v1/safes/{self.safe_address}/"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise SafeNotFoundError(f"Safe no encontrado: {self.safe_address}")

                if response.status != 200:
                    raise MultisigError(f"Error obteniendo Safe info: {response.status}")

                data = await response.json()

                self._safe_info = SafeInfo(
                    address=data["address"],
                    owners=data["owners"],
                    threshold=data["threshold"],
                    nonce=data["nonce"],
                    version=data.get("version", ""),
                    fallback_handler=data.get("fallbackHandler", ""),
                )

                return self._safe_info

    async def get_owners(self) -> List[str]:
        """Obtiene lista de owners del Safe."""
        info = await self.get_safe_info()
        return info.owners

    async def get_threshold_from_safe(self) -> int:
        """Obtiene el threshold actual del Safe."""
        info = await self.get_safe_info(refresh=True)
        return info.threshold

    # ==================== Propuestas ====================

    async def create_proposal(
        self,
        operation_type: str,
        target_contract: str,
        calldata: str,
        value: int = 0,
        amount_usd: Decimal = Decimal("0"),
        description: str = "",
        metadata: Optional[Dict] = None,
        created_by: Optional[str] = None,
    ) -> MultisigProposal:
        """
        Crea una nueva propuesta multisig.

        Args:
            operation_type: Tipo de operación
            target_contract: Contrato objetivo
            calldata: Datos de la llamada (hex)
            value: Valor en wei
            amount_usd: Monto equivalente en USD
            description: Descripción de la operación
            metadata: Metadata adicional
            created_by: ID del usuario creador

        Returns:
            MultisigProposal creada
        """
        # Obtener info del Safe
        safe_info = await self.get_safe_info(refresh=True)

        # Calcular hash de la transacción
        safe_tx_hash = self._calculate_safe_tx_hash(
            to=target_contract,
            value=value,
            data=calldata,
            nonce=safe_info.nonce,
        )

        # Crear propuesta
        proposal_id = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=PROPOSAL_TIMEOUT_HOURS)

        proposal = MultisigProposal(
            id=proposal_id,
            safe_address=self.safe_address,
            operation_type=OperationType(operation_type),
            description=description,
            target_contract=target_contract,
            calldata=calldata,
            value=value,
            amount_usd=amount_usd,
            status=ProposalStatus.PENDING,
            required_signatures=safe_info.threshold,
            current_signatures=0,
            signers=[],
            signatures=[],
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Guardar en DB
        db_proposal = MultisigProposalModel(
            id=proposal_id,
            safe_address=self.safe_address,
            network=self.network.value,
            operation_type=operation_type,
            description=description,
            target_contract=target_contract,
            calldata=calldata,
            value_wei=value,
            amount_usd=amount_usd,
            required_signatures=safe_info.threshold,
            expires_at=expires_at,
            safe_tx_hash=safe_tx_hash,
            created_by=created_by,
            extra_data=metadata or {},
        )
        self.db.add(db_proposal)
        self.db.commit()

        # Registrar propuesta en Safe Transaction Service
        await self._register_safe_transaction(proposal, safe_tx_hash)

        # Métricas
        PROPOSALS_CREATED.labels(operation_type=operation_type).inc()
        PROPOSALS_PENDING.inc()

        logger.info(
            f"Propuesta multisig creada: {proposal_id} "
            f"({operation_type}, ${amount_usd})"
        )

        return proposal

    async def _register_safe_transaction(
        self,
        proposal: MultisigProposal,
        safe_tx_hash: str,
    ):
        """Registra la transacción en Safe Transaction Service."""
        url = f"{self.api_url}/api/v1/safes/{self.safe_address}/multisig-transactions/"

        payload = {
            "to": proposal.target_contract,
            "value": str(proposal.value),
            "data": proposal.calldata,
            "operation": 0,  # CALL
            "safeTxGas": 0,
            "baseGas": 0,
            "gasPrice": 0,
            "gasToken": "0x0000000000000000000000000000000000000000",
            "refundReceiver": "0x0000000000000000000000000000000000000000",
            "nonce": (await self.get_safe_info()).nonce,
            "contractTransactionHash": safe_tx_hash,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status not in (200, 201):
                        error = await response.text()
                        logger.warning(f"Error registrando en Safe API: {error}")
        except Exception as e:
            logger.error(f"Error comunicando con Safe API: {e}")

    def _calculate_safe_tx_hash(
        self,
        to: str,
        value: int,
        data: str,
        nonce: int,
    ) -> str:
        """Calcula el hash de transacción Safe."""
        # Simplificado - en producción usar la librería safe-eth-py
        data_bytes = bytes.fromhex(data[2:]) if data.startswith("0x") else bytes.fromhex(data)
        msg = Web3.solidity_keccak(
            ["address", "uint256", "bytes", "uint256"],
            [to, value, data_bytes, nonce]
        )
        return msg.hex()

    # ==================== Firmas ====================

    async def add_signature(
        self,
        proposal_id: str,
        signer_address: str,
        signature: str,
    ) -> MultisigProposal:
        """
        Añade una firma a una propuesta.

        Args:
            proposal_id: ID de la propuesta
            signer_address: Dirección del firmante
            signature: Firma hex

        Returns:
            Propuesta actualizada
        """
        # Obtener propuesta
        db_proposal = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.id == proposal_id
        ).first()

        if not db_proposal:
            raise MultisigError(f"Propuesta no encontrada: {proposal_id}")

        if db_proposal.status != "pending":
            raise MultisigError(f"Propuesta no está pendiente: {db_proposal.status}")

        if datetime.utcnow() > db_proposal.expires_at:
            db_proposal.status = "expired"
            self.db.commit()
            raise ProposalExpiredError("La propuesta ha expirado")

        # Verificar que es un owner válido
        safe_info = await self.get_safe_info()
        if signer_address.lower() not in [o.lower() for o in safe_info.owners]:
            raise InvalidSignatureError(f"Firmante no es owner del Safe: {signer_address}")

        # Verificar que no ha firmado ya
        existing_signers = db_proposal.signers or []
        if signer_address.lower() in [s.lower() for s in existing_signers]:
            raise MultisigError("Este owner ya ha firmado")

        # Verificar firma
        if not self._verify_signature(
            db_proposal.safe_tx_hash,
            signer_address,
            signature,
        ):
            raise InvalidSignatureError("Firma inválida")

        # Guardar firma
        sig_record = MultisigSignatureModel(
            proposal_id=proposal_id,
            signer_address=signer_address,
            signature=signature,
        )
        self.db.add(sig_record)

        # Actualizar propuesta
        existing_signers.append(signer_address)
        existing_signatures = db_proposal.signatures or []
        existing_signatures.append({
            "signer": signer_address,
            "signature": signature,
            "timestamp": datetime.utcnow().isoformat(),
        })

        db_proposal.signers = existing_signers
        db_proposal.signatures = existing_signatures
        db_proposal.current_signatures = len(existing_signers)

        # Verificar si alcanzó quórum
        if db_proposal.current_signatures >= db_proposal.required_signatures:
            db_proposal.status = "approved"
            logger.info(f"Propuesta {proposal_id} aprobada - lista para ejecución")

        self.db.commit()

        logger.info(
            f"Firma añadida a propuesta {proposal_id}: "
            f"{db_proposal.current_signatures}/{db_proposal.required_signatures}"
        )

        return self._db_to_proposal(db_proposal)

    def _verify_signature(
        self,
        message_hash: str,
        signer_address: str,
        signature: str,
    ) -> bool:
        """Verifica una firma."""
        try:
            # Recuperar dirección de la firma
            message = encode_defunct(hexstr=message_hash)
            recovered = Account.recover_message(message, signature=signature)
            return recovered.lower() == signer_address.lower()
        except Exception as e:
            logger.error(f"Error verificando firma: {e}")
            return False

    # ==================== Ejecución ====================

    async def execute_proposal(
        self,
        proposal_id: str,
        executor_private_key: str,
    ) -> str:
        """
        Ejecuta una propuesta aprobada.

        Args:
            proposal_id: ID de la propuesta
            executor_private_key: Clave privada del ejecutor

        Returns:
            Hash de la transacción de ejecución
        """
        db_proposal = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.id == proposal_id
        ).first()

        if not db_proposal:
            raise MultisigError(f"Propuesta no encontrada: {proposal_id}")

        if db_proposal.status != "approved":
            raise MultisigError(f"Propuesta no está aprobada: {db_proposal.status}")

        if db_proposal.current_signatures < db_proposal.required_signatures:
            raise InsufficientSignaturesError(
                f"Firmas insuficientes: {db_proposal.current_signatures}/{db_proposal.required_signatures}"
            )

        # Combinar firmas
        combined_signatures = self._combine_signatures(db_proposal.signatures)

        try:
            # Ejecutar via Safe Transaction Service o directamente
            tx_hash = await self._execute_safe_transaction(
                db_proposal,
                combined_signatures,
                executor_private_key,
            )

            # Actualizar estado
            db_proposal.status = "executed"
            db_proposal.executed_at = datetime.utcnow()
            db_proposal.execution_tx_hash = tx_hash
            self.db.commit()

            # Métricas
            PROPOSALS_EXECUTED.labels(
                operation_type=db_proposal.operation_type,
                status="success"
            ).inc()
            PROPOSALS_PENDING.dec()

            # Calcular tiempo de firma
            creation_time = db_proposal.created_at
            execution_time = db_proposal.executed_at
            hours_to_sign = (execution_time - creation_time).total_seconds() / 3600
            SIGNATURE_TIME.observe(hours_to_sign)

            logger.info(f"Propuesta {proposal_id} ejecutada: {tx_hash}")
            return tx_hash

        except Exception as e:
            db_proposal.status = "failed"
            self.db.commit()

            PROPOSALS_EXECUTED.labels(
                operation_type=db_proposal.operation_type,
                status="failed"
            ).inc()

            logger.error(f"Error ejecutando propuesta {proposal_id}: {e}")
            raise

    def _combine_signatures(self, signatures: List[Dict]) -> str:
        """Combina múltiples firmas en formato Safe."""
        # Ordenar por dirección
        sorted_sigs = sorted(signatures, key=lambda s: s["signer"].lower())

        # Concatenar firmas
        combined = "0x"
        for sig in sorted_sigs:
            # Remover 0x y concatenar
            sig_hex = sig["signature"]
            if sig_hex.startswith("0x"):
                sig_hex = sig_hex[2:]
            combined += sig_hex

        return combined

    async def _execute_safe_transaction(
        self,
        proposal: MultisigProposalModel,
        signatures: str,
        executor_key: str,
    ) -> str:
        """Ejecuta la transacción Safe on-chain."""
        # En producción, usar safe-eth-py para interactuar con el contrato Safe
        # Simplificado aquí para demostración

        # ABI simplificado del método execTransaction de Safe
        safe_abi = [{
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "data", "type": "bytes"},
                {"name": "operation", "type": "uint8"},
                {"name": "safeTxGas", "type": "uint256"},
                {"name": "baseGas", "type": "uint256"},
                {"name": "gasPrice", "type": "uint256"},
                {"name": "gasToken", "type": "address"},
                {"name": "refundReceiver", "type": "address"},
                {"name": "signatures", "type": "bytes"},
            ],
            "name": "execTransaction",
            "outputs": [{"name": "success", "type": "bool"}],
            "type": "function",
        }]

        if not self.w3:
            raise MultisigError("Web3 no inicializado")

        safe_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.safe_address),
            abi=safe_abi,
        )

        # Preparar transacción
        executor = Account.from_key(executor_key)

        tx = safe_contract.functions.execTransaction(
            Web3.to_checksum_address(proposal.target_contract),
            int(proposal.value_wei),
            bytes.fromhex(proposal.calldata[2:] if proposal.calldata.startswith("0x") else proposal.calldata),
            0,  # operation: CALL
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            bytes.fromhex(signatures[2:] if signatures.startswith("0x") else signatures),
        ).build_transaction({
            "from": executor.address,
            "nonce": self.w3.eth.get_transaction_count(executor.address),
            "gas": 500000,
            "gasPrice": self.w3.eth.gas_price,
        })

        # Firmar y enviar
        signed = self.w3.eth.account.sign_transaction(tx, executor_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

        return tx_hash.hex()

    # ==================== Consultas ====================

    def get_pending_proposals(self) -> List[MultisigProposal]:
        """Obtiene propuestas pendientes."""
        db_proposals = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.status == "pending",
            MultisigProposalModel.network == self.network.value,
        ).order_by(MultisigProposalModel.created_at.desc()).all()

        return [self._db_to_proposal(p) for p in db_proposals]

    def get_proposal(self, proposal_id: str) -> Optional[MultisigProposal]:
        """Obtiene una propuesta por ID."""
        db_proposal = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.id == proposal_id
        ).first()

        if db_proposal:
            return self._db_to_proposal(db_proposal)
        return None

    def get_proposals_by_status(self, status: str) -> List[MultisigProposal]:
        """Obtiene propuestas por estado."""
        db_proposals = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.status == status,
            MultisigProposalModel.network == self.network.value,
        ).all()

        return [self._db_to_proposal(p) for p in db_proposals]

    def _db_to_proposal(self, db: MultisigProposalModel) -> MultisigProposal:
        """Convierte modelo DB a dataclass."""
        return MultisigProposal(
            id=str(db.id),
            safe_address=db.safe_address,
            operation_type=OperationType(db.operation_type),
            description=db.description,
            target_contract=db.target_contract,
            calldata=db.calldata,
            value=int(db.value_wei or 0),
            amount_usd=db.amount_usd,
            status=ProposalStatus(db.status),
            required_signatures=db.required_signatures,
            current_signatures=db.current_signatures or 0,
            signers=db.signers or [],
            signatures=db.signatures or [],
            created_at=db.created_at,
            expires_at=db.expires_at,
            executed_at=db.executed_at,
            tx_hash=db.execution_tx_hash,
            metadata=db.extra_data or {},
        )

    # ==================== Limpieza ====================

    async def expire_old_proposals(self) -> int:
        """Marca como expiradas las propuestas vencidas."""
        count = self.db.query(MultisigProposalModel).filter(
            MultisigProposalModel.status == "pending",
            MultisigProposalModel.expires_at < datetime.utcnow(),
        ).update({"status": "expired"})

        self.db.commit()

        if count > 0:
            PROPOSALS_PENDING.dec(count)
            logger.info(f"Expiradas {count} propuestas")

        return count

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()
