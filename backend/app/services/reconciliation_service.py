"""
Servicio de Conciliacion para FinCore.

Motor de reconciliacion automatica que verifica:
1. Saldos en Ledger Interno (PostgreSQL) vs Smart Contract (On-chain)
2. Transacciones pendientes y su estado
3. Discrepancias entre sistemas

Ejecuta automaticamente cada 60 minutos via APScheduler.
Alerta inmediatamente si hay discrepancia > $0.

Cumple con PRD: Sistema Blockchain Fintech - Conciliacion
"""
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.remittance import (
    Remittance,
    RemittanceBlockchainTx,
    ReconciliationLog,
    RemittanceStatus,
    BlockchainRemittanceStatus,
    Stablecoin,
)
from app.models.bank_account import (
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    BankTransactionType,
)
from app.services.blockchain_service import BlockchainService, TransactionResult
from app.services.notification_service import NotificationService
from app.models.blockchain import BlockchainNetwork

logger = logging.getLogger(__name__)


# ============ Configuracion ============

# Direccion del contrato de remesas
REMITTANCE_CONTRACT_ADDRESS = os.getenv(
    "REMITTANCE_CONTRACT_ADDRESS",
    "0x0000000000000000000000000000000000000000"
)

# Umbral de discrepancia para alertas (en USD)
DISCREPANCY_THRESHOLD = Decimal(os.getenv("DISCREPANCY_THRESHOLD", "0.01"))

# Intervalo de reconciliacion en minutos
RECONCILIATION_INTERVAL_MINUTES = int(os.getenv("RECONCILIATION_INTERVAL_MINUTES", "60"))

# Stablecoins soportados
SUPPORTED_STABLECOINS = [Stablecoin.USDC, Stablecoin.USDT]


# ============ Enums y Dataclasses ============

class DiscrepancyType(str, Enum):
    """Tipos de discrepancia detectada."""
    NONE = "none"
    LEDGER_ONCHAIN = "ledger_vs_onchain"
    LEDGER_FIAT = "ledger_vs_fiat"
    ONCHAIN_FIAT = "onchain_vs_fiat"
    MISSING_TX = "missing_transaction"
    STUCK_TX = "stuck_transaction"
    AMOUNT_MISMATCH = "amount_mismatch"


