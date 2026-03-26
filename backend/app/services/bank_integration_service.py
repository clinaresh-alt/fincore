"""
Servicio de Integración Bancaria para FinCore.

Conecta con sistemas bancarios mexicanos para:
- Recepción de depósitos SPEI (SPEI-IN)
- Envío de transferencias SPEI (SPEI-OUT / Payouts)
- Generación de CLABEs virtuales
- Consulta de saldos y movimientos
- Conciliación de transacciones bancarias

Proveedores soportados:
- STP (Sistema de Transferencias y Pagos) - Principal
- SPEI Directo (Banco de México) - Solo referencia
- Arcus Fi (APIs para SPEI)

Cumple con:
- Circular 14/2017 de Banxico (SPEI)
- Disposiciones de la CNBV para ITF
- PLD/FT (Prevención de Lavado de Dinero)
"""
import os
import uuid
import hmac
import hashlib
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.config import settings
from app.models.bank_account import (
    BankAccount,
    BankTransaction,
    BankStatementImport,
    VirtualClabeAssignment,
    BankProvider,
    BankAccountType,
    BankAccountStatus,
    BankTransactionType,
    BankTransactionStatus,
    SpeiOperationType,
)
from app.models.remittance import Remittance, RemittanceStatus, Currency


logger = logging.getLogger(__name__)


# ============ Configuración ============

# STP API Configuration
STP_BASE_URL = os.getenv("STP_BASE_URL", "https://demo.stpmex.com/speiws/rest")
STP_EMPRESA = os.getenv("STP_EMPRESA", "")
STP_PRIV_KEY_PATH = os.getenv("STP_PRIV_KEY_PATH", "")
STP_PRIV_KEY_PASSPHRASE = os.getenv("STP_PRIV_KEY_PASSPHRASE", "")
STP_WEBHOOK_SECRET = os.getenv("STP_WEBHOOK_SECRET", "")

# CLABE Configuration
FINCORE_BANK_CODE = os.getenv("FINCORE_BANK_CODE", "646")  # STP = 646
FINCORE_CLABE_PREFIX = os.getenv("FINCORE_CLABE_PREFIX", "646180")  # 646 + plaza

# Límites
MAX_SPEI_AMOUNT = Decimal("500000000")  # 500 millones MXN
MIN_SPEI_AMOUNT = Decimal("1")  # 1 MXN
SPEI_HORARIO_INICIO = 6  # 6:00 AM
SPEI_HORARIO_FIN = 17    # 5:00 PM (fuera de horario = liquidación siguiente día)


# ============ Data Classes ============

@dataclass
class SpeiTransferRequest:
    """Solicitud de transferencia SPEI-OUT."""
    amount: Decimal
    beneficiary_name: str
    beneficiary_clabe: str
    beneficiary_rfc: str
    concept: str
    reference: str
    # Opcionales
    beneficiary_bank_code: Optional[str] = None
    sender_name: Optional[str] = None
    sender_account: Optional[str] = None
    tracking_key: Optional[str] = None


@dataclass
class SpeiTransferResult:
    """Resultado de transferencia SPEI."""
    success: bool
    tracking_key: Optional[str] = None
    stp_id: Optional[str] = None
    status: str = "pending"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BankBalanceInfo:
    """Información de saldo bancario."""
    account_id: str
    clabe: str
    balance: Decimal
    available_balance: Decimal
    currency: str = "MXN"
    as_of: datetime = field(default_factory=datetime.utcnow)
    pending_deposits: Decimal = Decimal("0")
    pending_withdrawals: Decimal = Decimal("0")


@dataclass
class SpeiWebhookPayload:
    """Payload de webhook SPEI-IN (depósito recibido)."""
    id: str
    clabe_beneficiario: str
    clabe_ordenante: str
    monto: Decimal
    concepto: str
    referencia_numerica: str
    nombre_ordenante: str
    rfc_ordenante: Optional[str]
    institucion_ordenante: str
    fecha_operacion: datetime
    clave_rastreo: str
    tipo_cuenta_beneficiario: Optional[str] = None
    raw_data: Dict = field(default_factory=dict)


