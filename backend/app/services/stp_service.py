"""
Servicio de integracion con STP (Sistema de Transferencias y Pagos).

STP es la infraestructura de pagos en Mexico que opera SPEI (Sistema de
Pagos Electronicos Interbancarios) para transferencias en tiempo real.

Documentacion: https://stpmex.com/documentacion

Caracteristicas:
- Envio de pagos SPEI en tiempo real (< 30 segundos)
- Consulta de saldos y movimientos
- Webhooks para notificaciones de estado
- Firma digital RSA para autenticacion

Requisitos:
- Cuenta empresarial en STP
- Certificado digital (.pem) para firma
- CLABE concentradora asignada
"""
import logging
import hashlib
import base64
import json
import secrets
import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.config import settings
from app.schemas.stp import (
    STPOperationType,
    STPTransactionStatus,
    STPAccountType,
    STPPaymentType,
    STPOrderRequest,
    STPOrderResponse,
    STPWebhookPayload,
    STPBalanceResponse,
    STPSignatureData,
    STPReconciliationRecord,
    STP_ERROR_CODES,
    STP_RETURN_CAUSES,
    validate_clabe,
    get_bank_from_clabe,
)

logger = logging.getLogger(__name__)


class STPError(Exception):
    """Error base de STP."""
    pass


class STPAPIError(STPError):
    """Error de comunicacion con API STP."""
    def __init__(self, code: int, message: str, response: Optional[dict] = None):
        self.code = code
        self.message = message
        self.response = response
        super().__init__(f"STP Error ({code}): {message}")


class STPSignatureError(STPError):
    """Error de firma digital."""
    pass


class STPInsufficientFundsError(STPError):
    """Saldo insuficiente."""
    pass


class STPAccountError(STPError):
    """Error de cuenta (inexistente, bloqueada, etc.)."""
    pass


@dataclass
class STPConfig:
    """Configuracion del servicio STP."""
    # API
    api_url: str = "https://demo.stpmex.com/speiws/rest"
    api_url_prod: str = "https://prod.stpmex.com/speiws/rest"
    use_production: bool = False

    # Credenciales
    empresa: str = ""  # Codigo de empresa STP
    private_key_path: str = ""  # Ruta al archivo .pem
    private_key_password: Optional[str] = None

    # Cuenta concentradora
    clabe_concentradora: str = ""

    # Configuracion
    timeout_seconds: int = 30
    max_retries: int = 3

    @property
    def base_url(self) -> str:
        return self.api_url_prod if self.use_production else self.api_url


