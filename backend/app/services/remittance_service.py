"""
Servicio de Remesas Blockchain para FinCore.

Gestiona el flujo completo de remesas transfronterizas:
1. Creacion y validacion de remesas
2. Bloqueo de fondos en escrow (smart contract)
3. Liberacion tras confirmacion de entrega fiat
4. Reembolsos automaticos por time-lock (48h)
5. Conciliacion con ledger interno

Integra con:
- FinCoreRemittance.sol (smart contract)
- blockchain_service.py (transacciones web3)
- KYC/AML services (compliance)
"""
import logging
import secrets
import string
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from web3 import Web3

from app.models.remittance import (
    Remittance,
    RemittanceBlockchainTx,
    ReconciliationLog,
    RemittanceLimit,
    ExchangeRateHistory,
    RemittanceStatus,
    BlockchainRemittanceStatus,
    PaymentMethod,
    DisbursementMethod,
    Currency,
    Stablecoin,
)
from app.models.user import User
from app.models.compliance import KYCProfile, KYCLevel
from app.services.blockchain_service import BlockchainService, TransactionResult
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# ============ Configuracion de Contratos ============

# Direcciones de contratos (de variables de entorno)
REMITTANCE_CONTRACT_ADDRESS = os.getenv(
    "REMITTANCE_CONTRACT_ADDRESS",
    "0x0000000000000000000000000000000000000000"  # Placeholder
)

# Direcciones de stablecoins por red (Polygon)
STABLECOIN_ADDRESSES = {
    "polygon": {
        Stablecoin.USDC: os.getenv("USDC_ADDRESS", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"),
        Stablecoin.USDT: os.getenv("USDT_ADDRESS", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"),
    },
    "polygon_amoy": {
        Stablecoin.USDC: os.getenv("USDC_TESTNET_ADDRESS", "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582"),
        Stablecoin.USDT: os.getenv("USDT_TESTNET_ADDRESS", "0x1234567890123456789012345678901234567890"),
    }
}


def _load_contract_abi() -> List[Dict]:
    """Carga el ABI del contrato FinCoreRemittance."""
    # Buscar el archivo ABI en varias ubicaciones posibles
    possible_paths = [
        Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "src" / "FinCoreRemittance.sol" / "FinCoreRemittance.json",
        Path(__file__).parent.parent.parent.parent / "contracts" / "artifacts" / "src" / "FinCoreRemittance.sol" / "FinCoreRemittance.json",
        Path(os.getenv("CONTRACT_ABI_PATH", "")) / "FinCoreRemittance.json",
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, "r") as f:
                artifact = json.load(f)
                return artifact.get("abi", [])

    # ABI minimo para funciones principales si no se encuentra el archivo
    logger.warning("No se encontro ABI completo, usando ABI minimo")
    return _get_minimal_abi()


def _get_minimal_abi() -> List[Dict]:
    """ABI minimo para las funciones principales del contrato."""
    return [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "referenceId", "type": "bytes32"},
                {"internalType": "address", "name": "token", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}
            ],
            "name": "lockFunds",
            "outputs": [{"internalType": "uint256", "name": "remittanceId", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "remittanceId", "type": "uint256"}],
            "name": "releaseFunds",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "remittanceId", "type": "uint256"}],
            "name": "refund",
            "outputs": [],
            "stateMutability": "nonpayable",
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
            "name": "canRefund",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]


# Cargar ABI al iniciar
REMITTANCE_CONTRACT_ABI = _load_contract_abi()


@dataclass
class RemittanceQuote:
    """Cotizacion de remesa antes de confirmar."""
    amount_source: Decimal
    currency_source: Currency
    amount_destination: Decimal
    currency_destination: Currency
    amount_stablecoin: Decimal
    exchange_rate_source_usd: Decimal
    exchange_rate_usd_destination: Decimal
    platform_fee: Decimal
    network_fee: Decimal
    total_fees: Decimal
    total_to_pay: Decimal
    estimated_delivery: datetime
    quote_expires_at: datetime
    quote_id: str


@dataclass
class RemittanceResult:
    """Resultado de operacion de remesa."""
    success: bool
    remittance_id: Optional[str] = None
    reference_code: Optional[str] = None
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    status: Optional[RemittanceStatus] = None