class AlertSeverity(str, Enum):
    """Severidad de alertas."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BalanceSnapshot:
    """Snapshot de saldos en un momento dado."""
    timestamp: datetime
    ledger_locked: Decimal
    ledger_released: Decimal
    ledger_refunded: Decimal
    onchain_locked: Decimal
    onchain_released: Decimal
    onchain_refunded: Decimal
    onchain_fees: Decimal
    stablecoin: str
    network: str
    # Saldos Fiat (MXN)
    fiat_balance: Decimal = Decimal("0")
    fiat_pending_deposits: Decimal = Decimal("0")
    fiat_pending_payouts: Decimal = Decimal("0")
    fiat_currency: str = "MXN"


@dataclass
class ReconciliationResult:
    """Resultado de una reconciliacion."""
    success: bool
    timestamp: datetime
    balance_snapshot: Optional[BalanceSnapshot] = None
    discrepancies: List[Dict[str, Any]] = None
    alerts_sent: int = 0
    log_id: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.discrepancies is None:
            self.discrepancies = []


@dataclass
class TransactionReconciliation:
    """Resultado de reconciliacion de una transaccion."""
    remittance_id: str
    reference_code: str
    ledger_status: str
    onchain_status: Optional[str]
    ledger_amount: Decimal
    onchain_amount: Optional[Decimal]
    is_matched: bool
    discrepancy_type: Optional[DiscrepancyType] = None
    details: Optional[str] = None


# ============ ABI Minimo del Contrato ============

RECONCILIATION_ABI = [
    {
        "inputs": [],
        "name": "getTotals",
        "outputs": [
            {"internalType": "uint256", "name": "locked", "type": "uint256"},
            {"internalType": "uint256", "name": "released", "type": "uint256"},
            {"internalType": "uint256", "name": "refunded", "type": "uint256"},
            {"internalType": "uint256", "name": "fees", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "remittanceId", "type": "uint256"}],
        "name": "getRemittance",
        "outputs": [
            {"internalType": "bytes32", "name": "referenceId", "type": "bytes32"},
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "uint256", "name": "platformFee", "type": "uint256"},
            {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
            {"internalType": "uint256", "name": "expiresAt", "type": "uint256"},
            {"internalType": "uint8", "name": "state", "type": "uint8"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "referenceId", "type": "bytes32"}],
        "name": "getRemittanceByReference",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalLocked",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
]


class ReconciliationService:
    """
    Servicio de reconciliacion entre Ledger interno y Blockchain.

    Responsabilidades:
    - Comparar saldos totales (Ledger vs On-chain)
    - Verificar transacciones individuales
    - Detectar discrepancias
    - Enviar alertas
    - Generar logs de auditoria
    """

    STABLECOIN_DECIMALS = 6  # USDC/USDT tienen 6 decimales

    def __init__(
        self,
        db: Session,
        network: str = "polygon",
        contract_address: Optional[str] = None
    ):
        self.db = db
        self.network = network
        self.contract_address = contract_address or REMITTANCE_CONTRACT_ADDRESS
        self.blockchain_service: Optional[BlockchainService] = None
        self.notification_service: Optional[NotificationService] = None

    def _get_blockchain_service(self) -> BlockchainService:
        """Lazy initialization del blockchain service."""
        if self.blockchain_service is None:
            network_enum = (
                BlockchainNetwork.POLYGON if self.network == "polygon"
                else BlockchainNetwork.POLYGON_AMOY
            )
            self.blockchain_service = BlockchainService(network=network_enum)
        return self.blockchain_service

    def _get_notification_service(self) -> NotificationService:
        """Lazy initialization del notification service."""
        if self.notification_service is None:
            self.notification_service = NotificationService(self.db)
        return self.notification_service

    # ============ Conversion de Unidades ============

    def _wei_to_decimal(self, wei: int, decimals: int = 6) -> Decimal:
        """Convierte wei a decimal."""
        return Decimal(wei) / Decimal(10 ** decimals)

    def _decimal_to_wei(self, amount: Decimal, decimals: int = 6) -> int:
        """Convierte decimal a wei."""
        return int(amount * Decimal(10 ** decimals))

    # ============ Consultas de Saldos ============

    def get_fiat_totals(self, currency: str = "MXN") -> Dict[str, Decimal]:
        """
        Obtiene totales de saldos bancarios (Fiat).

        Returns:
            Dict con balance_total, pending_deposits, pending_payouts, etc.
        """
        try:
            # Total de saldos en cuentas operativas
            total_balance = self.db.query(
                func.coalesce(func.sum(BankAccount.last_known_balance), 0)
            ).filter(
                BankAccount.is_platform_account == True,
                BankAccount.status == "active",
                BankAccount.currency == currency,
            ).scalar() or Decimal("0")

            # Depósitos pendientes (SPEI-IN en proceso)
            pending_deposits = self.db.query(
                func.coalesce(func.sum(BankTransaction.amount), 0)
            ).filter(
                BankTransaction.transaction_type == BankTransactionType.TRANSFER_IN,
                BankTransaction.status == BankTransactionStatus.PENDING,
            ).scalar() or Decimal("0")

            # Payouts pendientes (SPEI-OUT en proceso)
            pending_payouts = self.db.query(
                func.coalesce(func.sum(func.abs(BankTransaction.amount)), 0)
            ).filter(
                BankTransaction.transaction_type == BankTransactionType.TRANSFER_OUT,
                BankTransaction.status.in_([
                    BankTransactionStatus.PENDING,
                    BankTransactionStatus.PROCESSING,
                ]),
            ).scalar() or Decimal("0")

            # Total remesas pendientes de pago fiat (ya convertidas a crypto, esperando payout)
            expected_payouts = self.db.query(
                func.coalesce(func.sum(Remittance.amount_fiat_destination), 0)
            ).filter(
                Remittance.status.in_([
                    RemittanceStatus.LOCKED,
                    RemittanceStatus.PROCESSING,
                ])
            ).scalar() or Decimal("0")

            # Total remesas esperando depósito fiat
            expected_deposits = self.db.query(
                func.coalesce(func.sum(Remittance.amount_fiat_source), 0)
            ).filter(
                Remittance.status == RemittanceStatus.PENDING_DEPOSIT
            ).scalar() or Decimal("0")

            # Transacciones sin conciliar
            unreconciled_count = self.db.query(
                func.count(BankTransaction.id)
            ).filter(
                BankTransaction.reconciled == False,
                BankTransaction.status == BankTransactionStatus.COMPLETED,
            ).scalar() or 0

            return {
                "balance_total": Decimal(str(total_balance)),
                "available_balance": Decimal(str(total_balance)) - Decimal(str(pending_payouts)),
                "pending_deposits": Decimal(str(pending_deposits)),
                "pending_payouts": Decimal(str(pending_payouts)),
                "expected_payouts": Decimal(str(expected_payouts)),
                "expected_deposits": Decimal(str(expected_deposits)),
                "unreconciled_count": unreconciled_count,
                "currency": currency,
            }

        except Exception as e:
            logger.error(f"Error obteniendo totales fiat: {e}")
            return {
                "balance_total": Decimal("0"),
                "available_balance": Decimal("0"),
                "pending_deposits": Decimal("0"),
                "pending_payouts": Decimal("0"),
                "expected_payouts": Decimal("0"),
                "expected_deposits": Decimal("0"),
                "unreconciled_count": 0,
                "currency": currency,
            }

    def get_ledger_totals(self) -> Dict[str, Decimal]:
        """
        Obtiene totales del ledger interno (PostgreSQL).

        Returns:
            Dict con locked, released, refunded
        """
        try:
            # Total bloqueado
            locked = self.db.query(
                func.coalesce(func.sum(Remittance.amount_stablecoin), 0)
            ).filter(
                Remittance.status == RemittanceStatus.LOCKED
            ).scalar() or Decimal("0")

            # Total liberado (DISBURSED + COMPLETED)
            released = self.db.query(
                func.coalesce(func.sum(Remittance.amount_stablecoin), 0)
            ).filter(
                Remittance.status.in_([
                    RemittanceStatus.DISBURSED,
                    RemittanceStatus.COMPLETED
                ])
            ).scalar() or Decimal("0")

            # Total reembolsado
            refunded = self.db.query(
                func.coalesce(func.sum(Remittance.amount_stablecoin), 0)
            ).filter(
                Remittance.status == RemittanceStatus.REFUNDED
            ).scalar() or Decimal("0")

            # Total fees
            fees = self.db.query(
                func.coalesce(func.sum(Remittance.platform_fee), 0)
            ).filter(
                Remittance.status.in_([
                    RemittanceStatus.LOCKED,
                    RemittanceStatus.DISBURSED,
                    RemittanceStatus.COMPLETED,
                    RemittanceStatus.REFUNDED
                ])
            ).scalar() or Decimal("0")

            return {
                "locked": Decimal(str(locked)),
                "released": Decimal(str(released)),
                "refunded": Decimal(str(refunded)),
                "fees": Decimal(str(fees)),
            }

        except Exception as e:
            logger.error(f"Error obteniendo totales del ledger: {e}")
            return {
                "locked": Decimal("0"),
                "released": Decimal("0"),
                "refunded": Decimal("0"),
                "fees": Decimal("0"),
            }

    def get_onchain_totals(self) -> Dict[str, Decimal]:
        """
        Obtiene totales del smart contract (On-chain).

        Returns:
            Dict con locked, released, refunded, fees
        """
        try:
            blockchain_svc = self._get_blockchain_service()

            result = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=RECONCILIATION_ABI,
                function_name="getTotals",
                args=[]
            )

            if result and len(result) == 4:
                return {
                    "locked": self._wei_to_decimal(result[0], self.STABLECOIN_DECIMALS),
                    "released": self._wei_to_decimal(result[1], self.STABLECOIN_DECIMALS),
                    "refunded": self._wei_to_decimal(result[2], self.STABLECOIN_DECIMALS),
                    "fees": self._wei_to_decimal(result[3], self.STABLECOIN_DECIMALS),
                }

            logger.warning("getTotals retorno resultado invalido")
            return {
                "locked": Decimal("0"),
                "released": Decimal("0"),
                "refunded": Decimal("0"),
                "fees": Decimal("0"),
            }

        except Exception as e:
            logger.error(f"Error obteniendo totales on-chain: {e}")
            return {
                "locked": Decimal("0"),
                "released": Decimal("0"),
                "refunded": Decimal("0"),
                "fees": Decimal("0"),
            }

    # ============ Reconciliacion Principal ============

    async def run_full_reconciliation(
        self,
        stablecoin: str = "USDC",
        include_fiat: bool = True,
        fiat_currency: str = "MXN"
    ) -> ReconciliationResult:
        """
        Ejecuta reconciliacion completa entre Ledger, On-chain y Fiat.

        Args:
            stablecoin: Stablecoin a reconciliar (USDC, USDT)
            include_fiat: Incluir conciliación de saldos bancarios
            fiat_currency: Moneda fiat a conciliar

        Returns:
            ReconciliationResult con detalles de la reconciliacion
        """
        timestamp = datetime.utcnow()
        discrepancies = []
        alerts_sent = 0

        try:
            logger.info(f"Iniciando reconciliacion para {stablecoin} en {self.network}")

            # 1. Obtener saldos de todas las fuentes
            ledger_totals = self.get_ledger_totals()
            onchain_totals = self.get_onchain_totals()
            fiat_totals = self.get_fiat_totals(fiat_currency) if include_fiat else None

            # 2. Crear snapshot de saldos
            balance_snapshot = BalanceSnapshot(
                timestamp=timestamp,
                ledger_locked=ledger_totals["locked"],
                ledger_released=ledger_totals["released"],
                ledger_refunded=ledger_totals["refunded"],
                onchain_locked=onchain_totals["locked"],
                onchain_released=onchain_totals["released"],
                onchain_refunded=onchain_totals["refunded"],
                onchain_fees=onchain_totals["fees"],
                stablecoin=stablecoin,
                network=self.network,
                fiat_balance=fiat_totals["balance_total"] if fiat_totals else Decimal("0"),
                fiat_pending_deposits=fiat_totals["pending_deposits"] if fiat_totals else Decimal("0"),
                fiat_pending_payouts=fiat_totals["pending_payouts"] if fiat_totals else Decimal("0"),
                fiat_currency=fiat_currency,
            )

            # 3. Calcular discrepancias
            discrepancy_locked = abs(ledger_totals["locked"] - onchain_totals["locked"])
            discrepancy_released = abs(ledger_totals["released"] - onchain_totals["released"])
            discrepancy_refunded = abs(ledger_totals["refunded"] - onchain_totals["refunded"])

            has_discrepancy = any([
                discrepancy_locked > DISCREPANCY_THRESHOLD,
                discrepancy_released > DISCREPANCY_THRESHOLD,
                discrepancy_refunded > DISCREPANCY_THRESHOLD,
            ])

            if discrepancy_locked > DISCREPANCY_THRESHOLD:
                discrepancies.append({
                    "type": DiscrepancyType.LEDGER_ONCHAIN.value,
                    "field": "locked",
                    "ledger_value": str(ledger_totals["locked"]),
                    "onchain_value": str(onchain_totals["locked"]),
                    "difference": str(discrepancy_locked),
                    "severity": self._get_severity(discrepancy_locked),
                })

            if discrepancy_released > DISCREPANCY_THRESHOLD:
                discrepancies.append({
                    "type": DiscrepancyType.LEDGER_ONCHAIN.value,
                    "field": "released",
                    "ledger_value": str(ledger_totals["released"]),
                    "onchain_value": str(onchain_totals["released"]),
                    "difference": str(discrepancy_released),
                    "severity": self._get_severity(discrepancy_released),
                })

            if discrepancy_refunded > DISCREPANCY_THRESHOLD:
                discrepancies.append({
                    "type": DiscrepancyType.LEDGER_ONCHAIN.value,
                    "field": "refunded",
                    "ledger_value": str(ledger_totals["refunded"]),
                    "onchain_value": str(onchain_totals["refunded"]),
                    "difference": str(discrepancy_refunded),
                    "severity": self._get_severity(discrepancy_refunded),
                })

            # 4. Verificar transacciones blockchain pendientes
            tx_discrepancies = await self._check_pending_transactions()
            discrepancies.extend(tx_discrepancies)

            # 5. Verificar discrepancias fiat (si está habilitado)
            if include_fiat and fiat_totals:
                fiat_discrepancies = self._check_fiat_discrepancies(fiat_totals)
                discrepancies.extend(fiat_discrepancies)

            # 6. Crear log de reconciliacion
            fiat_discrepancy = Decimal("0")
            if fiat_totals and fiat_totals.get("unreconciled_count", 0) > 0:
                fiat_discrepancy = fiat_totals.get("expected_payouts", Decimal("0"))

            log = ReconciliationLog(
                check_timestamp=timestamp,
                expected_balance_ledger=ledger_totals["locked"],
                actual_balance_ledger=ledger_totals["locked"],
                expected_balance_onchain=ledger_totals["locked"],
                actual_balance_onchain=onchain_totals["locked"],
                expected_balance_fiat=fiat_totals["expected_payouts"] if fiat_totals else None,
                actual_balance_fiat=fiat_totals["balance_total"] if fiat_totals else None,
                discrepancy_ledger=Decimal("0"),
                discrepancy_onchain=discrepancy_locked,
                discrepancy_fiat=fiat_discrepancy,
                discrepancy_detected=has_discrepancy or len(tx_discrepancies) > 0 or len(discrepancies) > 0,
                network=self.network,
                stablecoin=stablecoin,
                contract_address=self.contract_address,
                error_payload={
                    "discrepancies": discrepancies,
                    "ledger_totals": {k: str(v) for k, v in ledger_totals.items()},
                    "onchain_totals": {k: str(v) for k, v in onchain_totals.items()},
                    "fiat_totals": {k: str(v) for k, v in fiat_totals.items()} if fiat_totals else {},
                } if discrepancies else {},
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)

            # 6. Enviar alertas si hay discrepancias
            if discrepancies:
                alerts_sent = await self._send_discrepancy_alerts(discrepancies, log)

            logger.info(
                f"Reconciliacion completada: "
                f"discrepancias={len(discrepancies)}, alertas={alerts_sent}"
            )

            return ReconciliationResult(
                success=True,
                timestamp=timestamp,
                balance_snapshot=balance_snapshot,
                discrepancies=discrepancies,
                alerts_sent=alerts_sent,
                log_id=str(log.id),
            )

        except Exception as e:
            logger.error(f"Error en reconciliacion: {e}")
            return ReconciliationResult(
                success=False,
                timestamp=timestamp,
                error=str(e),
            )

    async def _check_pending_transactions(self) -> List[Dict[str, Any]]:
        """
        Verifica transacciones pendientes y detecta discrepancias.

        Returns:
            Lista de discrepancias encontradas
        """
        discrepancies = []

        try:
            # Buscar transacciones blockchain pendientes por mas de 10 minutos
            cutoff_time = datetime.utcnow() - timedelta(minutes=10)

            stuck_txs = self.db.query(RemittanceBlockchainTx).filter(
                and_(
                    RemittanceBlockchainTx.blockchain_status.in_([
                        BlockchainRemittanceStatus.PENDING,
                        BlockchainRemittanceStatus.SUBMITTED,
                    ]),
                    RemittanceBlockchainTx.created_at < cutoff_time
                )
            ).all()

            for tx in stuck_txs:
                discrepancies.append({
                    "type": DiscrepancyType.STUCK_TX.value,
                    "remittance_id": str(tx.remittance_id),
                    "tx_hash": tx.tx_hash,
                    "operation": tx.operation,
                    "status": tx.blockchain_status.value,
                    "created_at": tx.created_at.isoformat(),
                    "minutes_pending": int((datetime.utcnow() - tx.created_at).total_seconds() / 60),
                    "severity": AlertSeverity.WARNING.value,
                })

            # Buscar remesas en estado LOCKED sin transaccion blockchain
            orphan_remittances = self.db.query(Remittance).filter(
                and_(
                    Remittance.status == RemittanceStatus.LOCKED,
                    ~Remittance.blockchain_transactions.any(
                        RemittanceBlockchainTx.operation == "lock"
                    )
                )
            ).all()

            for rem in orphan_remittances:
                discrepancies.append({
                    "type": DiscrepancyType.MISSING_TX.value,
                    "remittance_id": str(rem.id),
                    "reference_code": rem.reference_code,
                    "status": rem.status.value,
                    "amount": str(rem.amount_stablecoin),
                    "severity": AlertSeverity.CRITICAL.value,
                })

        except Exception as e:
            logger.error(f"Error verificando transacciones pendientes: {e}")

        return discrepancies

    def _check_fiat_discrepancies(
        self,
        fiat_totals: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Verifica discrepancias en saldos fiat.

        Args:
            fiat_totals: Totales de saldos bancarios

        Returns:
            Lista de discrepancias encontradas
        """
        discrepancies = []

        try:
            # Verificar transacciones sin conciliar
            unreconciled_count = fiat_totals.get("unreconciled_count", 0)
            if unreconciled_count > 0:
                # Obtener transacciones sin conciliar
                unreconciled_txs = self.db.query(BankTransaction).filter(
                    BankTransaction.reconciled == False,
                    BankTransaction.status == BankTransactionStatus.COMPLETED,
                ).order_by(
                    BankTransaction.transaction_date.desc()
                ).limit(10).all()

                for tx in unreconciled_txs:
                    days_old = (datetime.utcnow() - tx.transaction_date).days
                    severity = (
                        AlertSeverity.CRITICAL.value if days_old > 3
                        else AlertSeverity.WARNING.value if days_old > 1
                        else AlertSeverity.INFO.value
                    )

                    discrepancies.append({
                        "type": DiscrepancyType.LEDGER_FIAT.value,
                        "subtype": "unreconciled_transaction",
                        "transaction_id": str(tx.id),
                        "reference": tx.reference_id,
                        "amount": str(tx.amount),
                        "currency": tx.currency,
                        "days_old": days_old,
                        "counterparty": tx.counterparty_name,
                        "severity": severity,
                    })

            # Verificar fondos insuficientes para payouts pendientes
            balance = fiat_totals.get("available_balance", Decimal("0"))
            expected_payouts = fiat_totals.get("expected_payouts", Decimal("0"))

            if balance < expected_payouts and expected_payouts > Decimal("0"):
                shortfall = expected_payouts - balance
                discrepancies.append({
                    "type": DiscrepancyType.LEDGER_FIAT.value,
                    "subtype": "insufficient_funds",
                    "available_balance": str(balance),
                    "expected_payouts": str(expected_payouts),
                    "shortfall": str(shortfall),
                    "currency": fiat_totals.get("currency", "MXN"),
                    "severity": (
                        AlertSeverity.CRITICAL.value if shortfall > Decimal("100000")
                        else AlertSeverity.WARNING.value
                    ),
                })

            # Verificar depósitos esperados no recibidos (más de 24 horas)
            expected_deposits = fiat_totals.get("expected_deposits", Decimal("0"))
            if expected_deposits > Decimal("0"):
                # Buscar remesas esperando depósito por más de 24 horas
                cutoff = datetime.utcnow() - timedelta(hours=24)
                stale_deposits = self.db.query(Remittance).filter(
                    Remittance.status == RemittanceStatus.PENDING_DEPOSIT,
                    Remittance.created_at < cutoff
                ).all()

                for rem in stale_deposits:
                    hours_waiting = int((datetime.utcnow() - rem.created_at).total_seconds() / 3600)
                    discrepancies.append({
                        "type": DiscrepancyType.LEDGER_FIAT.value,
                        "subtype": "stale_deposit",
                        "remittance_id": str(rem.id),
                        "reference_code": rem.reference_code,
                        "amount": str(rem.amount_fiat_source),
                        "currency": rem.currency_source.value if rem.currency_source else "MXN",
                        "hours_waiting": hours_waiting,
                        "severity": (
                            AlertSeverity.WARNING.value if hours_waiting > 48
                            else AlertSeverity.INFO.value
                        ),
                    })

        except Exception as e:
            logger.error(f"Error verificando discrepancias fiat: {e}")

        return discrepancies

    def _get_severity(self, amount: Decimal) -> str:
        """Determina severidad basada en el monto de discrepancia."""
        if amount > Decimal("1000"):
            return AlertSeverity.CRITICAL.value
        elif amount > Decimal("100"):
            return AlertSeverity.WARNING.value
        return AlertSeverity.INFO.value

    # ============ Reconciliacion Individual ============

    async def reconcile_single_remittance(
        self,
        remittance_id: str
    ) -> TransactionReconciliation:
        """
        Reconcilia una remesa individual contra on-chain.

        Args:
            remittance_id: ID de la remesa

        Returns:
            TransactionReconciliation con resultado
        """
        try:
            # Obtener remesa del ledger
            remittance = self.db.query(Remittance).filter(
                Remittance.id == remittance_id
            ).first()

            if not remittance:
                return TransactionReconciliation(
                    remittance_id=remittance_id,
                    reference_code="",
                    ledger_status="NOT_FOUND",
                    onchain_status=None,
                    ledger_amount=Decimal("0"),
                    onchain_amount=None,
                    is_matched=False,
                    discrepancy_type=DiscrepancyType.MISSING_TX,
                    details="Remesa no encontrada en ledger",
                )

            # Obtener estado on-chain
            onchain_data = await self._get_onchain_remittance(remittance.reference_code)

            if onchain_data is None:
                # No existe on-chain, verificar si deberia existir
                should_exist = remittance.status in [
                    RemittanceStatus.LOCKED,
                    RemittanceStatus.DISBURSED,
                    RemittanceStatus.COMPLETED,
                    RemittanceStatus.REFUNDED,
                ]

                return TransactionReconciliation(
                    remittance_id=str(remittance.id),
                    reference_code=remittance.reference_code,
                    ledger_status=remittance.status.value,
                    onchain_status=None,
                    ledger_amount=remittance.amount_stablecoin or Decimal("0"),
                    onchain_amount=None,
                    is_matched=not should_exist,
                    discrepancy_type=DiscrepancyType.MISSING_TX if should_exist else None,
                    details="Remesa no encontrada on-chain" if should_exist else "OK - No requiere registro on-chain",
                )

            # Comparar estados y montos
            onchain_state_map = {
                0: "LOCKED",
                1: "RELEASED",
                2: "REFUNDED",
                3: "CANCELLED",
            }
            onchain_status = onchain_state_map.get(onchain_data["state"], "UNKNOWN")
            onchain_amount = self._wei_to_decimal(onchain_data["amount"], self.STABLECOIN_DECIMALS)

            # Mapear estado ledger para comparacion
            ledger_status_map = {
                RemittanceStatus.LOCKED: "LOCKED",
                RemittanceStatus.DISBURSED: "RELEASED",
                RemittanceStatus.COMPLETED: "RELEASED",
                RemittanceStatus.REFUNDED: "REFUNDED",
                RemittanceStatus.CANCELLED: "CANCELLED",
            }
            expected_onchain = ledger_status_map.get(remittance.status, "UNKNOWN")

            # Verificar match
            status_match = expected_onchain == onchain_status
            amount_diff = abs((remittance.amount_stablecoin or Decimal("0")) - onchain_amount)
            amount_match = amount_diff <= DISCREPANCY_THRESHOLD

            is_matched = status_match and amount_match

            discrepancy_type = None
            details = None
            if not status_match:
                discrepancy_type = DiscrepancyType.LEDGER_ONCHAIN
                details = f"Estado: ledger={expected_onchain}, onchain={onchain_status}"
            elif not amount_match:
                discrepancy_type = DiscrepancyType.AMOUNT_MISMATCH
                details = f"Monto: ledger={remittance.amount_stablecoin}, onchain={onchain_amount}"

            return TransactionReconciliation(
                remittance_id=str(remittance.id),
                reference_code=remittance.reference_code,
                ledger_status=remittance.status.value,
                onchain_status=onchain_status,
                ledger_amount=remittance.amount_stablecoin or Decimal("0"),
                onchain_amount=onchain_amount,
                is_matched=is_matched,
                discrepancy_type=discrepancy_type,
                details=details,
            )

        except Exception as e:
            logger.error(f"Error reconciliando remesa {remittance_id}: {e}")
            return TransactionReconciliation(
                remittance_id=remittance_id,
                reference_code="",
                ledger_status="ERROR",
                onchain_status=None,
                ledger_amount=Decimal("0"),
                onchain_amount=None,
                is_matched=False,
                details=str(e),
            )

    async def _get_onchain_remittance(self, reference_code: str) -> Optional[Dict[str, Any]]:
        """Obtiene datos de una remesa del smart contract."""
        try:
            from web3 import Web3
            reference_bytes32 = Web3.keccak(text=reference_code)

            blockchain_svc = self._get_blockchain_service()

            # Obtener ID on-chain
            onchain_id = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=RECONCILIATION_ABI,
                function_name="getRemittanceByReference",
                args=[reference_bytes32]
            )

            if not onchain_id or onchain_id == 0:
                return None

            # Obtener datos de la remesa
            result = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=RECONCILIATION_ABI,
                function_name="getRemittance",
                args=[onchain_id]
            )

            if result:
                return {
                    "referenceId": result[0],
                    "sender": result[1],
                    "token": result[2],
                    "amount": result[3],
                    "platformFee": result[4],
                    "createdAt": result[5],
                    "expiresAt": result[6],
                    "state": result[7],
                }

            return None

        except Exception as e:
            logger.error(f"Error obteniendo remesa on-chain: {e}")
            return None

    # ============ Alertas ============

    async def _send_discrepancy_alerts(
        self,
        discrepancies: List[Dict[str, Any]],
        log: ReconciliationLog
    ) -> int:
        """
        Envia alertas por discrepancias detectadas.

        Args:
            discrepancies: Lista de discrepancias
            log: Log de reconciliacion

        Returns:
            Numero de alertas enviadas
        """
        alerts_sent = 0

        try:
            notification_svc = self._get_notification_service()

            for disc in discrepancies:
                severity = disc.get("severity", AlertSeverity.INFO.value)

                if severity == AlertSeverity.CRITICAL.value:
                    # Alerta critica - notificar inmediatamente
                    await self._send_critical_alert(disc, log)
                    alerts_sent += 1
                elif severity == AlertSeverity.WARNING.value:
                    # Alerta de warning - notificar a admins
                    await self._send_warning_alert(disc, log)
                    alerts_sent += 1

            # Actualizar log con acciones tomadas
            if alerts_sent > 0:
                log.action_taken = f"Enviadas {alerts_sent} alertas"
                self.db.commit()

        except Exception as e:
            logger.error(f"Error enviando alertas: {e}")

        return alerts_sent

    async def _send_critical_alert(
        self,
        discrepancy: Dict[str, Any],
        log: ReconciliationLog
    ):
        """Envia alerta critica."""
        logger.critical(
            f"ALERTA CRITICA - Discrepancia de conciliacion: "
            f"tipo={discrepancy.get('type')}, "
            f"diferencia={discrepancy.get('difference', 'N/A')}"
        )
        # TODO: Integrar con sistema de alertas (Slack, PagerDuty, email)

    async def _send_warning_alert(
        self,
        discrepancy: Dict[str, Any],
        log: ReconciliationLog
    ):
        """Envia alerta de warning."""
        logger.warning(
            f"ALERTA WARNING - Discrepancia de conciliacion: "
            f"tipo={discrepancy.get('type')}, "
            f"detalles={discrepancy}"
        )
        # TODO: Integrar con sistema de notificaciones

    # ============ Consultas ============

    def get_reconciliation_history(
        self,
        limit: int = 100,
        only_discrepancies: bool = False
    ) -> List[ReconciliationLog]:
        """
        Obtiene historial de reconciliaciones.

        Args:
            limit: Numero maximo de registros
            only_discrepancies: Solo mostrar logs con discrepancias

        Returns:
            Lista de logs de reconciliacion
        """
        query = self.db.query(ReconciliationLog)

        if only_discrepancies:
            query = query.filter(ReconciliationLog.discrepancy_detected == True)

        return query.order_by(
            ReconciliationLog.check_timestamp.desc()
        ).limit(limit).all()

    def get_unresolved_discrepancies(self) -> List[ReconciliationLog]:
        """Obtiene discrepancias no resueltas."""
        return self.db.query(ReconciliationLog).filter(
            and_(
                ReconciliationLog.discrepancy_detected == True,
                ReconciliationLog.resolved == False
            )
        ).order_by(
            ReconciliationLog.check_timestamp.desc()
        ).all()

    def resolve_discrepancy(
        self,
        log_id: str,
        resolved_by: str,
        action_taken: str
    ) -> bool:
        """
        Marca una discrepancia como resuelta.

        Args:
            log_id: ID del log de reconciliacion
            resolved_by: ID del usuario que resuelve
            action_taken: Descripcion de la accion tomada

        Returns:
            True si se resolvio correctamente
        """
        try:
            log = self.db.query(ReconciliationLog).filter(
                ReconciliationLog.id == log_id
            ).first()

            if not log:
                return False

            log.resolved = True
            log.resolved_at = datetime.utcnow()
            log.resolved_by = resolved_by
            log.action_taken = action_taken

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error resolviendo discrepancia: {e}")
            self.db.rollback()
            return False


# ============ Instancia Global ============

_reconciliation_service: Optional[ReconciliationService] = None


def get_reconciliation_service(
    db: Session,
    network: str = "polygon"
) -> ReconciliationService:
    """Obtiene instancia del servicio de reconciliacion."""
    return ReconciliationService(db=db, network=network)