class STPService:
    """
    Servicio principal de STP para operaciones SPEI.

    Uso:
        service = STPService(db, config)

        # Enviar pago
        result = await service.send_spei_payment(
            beneficiary_clabe="012180015678912345",
            beneficiary_name="JUAN PEREZ",
            amount=Decimal("1500.50"),
            concept="PAGO REMESA FRC-123",
            remittance_id="rem_456"
        )

        # Consultar estado
        status = await service.get_order_status(result.tracking_key)
    """

    # Horario SPEI (Lunes a Viernes 6:00 - 17:30 hora Mexico)
    SPEI_START_HOUR = 6
    SPEI_END_HOUR = 17
    SPEI_END_MINUTE = 30

    def __init__(
        self,
        db: Session,
        config: Optional[STPConfig] = None,
    ):
        """
        Inicializa el servicio STP.

        Args:
            db: Sesion de base de datos
            config: Configuracion opcional
        """
        self.db = db
        self.config = config or self._load_config_from_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._private_key = None

    def _load_config_from_settings(self) -> STPConfig:
        """Carga configuracion desde settings."""
        return STPConfig(
            api_url=getattr(settings, 'STP_API_URL', 'https://demo.stpmex.com/speiws/rest'),
            api_url_prod=getattr(settings, 'STP_API_URL_PROD', 'https://prod.stpmex.com/speiws/rest'),
            use_production=getattr(settings, 'STP_USE_PRODUCTION', False),
            empresa=getattr(settings, 'STP_EMPRESA', ''),
            private_key_path=getattr(settings, 'STP_PRIVATE_KEY_PATH', ''),
            private_key_password=getattr(settings, 'STP_PRIVATE_KEY_PASSWORD', None),
            clabe_concentradora=getattr(settings, 'STP_CLABE_CONCENTRADORA', ''),
            timeout_seconds=int(getattr(settings, 'STP_TIMEOUT', 30)),
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtiene cliente HTTP."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        return self._client

    async def close(self):
        """Cierra el cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ============ Firma Digital ============

    def _load_private_key(self):
        """Carga la llave privada RSA para firma."""
        if self._private_key is not None:
            return self._private_key

        key_path = Path(self.config.private_key_path)
        if not key_path.exists():
            raise STPSignatureError(f"Archivo de llave privada no encontrado: {key_path}")

        try:
            with open(key_path, "rb") as key_file:
                password = self.config.private_key_password
                if password:
                    password = password.encode()

                self._private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=password,
                    backend=default_backend()
                )
            return self._private_key

        except Exception as e:
            raise STPSignatureError(f"Error cargando llave privada: {e}")

    def _sign_data(self, data: str) -> str:
        """
        Firma datos con la llave privada RSA.

        Args:
            data: Cadena a firmar

        Returns:
            Firma en base64
        """
        try:
            private_key = self._load_private_key()

            signature = private_key.sign(
                data.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            return base64.b64encode(signature).decode('utf-8')

        except Exception as e:
            raise STPSignatureError(f"Error firmando datos: {e}")

    def _generate_tracking_key(self) -> str:
        """
        Genera clave de rastreo unica.

        Formato: YYYYMMDD + 22 caracteres alfanumericos
        Total: 30 caracteres
        """
        date_part = datetime.now().strftime("%Y%m%d")
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(22))
        return f"{date_part}{random_part}"

    def _generate_reference(self) -> str:
        """Genera referencia numerica de 7 digitos."""
        return str(secrets.randbelow(10000000)).zfill(7)

    # ============ Validaciones ============

    def is_spei_available(self) -> Tuple[bool, str]:
        """
        Verifica si SPEI esta disponible (horario).

        Returns:
            Tuple (disponible, mensaje)
        """
        now = datetime.now()

        # Fines de semana
        if now.weekday() >= 5:
            return (False, "SPEI no disponible en fines de semana")

        # Verificar horario
        if now.hour < self.SPEI_START_HOUR:
            return (False, f"SPEI disponible a partir de las {self.SPEI_START_HOUR}:00")

        if now.hour > self.SPEI_END_HOUR or (
            now.hour == self.SPEI_END_HOUR and now.minute > self.SPEI_END_MINUTE
        ):
            return (False, f"SPEI disponible hasta las {self.SPEI_END_HOUR}:{self.SPEI_END_MINUTE}")

        return (True, "SPEI disponible")

    def validate_beneficiary_account(self, clabe: str) -> Tuple[bool, Optional[str]]:
        """
        Valida cuenta CLABE del beneficiario.

        Returns:
            Tuple (valida, mensaje_error)
        """
        if not clabe:
            return (False, "CLABE requerida")

        if len(clabe) != 18:
            return (False, "CLABE debe tener 18 digitos")

        if not clabe.isdigit():
            return (False, "CLABE debe contener solo digitos")

        if not validate_clabe(clabe):
            return (False, "CLABE invalida (digito verificador incorrecto)")

        return (True, None)

    # ============ Operaciones SPEI ============

    async def send_spei_payment(
        self,
        beneficiary_clabe: str,
        beneficiary_name: str,
        amount: Decimal,
        concept: str,
        remittance_id: Optional[str] = None,
        user_id: Optional[str] = None,
        beneficiary_rfc: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> STPOrderResponse:
        """
        Envia un pago SPEI.

        Args:
            beneficiary_clabe: CLABE del beneficiario (18 digitos)
            beneficiary_name: Nombre del beneficiario
            amount: Monto en MXN
            concept: Concepto del pago
            remittance_id: ID de remesa asociada (opcional)
            user_id: ID del usuario (opcional)
            beneficiary_rfc: RFC del beneficiario (opcional)
            reference: Referencia numerica (opcional, se genera automaticamente)

        Returns:
            STPOrderResponse con el resultado

        Raises:
            STPError: Si hay error en el envio
        """
        # Validaciones previas
        spei_available, msg = self.is_spei_available()
        if not spei_available:
            raise STPError(msg)

        valid_clabe, error_msg = self.validate_beneficiary_account(beneficiary_clabe)
        if not valid_clabe:
            raise STPAccountError(error_msg)

        if amount <= 0:
            raise STPError("Monto debe ser mayor a cero")

        if amount > Decimal("500000"):  # Limite SPEI
            raise STPError("Monto excede limite SPEI de $500,000 MXN")

        # Generar identificadores
        tracking_key = self._generate_tracking_key()
        reference = reference or self._generate_reference()
        internal_id = str(uuid4())

        # Preparar datos para firma
        signature_data = STPSignatureData(
            operation_type="1",  # Pago SPEI
            tracking_key=tracking_key,
            sender_account=self.config.clabe_concentradora,
            beneficiary_account=beneficiary_clabe,
            amount_cents=int(amount * 100),
            sender_name=self.config.empresa,
            payment_type="1",  # Ordinario
            beneficiary_name=beneficiary_name[:40],  # Max 40 chars
            beneficiary_rfc=beneficiary_rfc,
            concept=concept[:40],  # Max 40 chars
            reference=reference,
        )

        # Firmar
        try:
            signature = self._sign_data(signature_data.to_sign_string())
        except STPSignatureError as e:
            logger.error(f"Error firmando orden SPEI: {e}")
            raise

        # Construir payload STP
        payload = {
            "institucionContraparte": beneficiary_clabe[:3],  # Codigo banco
            "empresa": self.config.empresa,
            "fechaOperacion": datetime.now().strftime("%Y%m%d"),
            "folioOrigen": tracking_key,
            "claveRastreo": tracking_key,
            "institucionOperante": "90646",  # STP
            "monto": float(amount),
            "tipoPago": 1,
            "tipoCuentaOrdenante": 40,  # CLABE
            "nombreOrdenante": self.config.empresa,
            "cuentaOrdenante": self.config.clabe_concentradora,
            "rfcCurpOrdenante": "ND",
            "tipoCuentaBeneficiario": 40,  # CLABE
            "nombreBeneficiario": beneficiary_name[:40],
            "cuentaBeneficiario": beneficiary_clabe,
            "rfcCurpBeneficiario": beneficiary_rfc or "ND",
            "emailBeneficiario": "",
            "conceptoPago": concept[:40],
            "referenciaNumerica": int(reference),
            "topologia": "T",
            "medioEntrega": 3,
            "firma": signature,
        }

        logger.info(f"Enviando orden SPEI: {tracking_key} - ${amount} a {beneficiary_clabe[:6]}***")

        # Enviar a STP
        try:
            response = await self._send_order(payload)
        except Exception as e:
            logger.error(f"Error enviando orden SPEI: {e}")
            return STPOrderResponse(
                id=internal_id,
                stp_id=None,
                tracking_key=tracking_key,
                reference=reference,
                status=STPTransactionStatus.FAILED,
                status_description=str(e),
                amount=amount,
                beneficiary_name=beneficiary_name,
                beneficiary_account=beneficiary_clabe,
                beneficiary_bank=get_bank_from_clabe(beneficiary_clabe),
                concept=concept,
                created_at=datetime.utcnow(),
                error_code="CONNECTION_ERROR",
                error_message=str(e),
                remittance_id=remittance_id,
            )

        # Procesar respuesta
        stp_id = response.get("id")
        resultado = response.get("resultado", {})
        descripcion = resultado.get("descripcion", "")

        if stp_id and stp_id > 0:
            # Orden aceptada
            logger.info(f"Orden SPEI aceptada: {tracking_key} - STP ID: {stp_id}")

            return STPOrderResponse(
                id=internal_id,
                stp_id=stp_id,
                tracking_key=tracking_key,
                reference=reference,
                status=STPTransactionStatus.SENT,
                status_description="Orden enviada a STP",
                amount=amount,
                beneficiary_name=beneficiary_name,
                beneficiary_account=beneficiary_clabe,
                beneficiary_bank=get_bank_from_clabe(beneficiary_clabe),
                concept=concept,
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow(),
                remittance_id=remittance_id,
            )
        else:
            # Error
            error_code = resultado.get("id", 99)
            error_msg = STP_ERROR_CODES.get(error_code, descripcion)

            logger.error(f"Orden SPEI rechazada: {tracking_key} - Error {error_code}: {error_msg}")

            return STPOrderResponse(
                id=internal_id,
                stp_id=None,
                tracking_key=tracking_key,
                reference=reference,
                status=STPTransactionStatus.REJECTED,
                status_description=error_msg,
                amount=amount,
                beneficiary_name=beneficiary_name,
                beneficiary_account=beneficiary_clabe,
                beneficiary_bank=get_bank_from_clabe(beneficiary_clabe),
                concept=concept,
                created_at=datetime.utcnow(),
                error_code=str(error_code),
                error_message=error_msg,
                remittance_id=remittance_id,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _send_order(self, payload: dict) -> dict:
        """Envia orden a la API de STP."""
        client = await self._get_client()
        url = f"{self.config.base_url}/ordenPago/registra"

        response = await client.put(url, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise STPAPIError(
                code=response.status_code,
                message=f"Error HTTP: {response.text[:200]}",
                response=None
            )

    async def get_order_status(self, tracking_key: str) -> STPOrderResponse:
        """
        Consulta el estado de una orden SPEI.

        Args:
            tracking_key: Clave de rastreo de la orden

        Returns:
            STPOrderResponse con estado actual
        """
        client = await self._get_client()
        url = f"{self.config.base_url}/ordenPago/consEstatus"

        payload = {
            "empresa": self.config.empresa,
            "claveRastreo": tracking_key,
            "fechaOperacion": datetime.now().strftime("%Y%m%d"),
        }

        try:
            response = await client.post(url, json=payload)
            data = response.json()

            estado = data.get("estado", {})
            estado_id = estado.get("id", -1)

            # Mapear estado STP a nuestro enum
            status_map = {
                0: STPTransactionStatus.LIQUIDATED,
                1: STPTransactionStatus.PROCESSING,
                2: STPTransactionStatus.RETURNED,
                3: STPTransactionStatus.CANCELLED,
                -1: STPTransactionStatus.PENDING,
            }

            status = status_map.get(estado_id, STPTransactionStatus.PROCESSING)
            causa_devolucion = data.get("causaDevolucion")

            if causa_devolucion:
                status = STPTransactionStatus.RETURNED

            return STPOrderResponse(
                id="",
                stp_id=data.get("id"),
                tracking_key=tracking_key,
                reference=str(data.get("referenciaNumerica", "")),
                status=status,
                status_description=estado.get("descripcion"),
                amount=Decimal(str(data.get("monto", 0))),
                beneficiary_name=data.get("nombreBeneficiario", ""),
                beneficiary_account=data.get("cuentaBeneficiario", ""),
                concept=data.get("conceptoPago", ""),
                created_at=datetime.utcnow(),
                liquidated_at=datetime.utcnow() if status == STPTransactionStatus.LIQUIDATED else None,
                error_code=str(causa_devolucion) if causa_devolucion else None,
                error_message=STP_RETURN_CAUSES.get(causa_devolucion) if causa_devolucion else None,
            )

        except Exception as e:
            logger.error(f"Error consultando estado de orden {tracking_key}: {e}")
            raise STPAPIError(code=0, message=str(e))

    async def get_balance(self) -> STPBalanceResponse:
        """
        Consulta el saldo de la cuenta concentradora.

        Returns:
            STPBalanceResponse con saldo actual
        """
        client = await self._get_client()
        url = f"{self.config.base_url}/ordenPago/consSaldo"

        payload = {
            "empresa": self.config.empresa,
            "cuenta": self.config.clabe_concentradora,
        }

        try:
            response = await client.post(url, json=payload)
            data = response.json()

            return STPBalanceResponse(
                account=self.config.clabe_concentradora,
                balance=Decimal(str(data.get("saldo", 0))),
                available_balance=Decimal(str(data.get("saldoDisponible", data.get("saldo", 0)))),
                currency="MXN",
                as_of=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Error consultando saldo: {e}")
            raise STPAPIError(code=0, message=str(e))

    # ============ Webhooks ============

    async def process_webhook(self, payload: STPWebhookPayload) -> Dict[str, Any]:
        """
        Procesa notificacion webhook de STP.

        Args:
            payload: Datos del webhook

        Returns:
            Dict con resultado del procesamiento
        """
        logger.info(
            f"Procesando webhook STP: {payload.clave_rastreo} - "
            f"estado={payload.estado}, monto=${payload.amount_decimal}"
        )

        result = {
            "tracking_key": payload.clave_rastreo,
            "processed": True,
            "action_taken": None,
        }

        if payload.is_liquidated:
            # Pago liquidado exitosamente
            result["action_taken"] = "marked_as_liquidated"
            logger.info(f"Pago liquidado: {payload.clave_rastreo}")

            # TODO: Actualizar remesa asociada a DISBURSED
            # await self._update_remittance_status(payload.clave_rastreo, "DISBURSED")

        elif payload.is_returned:
            # Pago devuelto
            causa = STP_RETURN_CAUSES.get(payload.causa_devolucion, "Motivo desconocido")
            result["action_taken"] = "marked_as_returned"
            result["return_reason"] = causa
            logger.warning(f"Pago devuelto: {payload.clave_rastreo} - {causa}")

            # TODO: Actualizar remesa y notificar
            # await self._handle_returned_payment(payload)

        else:
            # Otro estado - deposito entrante u otro
            result["action_taken"] = "logged"
            logger.info(f"Webhook STP recibido: {payload.clave_rastreo} - estado {payload.estado}")

        return result

    # ============ Conciliacion ============

    async def reconcile_orders(
        self,
        date: Optional[datetime] = None,
    ) -> List[STPReconciliationRecord]:
        """
        Reconcilia ordenes del dia con STP.

        Args:
            date: Fecha a reconciliar (default: hoy)

        Returns:
            Lista de registros de conciliacion
        """
        date = date or datetime.now()
        date_str = date.strftime("%Y%m%d")

        client = await self._get_client()
        url = f"{self.config.base_url}/ordenPago/consOrdenes"

        payload = {
            "empresa": self.config.empresa,
            "fechaOperacion": date_str,
        }

        try:
            response = await client.post(url, json=payload)
            orders = response.json().get("ordenes", [])

            records = []
            for order in orders:
                estado_id = order.get("estado", {}).get("id", -1)
                status_map = {
                    0: STPTransactionStatus.LIQUIDATED,
                    1: STPTransactionStatus.PROCESSING,
                    2: STPTransactionStatus.RETURNED,
                }

                records.append(STPReconciliationRecord(
                    date=date,
                    tracking_key=order.get("claveRastreo", ""),
                    stp_id=order.get("id", 0),
                    amount=Decimal(str(order.get("monto", 0))),
                    status=status_map.get(estado_id, STPTransactionStatus.PROCESSING),
                ))

            logger.info(f"Conciliacion STP: {len(records)} ordenes para {date_str}")
            return records

        except Exception as e:
            logger.error(f"Error en conciliacion STP: {e}")
            raise STPAPIError(code=0, message=str(e))


# ============ Factory ============

_stp_service: Optional[STPService] = None


def get_stp_service(db: Session) -> STPService:
    """Factory para obtener instancia del servicio."""
    return STPService(db=db)


async def cleanup_stp_service():
    """Limpia recursos del servicio."""
    global _stp_service
    if _stp_service:
        await _stp_service.close()
        _stp_service = None