class RemittanceService:
    """
    Servicio principal de remesas.

    Responsabilidades:
    - Validar limites por KYC
    - Calcular tasas de cambio y fees
    - Orquestar flujo de escrow blockchain
    - Gestionar estados y notificaciones
    """

    # Configuracion
    PLATFORM_FEE_PERCENT = Decimal("0.015")  # 1.5%
    MIN_AMOUNT_USD = Decimal("10")
    MAX_AMOUNT_USD = Decimal("10000")
    QUOTE_VALIDITY_MINUTES = 15
    ESCROW_TIMELOCK_HOURS = 48
    STABLECOIN_DECIMALS = 6  # USDC/USDT tienen 6 decimales

    def __init__(self, db: Session, network: str = "polygon"):
        self.db = db
        self.network = network
        self.blockchain_service: Optional[BlockchainService] = None
        self.contract_address = REMITTANCE_CONTRACT_ADDRESS
        self.contract_abi = REMITTANCE_CONTRACT_ABI

    def _get_blockchain_service(self) -> BlockchainService:
        """Lazy initialization del blockchain service."""
        if self.blockchain_service is None:
            from app.models.blockchain import BlockchainNetwork
            network_enum = BlockchainNetwork.POLYGON if self.network == "polygon" else BlockchainNetwork.POLYGON_AMOY
            self.blockchain_service = BlockchainService(network=network_enum)
        return self.blockchain_service

    def _reference_to_bytes32(self, reference_code: str) -> bytes:
        """Convierte un codigo de referencia a bytes32 para el smart contract."""
        # Usar keccak256 del reference code para obtener bytes32
        return Web3.keccak(text=reference_code)

    def _get_stablecoin_address(self, stablecoin: Stablecoin) -> str:
        """Obtiene la direccion del stablecoin para la red actual."""
        network_key = "polygon_amoy" if "amoy" in self.network.lower() else "polygon"
        addresses = STABLECOIN_ADDRESSES.get(network_key, {})
        return addresses.get(stablecoin, addresses.get(Stablecoin.USDC, ""))

    def _amount_to_wei(self, amount: Decimal, decimals: int = 6) -> int:
        """Convierte monto decimal a unidades del token (wei)."""
        return int(amount * Decimal(10 ** decimals))

    def _wei_to_amount(self, wei: int, decimals: int = 6) -> Decimal:
        """Convierte unidades del token (wei) a decimal."""
        return Decimal(wei) / Decimal(10 ** decimals)

    def _generate_reference_code(self) -> str:
        """Genera codigo de referencia unico (ej: FRC-A1B2C3D4)."""
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(8))
        return f"FRC-{code}"

    # ============ Cotizacion ============

    async def get_quote(
        self,
        amount_source: Decimal,
        currency_source: Currency,
        currency_destination: Currency,
        user_id: Optional[str] = None,
    ) -> RemittanceQuote:
        """
        Obtiene cotizacion para una remesa.

        Args:
            amount_source: Monto en moneda origen
            currency_source: Moneda origen (ej: MXN)
            currency_destination: Moneda destino (ej: USD)
            user_id: ID del usuario (para verificar limites)

        Returns:
            RemittanceQuote con todos los detalles
        """
        # Obtener tasas de cambio (simulado - integrar con API real)
        rate_source_usd = await self._get_exchange_rate(currency_source, Currency.USD)
        rate_usd_destination = await self._get_exchange_rate(Currency.USD, currency_destination)

        # Calcular montos
        amount_usd = amount_source * rate_source_usd
        amount_stablecoin = amount_usd  # 1:1 con USD
        amount_destination = amount_usd * rate_usd_destination

        # Calcular fees
        platform_fee = amount_source * self.PLATFORM_FEE_PERCENT
        network_fee = Decimal("0.50")  # Fee de gas estimado en USD
        total_fees = platform_fee + network_fee

        # Total a pagar
        total_to_pay = amount_source + total_fees

        # Tiempos
        now = datetime.utcnow()
        quote_expires = now + timedelta(minutes=self.QUOTE_VALIDITY_MINUTES)
        estimated_delivery = now + timedelta(minutes=10)  # 10 min promedio

        quote_id = secrets.token_urlsafe(16)

        return RemittanceQuote(
            amount_source=amount_source,
            currency_source=currency_source,
            amount_destination=amount_destination.quantize(Decimal("0.01")),
            currency_destination=currency_destination,
            amount_stablecoin=amount_stablecoin.quantize(Decimal("0.000001")),
            exchange_rate_source_usd=rate_source_usd,
            exchange_rate_usd_destination=rate_usd_destination,
            platform_fee=platform_fee.quantize(Decimal("0.01")),
            network_fee=network_fee,
            total_fees=total_fees.quantize(Decimal("0.01")),
            total_to_pay=total_to_pay.quantize(Decimal("0.01")),
            estimated_delivery=estimated_delivery,
            quote_expires_at=quote_expires,
            quote_id=quote_id,
        )

    async def _get_exchange_rate(
        self,
        currency_from: Currency,
        currency_to: Currency
    ) -> Decimal:
        """
        Obtiene tasa de cambio actual.
        TODO: Integrar con APIs reales (Banxico, Binance, etc.)
        """
        # Tasas simuladas - reemplazar con API real
        rates_to_usd = {
            Currency.MXN: Decimal("0.058"),  # 1 MXN = 0.058 USD
            Currency.USD: Decimal("1.0"),
            Currency.EUR: Decimal("1.08"),
            Currency.CLP: Decimal("0.0011"),
            Currency.COP: Decimal("0.00025"),
            Currency.PEN: Decimal("0.27"),
            Currency.BRL: Decimal("0.20"),
            Currency.ARS: Decimal("0.0012"),
        }

        if currency_from == currency_to:
            return Decimal("1.0")

        if currency_to == Currency.USD:
            return rates_to_usd.get(currency_from, Decimal("1.0"))

        if currency_from == Currency.USD:
            rate = rates_to_usd.get(currency_to, Decimal("1.0"))
            return (Decimal("1.0") / rate).quantize(Decimal("0.00000001"))

        # Cross rate
        rate_from_usd = rates_to_usd.get(currency_from, Decimal("1.0"))
        rate_to_usd = rates_to_usd.get(currency_to, Decimal("1.0"))
        return (rate_from_usd / rate_to_usd).quantize(Decimal("0.00000001"))

    # ============ Creacion de Remesas ============

    async def create_remittance(
        self,
        sender_id: str,
        recipient_info: Dict[str, Any],
        amount_source: Decimal,
        currency_source: Currency,
        currency_destination: Currency,
        payment_method: PaymentMethod,
        disbursement_method: DisbursementMethod,
        sender_ip: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> RemittanceResult:
        """
        Crea una nueva remesa.

        Args:
            sender_id: ID del usuario que envia
            recipient_info: Datos del beneficiario (nombre, banco, cuenta, etc.)
            amount_source: Monto en moneda origen
            currency_source: Moneda origen
            currency_destination: Moneda destino
            payment_method: Metodo de deposito
            disbursement_method: Metodo de entrega

        Returns:
            RemittanceResult con ID y estado
        """
        try:
            # 1. Validar usuario y KYC
            user = self.db.query(User).filter(User.id == sender_id).first()
            if not user:
                return RemittanceResult(success=False, error="User no encontrado")

            kyc_check = await self._validate_kyc_limits(
                sender_id, amount_source, currency_source
            )
            if not kyc_check["valid"]:
                return RemittanceResult(success=False, error=kyc_check["error"])

            # 2. Validar datos del beneficiario
            if not self._validate_recipient_info(recipient_info, disbursement_method):
                return RemittanceResult(success=False, error="Datos del beneficiario invalidos")

            # 3. Obtener cotizacion
            quote = await self.get_quote(
                amount_source, currency_source, currency_destination, sender_id
            )

            # 4. Crear registro de remesa
            reference_code = self._generate_reference_code()

            remittance = Remittance(
                reference_code=reference_code,
                sender_id=sender_id,
                recipient_info=recipient_info,
                amount_fiat_source=amount_source,
                currency_source=currency_source,
                amount_fiat_destination=quote.amount_destination,
                currency_destination=currency_destination,
                amount_stablecoin=quote.amount_stablecoin,
                stablecoin=Stablecoin.USDC,
                exchange_rate_source_usd=quote.exchange_rate_source_usd,
                exchange_rate_usd_destination=quote.exchange_rate_usd_destination,
                exchange_rate_locked_at=datetime.utcnow(),
                platform_fee=quote.platform_fee,
                network_fee=quote.network_fee,
                total_fees=quote.total_fees,
                status=RemittanceStatus.INITIATED,
                payment_method=payment_method,
                disbursement_method=disbursement_method,
                sender_ip=sender_ip,
                sender_device_fingerprint=device_fingerprint,
            )

            self.db.add(remittance)
            self.db.commit()
            self.db.refresh(remittance)

            logger.info(f"Remesa creada: {reference_code} - {amount_source} {currency_source.value}")

            return RemittanceResult(
                success=True,
                remittance_id=str(remittance.id),
                reference_code=reference_code,
                status=RemittanceStatus.INITIATED,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creando remesa: {e}")
            return RemittanceResult(success=False, error=str(e))

    async def _validate_kyc_limits(
        self,
        user_id: str,
        amount: Decimal,
        currency: Currency
    ) -> Dict[str, Any]:
        """Valida limites de remesa segun nivel KYC del usuario."""
        # Obtener perfil KYC
        kyc_profile = self.db.query(KYCProfile).filter(
            KYCProfile.user_id == user_id
        ).first()

        if not kyc_profile or kyc_profile.current_level == KYCLevel.LEVEL_0:
            return {"valid": False, "error": "Verificacion KYC requerida"}

        # Obtener limites para el nivel
        kyc_level_num = int(kyc_profile.current_level.value.split("_")[1])

        limits = self.db.query(RemittanceLimit).filter(
            and_(
                RemittanceLimit.corridor_source == currency,
                RemittanceLimit.kyc_level == kyc_level_num,
                RemittanceLimit.is_active == True
            )
        ).first()

        if not limits:
            # Limites por defecto
            max_amount = {1: 1000, 2: 5000, 3: 50000}.get(kyc_level_num, 1000)
        else:
            max_amount = float(limits.max_amount_usd)

        # Convertir monto a USD para comparar
        rate = await self._get_exchange_rate(currency, Currency.USD)
        amount_usd = float(amount * rate)

        if amount_usd > max_amount:
            return {
                "valid": False,
                "error": f"Monto excede limite de ${max_amount} USD para tu nivel KYC"
            }

        # Verificar limite mensual
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        monthly_total = self.db.query(func.sum(Remittance.amount_stablecoin)).filter(
            and_(
                Remittance.sender_id == user_id,
                Remittance.created_at >= month_start,
                Remittance.status.notin_([
                    RemittanceStatus.CANCELLED,
                    RemittanceStatus.FAILED,
                    RemittanceStatus.REFUNDED
                ])
            )
        ).scalar() or Decimal("0")

        monthly_limit = {1: 5000, 2: 25000, 3: 100000}.get(kyc_level_num, 5000)
        if float(monthly_total) + amount_usd > monthly_limit:
            return {
                "valid": False,
                "error": f"Excedes limite mensual de ${monthly_limit} USD"
            }

        return {"valid": True}

    def _validate_recipient_info(
        self,
        recipient_info: Dict[str, Any],
        method: DisbursementMethod
    ) -> bool:
        """Valida que los datos del beneficiario esten completos."""
        required_fields = ["name"]

        if method == DisbursementMethod.BANK_TRANSFER:
            required_fields.extend(["bank_name", "account_number"])

        if method == DisbursementMethod.MOBILE_WALLET:
            required_fields.extend(["phone"])

        return all(field in recipient_info and recipient_info[field] for field in required_fields)

    # ============ Operaciones Blockchain ============

    async def lock_funds_in_escrow(
        self,
        remittance_id: str,
        wallet_address: str,
    ) -> RemittanceResult:
        """
        Bloquea fondos en el smart contract de escrow.

        Args:
            remittance_id: ID de la remesa
            wallet_address: Wallet del usuario con los stablecoins

        Returns:
            RemittanceResult con tx_hash
        """
        try:
            remittance = self.db.query(Remittance).filter(
                Remittance.id == remittance_id
            ).first()

            if not remittance:
                return RemittanceResult(success=False, error="Remesa no encontrada")

            if remittance.status != RemittanceStatus.DEPOSITED:
                return RemittanceResult(
                    success=False,
                    error=f"Estado invalido: {remittance.status.value}"
                )

            # Crear registro de transaccion blockchain
            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                operation="lock",
                blockchain_status=BlockchainRemittanceStatus.PENDING,
                network=self.network,
                from_address=wallet_address,
                contract_address=self.contract_address,
            )
            self.db.add(blockchain_tx)
            self.db.flush()  # Para obtener el ID

            # Preparar parametros para el smart contract
            reference_bytes32 = self._reference_to_bytes32(remittance.reference_code)
            token_address = self._get_stablecoin_address(remittance.stablecoin)
            amount_wei = self._amount_to_wei(remittance.amount_stablecoin, self.STABLECOIN_DECIMALS)

            # Llamar al smart contract
            blockchain_svc = self._get_blockchain_service()
            tx_result = blockchain_svc.execute_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="lockFunds",
                args=[reference_bytes32, token_address, amount_wei]
            )

            if not tx_result.success:
                # Actualizar estado de la transaccion
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = tx_result.error
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error=f"Error en blockchain: {tx_result.error}"
                )

            # Actualizar estado de la transaccion blockchain
            blockchain_tx.tx_hash = tx_result.tx_hash
            blockchain_tx.blockchain_status = BlockchainRemittanceStatus.CONFIRMED
            blockchain_tx.block_number = tx_result.block_number
            blockchain_tx.gas_used = tx_result.gas_used
            blockchain_tx.submitted_at = datetime.utcnow()
            blockchain_tx.confirmed_at = datetime.utcnow()

            # Actualizar estado de remesa
            remittance.status = RemittanceStatus.LOCKED
            remittance.escrow_locked_at = datetime.utcnow()
            remittance.escrow_expires_at = datetime.utcnow() + timedelta(
                hours=self.ESCROW_TIMELOCK_HOURS
            )

            self.db.commit()

            logger.info(f"Fondos bloqueados para remesa {remittance.reference_code} - tx: {tx_result.tx_hash}")

            return RemittanceResult(
                success=True,
                remittance_id=str(remittance.id),
                reference_code=remittance.reference_code,
                status=RemittanceStatus.LOCKED,
                tx_hash=tx_result.tx_hash,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bloqueando fondos: {e}")
            return RemittanceResult(success=False, error=str(e))

    async def release_funds(
        self,
        remittance_id: str,
        operator_id: str,
    ) -> RemittanceResult:
        """
        Libera fondos del escrow (tras confirmar entrega fiat).
        Solo puede ser llamado por operadores autorizados.
        """
        try:
            remittance = self.db.query(Remittance).filter(
                Remittance.id == remittance_id
            ).first()

            if not remittance:
                return RemittanceResult(success=False, error="Remesa no encontrada")

            if remittance.status != RemittanceStatus.LOCKED:
                return RemittanceResult(
                    success=False,
                    error=f"Estado invalido: {remittance.status.value}"
                )

            # Crear registro de transaccion
            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                operation="release",
                blockchain_status=BlockchainRemittanceStatus.PENDING,
                network=self.network,
                contract_address=self.contract_address,
            )
            self.db.add(blockchain_tx)
            self.db.flush()

            # Obtener el ID de remesa en el smart contract
            onchain_remittance_id = await self._get_onchain_remittance_id(remittance.reference_code)
            if onchain_remittance_id is None or onchain_remittance_id == 0:
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = "Remesa no encontrada en blockchain"
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error="Remesa no encontrada en blockchain"
                )

            # Llamar al smart contract
            blockchain_svc = self._get_blockchain_service()
            tx_result = blockchain_svc.execute_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="releaseFunds",
                args=[onchain_remittance_id]
            )

            if not tx_result.success:
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = tx_result.error
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error=f"Error en blockchain: {tx_result.error}"
                )

            # Actualizar transaccion blockchain
            blockchain_tx.tx_hash = tx_result.tx_hash
            blockchain_tx.blockchain_status = BlockchainRemittanceStatus.CONFIRMED
            blockchain_tx.block_number = tx_result.block_number
            blockchain_tx.gas_used = tx_result.gas_used
            blockchain_tx.submitted_at = datetime.utcnow()
            blockchain_tx.confirmed_at = datetime.utcnow()

            # Actualizar estado
            remittance.status = RemittanceStatus.DISBURSED
            remittance.completed_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Fondos liberados para remesa {remittance.reference_code} - tx: {tx_result.tx_hash}")

            return RemittanceResult(
                success=True,
                remittance_id=str(remittance.id),
                reference_code=remittance.reference_code,
                status=RemittanceStatus.DISBURSED,
                tx_hash=tx_result.tx_hash,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error liberando fondos: {e}")
            return RemittanceResult(success=False, error=str(e))

    async def _get_onchain_remittance_id(self, reference_code: str) -> Optional[int]:
        """Obtiene el ID de remesa en el smart contract por codigo de referencia."""
        try:
            reference_bytes32 = self._reference_to_bytes32(reference_code)
            blockchain_svc = self._get_blockchain_service()

            result = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="getRemittanceByReference",
                args=[reference_bytes32]
            )
            return result
        except Exception as e:
            logger.error(f"Error obteniendo ID on-chain: {e}")
            return None

    async def process_refund(
        self,
        remittance_id: str,
    ) -> RemittanceResult:
        """
        Procesa reembolso automatico por expiracion del time-lock.
        """
        try:
            remittance = self.db.query(Remittance).filter(
                Remittance.id == remittance_id
            ).first()

            if not remittance:
                return RemittanceResult(success=False, error="Remesa no encontrada")

            if remittance.status != RemittanceStatus.LOCKED:
                return RemittanceResult(
                    success=False,
                    error=f"Estado invalido: {remittance.status.value}"
                )

            # Verificar que haya expirado
            if remittance.escrow_expires_at and datetime.utcnow() < remittance.escrow_expires_at:
                return RemittanceResult(
                    success=False,
                    error="Time-lock aun no ha expirado"
                )

            # Registro blockchain
            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                operation="refund",
                blockchain_status=BlockchainRemittanceStatus.PENDING,
                network=self.network,
                contract_address=self.contract_address,
            )
            self.db.add(blockchain_tx)
            self.db.flush()

            # Obtener el ID de remesa en el smart contract
            onchain_remittance_id = await self._get_onchain_remittance_id(remittance.reference_code)
            if onchain_remittance_id is None or onchain_remittance_id == 0:
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = "Remesa no encontrada en blockchain"
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error="Remesa no encontrada en blockchain"
                )

            # Verificar que se puede reembolsar en el smart contract
            blockchain_svc = self._get_blockchain_service()
            can_refund = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="canRefund",
                args=[onchain_remittance_id]
            )

            if not can_refund:
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = "Time-lock no ha expirado en blockchain"
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error="Time-lock aun no ha expirado en blockchain"
                )

            # Llamar al smart contract
            tx_result = blockchain_svc.execute_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="refund",
                args=[onchain_remittance_id]
            )

            if not tx_result.success:
                blockchain_tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                blockchain_tx.error_message = tx_result.error
                self.db.commit()
                return RemittanceResult(
                    success=False,
                    error=f"Error en blockchain: {tx_result.error}"
                )

            # Actualizar transaccion blockchain
            blockchain_tx.tx_hash = tx_result.tx_hash
            blockchain_tx.blockchain_status = BlockchainRemittanceStatus.CONFIRMED
            blockchain_tx.block_number = tx_result.block_number
            blockchain_tx.gas_used = tx_result.gas_used
            blockchain_tx.submitted_at = datetime.utcnow()
            blockchain_tx.confirmed_at = datetime.utcnow()

            # Actualizar estado
            remittance.status = RemittanceStatus.REFUNDED
            remittance.completed_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Reembolso procesado para remesa {remittance.reference_code} - tx: {tx_result.tx_hash}")

            return RemittanceResult(
                success=True,
                remittance_id=str(remittance.id),
                reference_code=remittance.reference_code,
                status=RemittanceStatus.REFUNDED,
                tx_hash=tx_result.tx_hash,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error procesando reembolso: {e}")
            return RemittanceResult(success=False, error=str(e))

    # ============ Consultas ============

    def get_remittance(self, remittance_id: str) -> Optional[Remittance]:
        """Obtiene una remesa por ID."""
        return self.db.query(Remittance).filter(
            Remittance.id == remittance_id
        ).first()

    def get_remittance_by_reference(self, reference_code: str) -> Optional[Remittance]:
        """Obtiene una remesa por codigo de referencia."""
        return self.db.query(Remittance).filter(
            Remittance.reference_code == reference_code
        ).first()

    def get_user_remittances(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[RemittanceStatus] = None,
    ) -> List[Remittance]:
        """Obtiene remesas de un usuario."""
        query = self.db.query(Remittance).filter(
            Remittance.sender_id == user_id
        )

        if status:
            query = query.filter(Remittance.status == status)

        return query.order_by(Remittance.created_at.desc()).offset(offset).limit(limit).all()

    def get_pending_refunds(self) -> List[Remittance]:
        """Obtiene remesas con time-lock expirado pendientes de reembolso."""
        return self.db.query(Remittance).filter(
            and_(
                Remittance.status == RemittanceStatus.LOCKED,
                Remittance.escrow_expires_at <= datetime.utcnow()
            )
        ).all()

    # ============ Conciliacion ============

    async def run_reconciliation(self) -> ReconciliationLog:
        """
        Ejecuta conciliacion entre ledger interno y blockchain.

        Compara:
        - Total bloqueado en DB vs total en smart contract
        - Alerta si hay discrepancia

        Debe ejecutarse cada 60 minutos via job scheduler.
        """
        log = ReconciliationLog(
            check_timestamp=datetime.utcnow(),
            network=self.network,
            stablecoin="USDC",
            contract_address=self.contract_address,
        )

        try:
            # Calcular total en ledger interno
            total_locked_db = self.db.query(
                func.sum(Remittance.amount_stablecoin)
            ).filter(
                Remittance.status == RemittanceStatus.LOCKED
            ).scalar() or Decimal("0")

            log.expected_balance_ledger = total_locked_db
            log.actual_balance_ledger = total_locked_db  # Mismo valor

            # Obtener totales del smart contract
            contract_totals = await self._get_contract_totals()
            contract_balance = contract_totals.get("locked", Decimal("0"))

            log.expected_balance_onchain = total_locked_db
            log.actual_balance_onchain = contract_balance

            # Calcular discrepancias
            log.discrepancy_ledger = Decimal("0")
            log.discrepancy_onchain = abs(total_locked_db - contract_balance)

            # Tolerancia de 0.01 USD para diferencias de redondeo
            log.discrepancy_detected = log.discrepancy_onchain > Decimal("0.01")

            if log.discrepancy_detected:
                log.error_payload = {
                    "message": "Discrepancia detectada entre ledger y blockchain",
                    "expected": str(total_locked_db),
                    "actual": str(contract_balance),
                    "difference": str(log.discrepancy_onchain),
                    "contract_totals": {
                        "locked": str(contract_totals.get("locked", 0)),
                        "released": str(contract_totals.get("released", 0)),
                        "refunded": str(contract_totals.get("refunded", 0)),
                        "fees": str(contract_totals.get("fees", 0)),
                    }
                }
                logger.warning(f"ALERTA: Discrepancia en conciliacion: {log.error_payload}")

            self.db.add(log)
            self.db.commit()

            return log

        except Exception as e:
            logger.error(f"Error en conciliacion: {e}")
            log.error_payload = {"error": str(e)}
            log.discrepancy_detected = True
            self.db.add(log)
            self.db.commit()
            return log

    async def _get_contract_totals(self) -> Dict[str, Decimal]:
        """Obtiene los totales del smart contract."""
        try:
            blockchain_svc = self._get_blockchain_service()

            result = blockchain_svc.call_contract_function(
                contract_address=self.contract_address,
                abi=self.contract_abi,
                function_name="getTotals",
                args=[]
            )

            # El resultado es una tupla: (locked, released, refunded, fees)
            if result and len(result) == 4:
                return {
                    "locked": self._wei_to_amount(result[0], self.STABLECOIN_DECIMALS),
                    "released": self._wei_to_amount(result[1], self.STABLECOIN_DECIMALS),
                    "refunded": self._wei_to_amount(result[2], self.STABLECOIN_DECIMALS),
                    "fees": self._wei_to_amount(result[3], self.STABLECOIN_DECIMALS),
                }
            return {"locked": Decimal("0"), "released": Decimal("0"), "refunded": Decimal("0"), "fees": Decimal("0")}

        except Exception as e:
            logger.error(f"Error obteniendo totales del contrato: {e}")
            return {"locked": Decimal("0"), "released": Decimal("0"), "refunded": Decimal("0"), "fees": Decimal("0")}