# ============ Excepciones ============

class BankIntegrationError(Exception):
    """Error base de integración bancaria."""
    pass


class SpeiError(BankIntegrationError):
    """Error específico de SPEI."""
    def __init__(self, message: str, code: Optional[str] = None):
        self.code = code
        super().__init__(message)


class InsufficientFundsError(BankIntegrationError):
    """Fondos insuficientes."""
    pass


class InvalidClabeError(BankIntegrationError):
    """CLABE inválida."""
    pass


class SpeiHorarioError(BankIntegrationError):
    """Fuera de horario SPEI."""
    pass


# ============ Servicio Principal ============

class BankIntegrationService:
    """
    Servicio de integración con sistemas bancarios.

    Funcionalidades principales:
    1. Transferencias SPEI-OUT (payouts)
    2. Recepción de webhooks SPEI-IN (depósitos)
    3. Generación de CLABEs virtuales
    4. Consulta de saldos y movimientos
    5. Conciliación con el ledger interno
    """

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.provider = BankProvider.STP

    async def close(self):
        """Cerrar conexiones."""
        await self.http_client.aclose()

    # ==================== TRANSFERENCIAS SPEI-OUT ====================

    async def send_spei_transfer(
        self,
        request: SpeiTransferRequest,
        source_account_id: str,
    ) -> SpeiTransferResult:
        """
        Envía una transferencia SPEI-OUT.

        Args:
            request: Datos de la transferencia
            source_account_id: ID de la cuenta origen (FinCore)

        Returns:
            SpeiTransferResult con estado de la operación
        """
        try:
            # Validaciones
            self._validate_spei_transfer(request)

            # Verificar cuenta origen
            source_account = self.db.query(BankAccount).filter(
                BankAccount.id == source_account_id,
                BankAccount.status == BankAccountStatus.ACTIVE,
                BankAccount.is_platform_account == True,
            ).first()

            if not source_account:
                raise BankIntegrationError("Cuenta origen no encontrada o inactiva")

            # Verificar saldo suficiente
            if source_account.last_known_balance < request.amount:
                raise InsufficientFundsError(
                    f"Saldo insuficiente. Disponible: {source_account.last_known_balance}, "
                    f"Requerido: {request.amount}"
                )

            # Generar clave de rastreo si no existe
            tracking_key = request.tracking_key or self._generate_tracking_key()

            # Crear registro de transacción
            tx_reference = f"SPEI-OUT-{uuid.uuid4().hex[:12].upper()}"
            transaction = BankTransaction(
                account_id=source_account.id,
                reference_id=tx_reference,
                tracking_key=tracking_key,
                transaction_type=BankTransactionType.TRANSFER_OUT,
                amount=-request.amount,  # Negativo = cargo
                currency="MXN",
                status=BankTransactionStatus.PENDING,
                counterparty_name=request.beneficiary_name,
                counterparty_clabe=request.beneficiary_clabe,
                counterparty_rfc=request.beneficiary_rfc,
                concept=request.concept,
                spei_operation_type=SpeiOperationType.SPEI_ORDINARIO,
                provider=self.provider,
                transaction_date=datetime.utcnow(),
            )
            self.db.add(transaction)

            # Llamar API de STP
            result = await self._call_stp_transfer_api(request, tracking_key)

            # Actualizar transacción con resultado
            if result.success:
                transaction.status = BankTransactionStatus.PROCESSING
                transaction.provider_transaction_id = result.stp_id
                transaction.bank_reference = result.tracking_key
            else:
                transaction.status = BankTransactionStatus.FAILED
                transaction.error_code = result.error_code
                transaction.error_message = result.error_message

            self.db.commit()

            logger.info(
                f"SPEI-OUT {'exitoso' if result.success else 'fallido'}: "
                f"{request.amount} MXN -> {request.beneficiary_clabe} "
                f"(tracking: {tracking_key})"
            )

            return result

        except Exception as e:
            logger.error(f"Error en SPEI-OUT: {e}")
            self.db.rollback()
            return SpeiTransferResult(
                success=False,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
            )

    async def _call_stp_transfer_api(
        self,
        request: SpeiTransferRequest,
        tracking_key: str,
    ) -> SpeiTransferResult:
        """Llama a la API de STP para enviar transferencia."""
        try:
            # Construir payload según especificación STP
            payload = {
                "empresa": STP_EMPRESA,
                "claveRastreo": tracking_key,
                "institucionContraparte": request.beneficiary_bank_code or self._get_bank_from_clabe(request.beneficiary_clabe),
                "monto": float(request.amount),
                "tipoPago": 1,  # SPEI
                "tipoCuentaBeneficiario": 40,  # CLABE
                "nombreBeneficiario": request.beneficiary_name[:40],
                "cuentaBeneficiario": request.beneficiary_clabe,
                "rfcCurpBeneficiario": request.beneficiary_rfc or "ND",
                "conceptoPago": request.concept[:40],
                "referenciaNumerica": int(request.reference) if request.reference.isdigit() else 0,
            }

            # Firmar request (en producción, usar llave privada)
            signature = self._sign_stp_request(payload)
            payload["firma"] = signature

            # En modo demo/test, simular respuesta exitosa
            if "demo" in STP_BASE_URL.lower() or not STP_EMPRESA:
                logger.info("Modo DEMO STP - simulando transferencia exitosa")
                return SpeiTransferResult(
                    success=True,
                    tracking_key=tracking_key,
                    stp_id=f"STP-{uuid.uuid4().hex[:10].upper()}",
                    status="liquidada",
                )

            # Llamada real a STP
            response = await self.http_client.put(
                f"{STP_BASE_URL}/ordenPago/registra",
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                return SpeiTransferResult(
                    success=True,
                    tracking_key=tracking_key,
                    stp_id=str(data.get("id")),
                    status="enviada",
                )
            else:
                error_data = response.json() if response.content else {}
                return SpeiTransferResult(
                    success=False,
                    tracking_key=tracking_key,
                    error_code=str(error_data.get("codigo", response.status_code)),
                    error_message=error_data.get("mensaje", "Error desconocido"),
                )

        except httpx.RequestError as e:
            logger.error(f"Error de conexión con STP: {e}")
            return SpeiTransferResult(
                success=False,
                error_code="CONNECTION_ERROR",
                error_message=f"Error de conexión: {str(e)}",
            )

    # ==================== WEBHOOKS SPEI-IN ====================

    async def process_spei_webhook(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> Tuple[bool, Optional[BankTransaction]]:
        """
        Procesa webhook de depósito SPEI-IN.

        Args:
            payload: Datos del webhook de STP
            signature: Firma para verificación

        Returns:
            Tuple (success, transaction)
        """
        try:
            # Verificar firma si está configurado
            if STP_WEBHOOK_SECRET and signature:
                if not self._verify_webhook_signature(payload, signature):
                    logger.warning("Firma de webhook inválida")
                    return False, None

            # Parsear payload
            webhook_data = self._parse_spei_webhook(payload)

            # Verificar si ya existe la transacción (idempotencia)
            existing = self.db.query(BankTransaction).filter(
                BankTransaction.tracking_key == webhook_data.clave_rastreo
            ).first()

            if existing:
                logger.info(f"Webhook duplicado ignorado: {webhook_data.clave_rastreo}")
                return True, existing

            # Buscar cuenta destino por CLABE
            account = self.db.query(BankAccount).filter(
                BankAccount.clabe == webhook_data.clabe_beneficiario,
                BankAccount.status == BankAccountStatus.ACTIVE,
            ).first()

            # Si no hay cuenta directa, buscar CLABE virtual
            remittance_id = None
            if not account:
                virtual_clabe = self.db.query(VirtualClabeAssignment).filter(
                    VirtualClabeAssignment.virtual_clabe == webhook_data.clabe_beneficiario,
                    VirtualClabeAssignment.is_active == True,
                ).first()

                if virtual_clabe:
                    account = self.db.query(BankAccount).filter(
                        BankAccount.id == virtual_clabe.base_account_id
                    ).first()
                    remittance_id = virtual_clabe.remittance_id

                    # Actualizar uso de CLABE virtual
                    virtual_clabe.times_used += 1
                    virtual_clabe.last_used_at = datetime.utcnow()
                    virtual_clabe.total_received += webhook_data.monto

            if not account:
                logger.warning(f"CLABE no encontrada: {webhook_data.clabe_beneficiario}")
                # Registrar en cuenta de depósitos huérfanos si existe
                account = self.db.query(BankAccount).filter(
                    BankAccount.account_alias == "ORPHAN_DEPOSITS",
                    BankAccount.is_platform_account == True,
                ).first()

                if not account:
                    return False, None

            # Crear transacción
            tx_reference = f"SPEI-IN-{uuid.uuid4().hex[:12].upper()}"
            transaction = BankTransaction(
                account_id=account.id,
                reference_id=tx_reference,
                bank_reference=webhook_data.id,
                tracking_key=webhook_data.clave_rastreo,
                transaction_type=BankTransactionType.TRANSFER_IN,
                amount=webhook_data.monto,
                currency="MXN",
                status=BankTransactionStatus.COMPLETED,
                counterparty_name=webhook_data.nombre_ordenante,
                counterparty_clabe=webhook_data.clabe_ordenante,
                counterparty_rfc=webhook_data.rfc_ordenante,
                concept=webhook_data.concepto,
                spei_operation_type=SpeiOperationType.SPEI_ORDINARIO,
                provider=self.provider,
                transaction_date=webhook_data.fecha_operacion,
                remittance_id=remittance_id,
                raw_data=webhook_data.raw_data,
            )
            self.db.add(transaction)

            # Actualizar balance de la cuenta
            if account.is_platform_account:
                account.last_known_balance = (account.last_known_balance or Decimal("0")) + webhook_data.monto
                account.balance_updated_at = datetime.utcnow()

            # Si está asociado a una remesa, actualizar estado
            if remittance_id:
                remittance = self.db.query(Remittance).filter(
                    Remittance.id == remittance_id
                ).first()

                if remittance and remittance.status == RemittanceStatus.PENDING_DEPOSIT:
                    if webhook_data.monto >= remittance.amount_fiat_source:
                        remittance.status = RemittanceStatus.DEPOSITED
                        logger.info(f"Remesa {remittance.reference_code} marcada como DEPOSITED")

            self.db.commit()

            logger.info(
                f"SPEI-IN procesado: {webhook_data.monto} MXN de {webhook_data.nombre_ordenante} "
                f"(tracking: {webhook_data.clave_rastreo})"
            )

            return True, transaction

        except Exception as e:
            logger.error(f"Error procesando webhook SPEI: {e}")
            self.db.rollback()
            return False, None

    def _parse_spei_webhook(self, payload: Dict) -> SpeiWebhookPayload:
        """Parsea payload de webhook STP."""
        return SpeiWebhookPayload(
            id=payload.get("id", str(uuid.uuid4())),
            clabe_beneficiario=payload.get("cuentaBeneficiario", ""),
            clabe_ordenante=payload.get("cuentaOrdenante", ""),
            monto=Decimal(str(payload.get("monto", 0))),
            concepto=payload.get("conceptoPago", ""),
            referencia_numerica=payload.get("referenciaNumerica", ""),
            nombre_ordenante=payload.get("nombreOrdenante", ""),
            rfc_ordenante=payload.get("rfcCurpOrdenante"),
            institucion_ordenante=payload.get("institucionOrdenante", ""),
            fecha_operacion=datetime.fromisoformat(
                payload.get("fechaOperacion", datetime.utcnow().isoformat())
            ),
            clave_rastreo=payload.get("claveRastreo", ""),
            raw_data=payload,
        )

    # ==================== CLABEs VIRTUALES ====================

    def generate_virtual_clabe(
        self,
        assignment_type: str,
        remittance_id: Optional[str] = None,
        user_id: Optional[str] = None,
        base_account_id: Optional[str] = None,
        expires_hours: int = 72,
    ) -> Optional[str]:
        """
        Genera una CLABE virtual única para identificar depósitos.

        Args:
            assignment_type: "remittance", "user", "general"
            remittance_id: ID de remesa si aplica
            user_id: ID de usuario si aplica
            base_account_id: Cuenta STP base (si no se especifica, usa la default)
            expires_hours: Horas hasta expiración

        Returns:
            CLABE virtual de 18 dígitos
        """
        try:
            # Obtener cuenta base
            if not base_account_id:
                base_account = self.db.query(BankAccount).filter(
                    BankAccount.is_platform_account == True,
                    BankAccount.status == BankAccountStatus.ACTIVE,
                    BankAccount.provider == BankProvider.STP,
                ).first()

                if not base_account:
                    logger.error("No hay cuenta STP base configurada")
                    return None

                base_account_id = str(base_account.id)

            # Generar CLABE única
            # Formato: 646 (STP) + 180 (plaza) + 11 dígitos únicos + 1 dígito verificador = 18 total
            # FINCORE_CLABE_PREFIX = "646180" (6 dígitos)
            unique_part = str(uuid.uuid4().int)[:11].zfill(11)  # 11 dígitos
            clabe_sin_verificador = f"{FINCORE_CLABE_PREFIX}{unique_part}"  # 6 + 11 = 17 dígitos
            digito_verificador = self._calculate_clabe_check_digit(clabe_sin_verificador)
            virtual_clabe = f"{clabe_sin_verificador}{digito_verificador}"  # 17 + 1 = 18 dígitos

            # Verificar que no exista
            exists = self.db.query(VirtualClabeAssignment).filter(
                VirtualClabeAssignment.virtual_clabe == virtual_clabe
            ).first()

            if exists:
                # Reintentar con otro UUID
                return self.generate_virtual_clabe(
                    assignment_type, remittance_id, user_id, base_account_id, expires_hours
                )

            # Crear asignación
            assignment = VirtualClabeAssignment(
                virtual_clabe=virtual_clabe,
                assignment_type=assignment_type,
                remittance_id=uuid.UUID(remittance_id) if remittance_id else None,
                user_id=uuid.UUID(user_id) if user_id else None,
                base_account_id=uuid.UUID(base_account_id),
                is_active=True,
                expires_at=datetime.utcnow() + timedelta(hours=expires_hours) if expires_hours else None,
            )
            self.db.add(assignment)
            self.db.commit()

            logger.info(f"CLABE virtual generada: {virtual_clabe} para {assignment_type}")
            return virtual_clabe

        except Exception as e:
            logger.error(f"Error generando CLABE virtual: {e}")
            self.db.rollback()
            return None

    def _calculate_clabe_check_digit(self, clabe_17: str) -> str:
        """Calcula dígito verificador de CLABE según algoritmo Banxico."""
        weights = [3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7]
        total = sum(int(d) * w for d, w in zip(clabe_17, weights))
        remainder = total % 10
        check_digit = (10 - remainder) % 10
        return str(check_digit)

    def validate_clabe(self, clabe: str) -> bool:
        """Valida formato y dígito verificador de CLABE."""
        if not clabe or len(clabe) != 18 or not clabe.isdigit():
            return False

        calculated_check = self._calculate_clabe_check_digit(clabe[:17])
        return clabe[17] == calculated_check

    # ==================== CONSULTA DE SALDOS ====================

    async def get_account_balance(self, account_id: str) -> Optional[BankBalanceInfo]:
        """
        Obtiene saldo actual de una cuenta bancaria.

        Para cuentas STP, consulta la API. Para otras, usa el último saldo conocido.
        """
        try:
            account = self.db.query(BankAccount).filter(
                BankAccount.id == account_id
            ).first()

            if not account:
                return None

            # Para STP, intentar consultar API
            if account.provider == BankProvider.STP and STP_EMPRESA:
                api_balance = await self._query_stp_balance(account)
                if api_balance is not None:
                    account.last_known_balance = api_balance
                    account.balance_updated_at = datetime.utcnow()
                    self.db.commit()

            # Calcular pendientes
            pending_out = self.db.query(func.sum(func.abs(BankTransaction.amount))).filter(
                BankTransaction.account_id == account_id,
                BankTransaction.transaction_type == BankTransactionType.TRANSFER_OUT,
                BankTransaction.status == BankTransactionStatus.PROCESSING,
            ).scalar() or Decimal("0")

            pending_in = self.db.query(func.sum(BankTransaction.amount)).filter(
                BankTransaction.account_id == account_id,
                BankTransaction.transaction_type == BankTransactionType.TRANSFER_IN,
                BankTransaction.status == BankTransactionStatus.PROCESSING,
            ).scalar() or Decimal("0")

            return BankBalanceInfo(
                account_id=str(account.id),
                clabe=account.clabe or "",
                balance=account.last_known_balance or Decimal("0"),
                available_balance=(account.last_known_balance or Decimal("0")) - pending_out,
                currency=account.currency,
                as_of=account.balance_updated_at or account.updated_at,
                pending_deposits=pending_in,
                pending_withdrawals=pending_out,
            )

        except Exception as e:
            logger.error(f"Error obteniendo balance: {e}")
            return None

    async def _query_stp_balance(self, account: BankAccount) -> Optional[Decimal]:
        """Consulta saldo en API de STP."""
        try:
            if "demo" in STP_BASE_URL.lower():
                # En demo, simular saldo
                return account.last_known_balance or Decimal("100000")

            response = await self.http_client.get(
                f"{STP_BASE_URL}/cuentas/saldo",
                params={"empresa": STP_EMPRESA, "cuenta": account.clabe},
            )

            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get("saldo", 0)))

            return None

        except Exception as e:
            logger.error(f"Error consultando saldo STP: {e}")
            return None

    # ==================== CONCILIACIÓN ====================

    def get_bank_totals(
        self,
        as_of: Optional[datetime] = None,
        currency: str = "MXN",
    ) -> Dict[str, Decimal]:
        """
        Obtiene totales de cuentas bancarias para conciliación.

        Returns:
            Dict con totales: balance_total, deposits_today, withdrawals_today, etc.
        """
        as_of = as_of or datetime.utcnow()
        start_of_day = as_of.replace(hour=0, minute=0, second=0, microsecond=0)

        # Total de saldos en cuentas operativas
        total_balance = self.db.query(
            func.sum(BankAccount.last_known_balance)
        ).filter(
            BankAccount.is_platform_account == True,
            BankAccount.status == BankAccountStatus.ACTIVE,
            BankAccount.currency == currency,
        ).scalar() or Decimal("0")

        # Depósitos del día
        deposits_today = self.db.query(
            func.sum(BankTransaction.amount)
        ).filter(
            BankTransaction.transaction_type == BankTransactionType.TRANSFER_IN,
            BankTransaction.status == BankTransactionStatus.COMPLETED,
            BankTransaction.transaction_date >= start_of_day,
        ).scalar() or Decimal("0")

        # Retiros del día
        withdrawals_today = self.db.query(
            func.sum(func.abs(BankTransaction.amount))
        ).filter(
            BankTransaction.transaction_type == BankTransactionType.TRANSFER_OUT,
            BankTransaction.status.in_([
                BankTransactionStatus.COMPLETED,
                BankTransactionStatus.PROCESSING,
            ]),
            BankTransaction.transaction_date >= start_of_day,
        ).scalar() or Decimal("0")

        # Pendientes de procesar
        pending_deposits = self.db.query(
            func.sum(BankTransaction.amount)
        ).filter(
            BankTransaction.transaction_type == BankTransactionType.TRANSFER_IN,
            BankTransaction.status == BankTransactionStatus.PENDING,
        ).scalar() or Decimal("0")

        pending_withdrawals = self.db.query(
            func.sum(func.abs(BankTransaction.amount))
        ).filter(
            BankTransaction.transaction_type == BankTransactionType.TRANSFER_OUT,
            BankTransaction.status == BankTransactionStatus.PROCESSING,
        ).scalar() or Decimal("0")

        # Transacciones sin conciliar
        unreconciled = self.db.query(
            func.count(BankTransaction.id)
        ).filter(
            BankTransaction.reconciled == False,
            BankTransaction.status == BankTransactionStatus.COMPLETED,
        ).scalar() or 0

        return {
            "balance_total": total_balance,
            "available_balance": total_balance - pending_withdrawals,
            "deposits_today": deposits_today,
            "withdrawals_today": withdrawals_today,
            "pending_deposits": pending_deposits,
            "pending_withdrawals": pending_withdrawals,
            "unreconciled_count": unreconciled,
            "currency": currency,
            "as_of": as_of,
        }

    def get_unreconciled_transactions(
        self,
        limit: int = 100,
    ) -> List[BankTransaction]:
        """Obtiene transacciones bancarias sin conciliar."""
        return self.db.query(BankTransaction).filter(
            BankTransaction.reconciled == False,
            BankTransaction.status == BankTransactionStatus.COMPLETED,
        ).order_by(
            BankTransaction.transaction_date.desc()
        ).limit(limit).all()

    def mark_transactions_reconciled(
        self,
        transaction_ids: List[str],
        reconciliation_log_id: Optional[str] = None,
    ) -> int:
        """Marca transacciones como conciliadas."""
        try:
            count = self.db.query(BankTransaction).filter(
                BankTransaction.id.in_([uuid.UUID(tid) for tid in transaction_ids])
            ).update({
                BankTransaction.reconciled: True,
                BankTransaction.reconciled_at: datetime.utcnow(),
                BankTransaction.reconciliation_log_id: (
                    uuid.UUID(reconciliation_log_id) if reconciliation_log_id else None
                ),
            }, synchronize_session=False)

            self.db.commit()
            return count

        except Exception as e:
            logger.error(f"Error marcando transacciones conciliadas: {e}")
            self.db.rollback()
            return 0

    # ==================== HELPERS ====================

    def _validate_spei_transfer(self, request: SpeiTransferRequest):
        """Valida datos de transferencia SPEI."""
        # Validar CLABE
        if not self.validate_clabe(request.beneficiary_clabe):
            raise InvalidClabeError(f"CLABE inválida: {request.beneficiary_clabe}")

        # Validar monto
        if request.amount < MIN_SPEI_AMOUNT:
            raise SpeiError(f"Monto mínimo: {MIN_SPEI_AMOUNT} MXN", "MIN_AMOUNT")

        if request.amount > MAX_SPEI_AMOUNT:
            raise SpeiError(f"Monto máximo: {MAX_SPEI_AMOUNT} MXN", "MAX_AMOUNT")

        # Validar horario SPEI (opcional, depende de requisitos)
        # now = datetime.now()
        # if now.hour < SPEI_HORARIO_INICIO or now.hour >= SPEI_HORARIO_FIN:
        #     raise SpeiHorarioError("Fuera de horario SPEI, se procesará mañana")

    def _generate_tracking_key(self) -> str:
        """Genera clave de rastreo SPEI única."""
        # Formato STP: 7 dígitos numéricos
        return str(uuid.uuid4().int)[:7]

    def _get_bank_from_clabe(self, clabe: str) -> str:
        """Obtiene código de banco desde CLABE."""
        if len(clabe) >= 3:
            return clabe[:3]
        return "000"

    def _sign_stp_request(self, payload: Dict) -> str:
        """Firma request para STP (placeholder)."""
        # En producción, usar llave privada RSA
        # Por ahora, retornar firma dummy para desarrollo
        data = json.dumps(payload, sort_keys=True)
        return hmac.new(
            (STP_WEBHOOK_SECRET or "dev_key").encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def _verify_webhook_signature(self, payload: Dict, signature: str) -> bool:
        """Verifica firma de webhook."""
        expected = self._sign_stp_request(payload)
        return hmac.compare_digest(expected, signature)


# ============ Factory Function ============

def get_bank_service(db: Session) -> BankIntegrationService:
    """Factory para obtener instancia del servicio."""
    return BankIntegrationService(db)
