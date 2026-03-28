"""
Servicio de integracion con Bitso Exchange.

Bitso es el exchange de criptomonedas mas grande de Mexico.
Este servicio permite:
- Conversion de stablecoins (USDC/USDT) a MXN
- Retiros directos via SPEI a cualquier banco mexicano
- Consulta de cotizaciones en tiempo real
- Gestion de balances

Documentacion API: https://bitso.com/api_info

Autenticacion:
- Firma HMAC-SHA256 con api_key y api_secret
- Nonce basado en timestamp

Limites:
- Rate limit: 300 requests/minuto
- Minimo orden USDC: 1 USDC
- Minimo retiro SPEI: 10 MXN
"""
import logging
import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.bitso import (
    BitsoOrderSide,
    BitsoOrderType,
    BitsoOrderStatus,
    BitsoWithdrawalStatus,
    BitsoCurrency,
    BitsoBook,
    BitsoTicker,
    BitsoBalance,
    BitsoOrder,
    BitsoWithdrawal,
    BitsoTrade,
    BitsoAccountStatus,
    PlaceOrderRequest,
    SPEIWithdrawalRequest,
    ConvertResponse,
    QuoteResponse,
    WithdrawalResponse,
    BitsoRateCache,
    BITSO_FEES,
    BITSO_MIN_ORDER,
    BITSO_MIN_SPEI_WITHDRAWAL,
)

logger = logging.getLogger(__name__)


class BitsoError(Exception):
    """Error base de Bitso."""
    pass


class BitsoAPIError(BitsoError):
    """Error de API de Bitso."""
    def __init__(self, code: str, message: str, response: Optional[dict] = None):
        self.code = code
        self.message = message
        self.response = response
        super().__init__(f"Bitso API Error ({code}): {message}")


class BitsoAuthError(BitsoError):
    """Error de autenticacion."""
    pass


class BitsoInsufficientFundsError(BitsoError):
    """Fondos insuficientes."""
    pass


class BitsoRateLimitError(BitsoError):
    """Rate limit excedido."""
    pass


@dataclass
class BitsoConfig:
    """Configuracion del servicio Bitso."""
    api_key: str = ""
    api_secret: str = ""
    api_url: str = "https://api.bitso.com/v3"
    sandbox_url: str = "https://api-dev.bitso.com/v3"
    use_sandbox: bool = True
    timeout_seconds: int = 30
    rate_cache_ttl: int = 30  # segundos

    @property
    def base_url(self) -> str:
        return self.sandbox_url if self.use_sandbox else self.api_url


class BitsoService:
    """
    Servicio principal de Bitso Exchange.

    Uso:
        service = BitsoService(db)

        # Obtener cotizacion
        quote = await service.get_quote(
            from_currency=BitsoCurrency.USDC,
            to_currency=BitsoCurrency.MXN,
            amount=Decimal("100")
        )

        # Convertir USDC a MXN
        result = await service.convert_to_mxn(
            usdc_amount=Decimal("100")
        )

        # Retirar a SPEI
        withdrawal = await service.withdraw_spei(
            amount=quote.result_amount,
            clabe="012180015678912345",
            beneficiary_name="JUAN PEREZ"
        )
    """

    def __init__(
        self,
        db: Session,
        config: Optional[BitsoConfig] = None,
    ):
        """
        Inicializa el servicio Bitso.

        Args:
            db: Sesion de base de datos
            config: Configuracion opcional

        Raises:
            ValueError: Si las credenciales están vacías en producción
        """
        self.db = db
        self.config = config or self._load_config_from_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_cache: Dict[str, BitsoRateCache] = {}

        # Validar credenciales en producción
        self._validate_credentials()

    def _load_config_from_settings(self) -> BitsoConfig:
        """Carga configuracion desde settings."""
        return BitsoConfig(
            api_key=getattr(settings, 'BITSO_API_KEY', ''),
            api_secret=getattr(settings, 'BITSO_API_SECRET', ''),
            api_url=getattr(settings, 'BITSO_API_URL', 'https://api.bitso.com/v3'),
            sandbox_url=getattr(settings, 'BITSO_SANDBOX_URL', 'https://api-dev.bitso.com/v3'),
            use_sandbox=getattr(settings, 'BITSO_USE_SANDBOX', True),
            timeout_seconds=int(getattr(settings, 'BITSO_TIMEOUT', 30)),
            rate_cache_ttl=int(getattr(settings, 'BITSO_RATE_CACHE_TTL', 30)),
        )

    def _validate_credentials(self) -> None:
        """
        Valida que las credenciales de Bitso estén configuradas.

        En producción (no sandbox), las credenciales son obligatorias.
        En sandbox, se permite operar sin credenciales para endpoints públicos.
        """
        if not self.config.use_sandbox:
            # En producción, credenciales son obligatorias
            if not self.config.api_key or not self.config.api_secret:
                raise ValueError(
                    "BITSO_API_KEY y BITSO_API_SECRET son obligatorios en producción. "
                    "Configure las variables de entorno o use sandbox mode."
                )

            # Validar formato mínimo de credenciales
            if len(self.config.api_key) < 10:
                raise ValueError("BITSO_API_KEY parece inválido (muy corto)")
            if len(self.config.api_secret) < 10:
                raise ValueError("BITSO_API_SECRET parece inválido (muy corto)")

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

    # ============ Autenticacion ============

    def _generate_signature(
        self,
        http_method: str,
        request_path: str,
        payload: str = "",
    ) -> Tuple[str, str]:
        """
        Genera firma HMAC-SHA256 para autenticacion.

        Returns:
            Tuple (nonce, signature)
        """
        nonce = str(int(time.time() * 1000))

        # Mensaje a firmar: nonce + method + path + payload
        message = f"{nonce}{http_method.upper()}{request_path}{payload}"

        # Firma HMAC-SHA256
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return nonce, signature

    def _get_auth_headers(
        self,
        http_method: str,
        request_path: str,
        payload: str = "",
    ) -> Dict[str, str]:
        """Genera headers de autenticacion."""
        nonce, signature = self._generate_signature(http_method, request_path, payload)

        return {
            "Authorization": f"Bitso {self.config.api_key}:{nonce}:{signature}",
        }

    # ============ Requests ============

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        auth_required: bool = True,
    ) -> dict:
        """
        Realiza request a la API de Bitso.

        Args:
            method: HTTP method
            endpoint: Endpoint (sin base URL)
            params: Query parameters
            json_data: Body JSON
            auth_required: Si requiere autenticacion

        Returns:
            Respuesta JSON parseada

        Raises:
            BitsoAPIError: Error de API
        """
        client = await self._get_client()

        url = f"{self.config.base_url}{endpoint}"
        request_path = f"/v3{endpoint}"

        # Preparar payload para firma
        payload = ""
        if json_data:
            payload = json.dumps(json_data, separators=(',', ':'))

        # Headers
        headers = {}
        if auth_required:
            headers = self._get_auth_headers(method.upper(), request_path, payload)

        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )

            data = response.json()

            # Verificar respuesta
            if not data.get("success", False):
                error = data.get("error", {})
                code = error.get("code", "unknown")
                message = error.get("message", "Error desconocido")

                if code == "0201":  # Insufficient funds
                    raise BitsoInsufficientFundsError(message)
                elif code == "0102":  # Invalid credentials
                    raise BitsoAuthError(message)
                elif response.status_code == 429:
                    raise BitsoRateLimitError("Rate limit excedido")

                raise BitsoAPIError(code=code, message=message, response=data)

            return data.get("payload", data)

        except httpx.TimeoutException:
            raise BitsoAPIError(code="TIMEOUT", message="Request timeout")
        except json.JSONDecodeError:
            raise BitsoAPIError(code="PARSE_ERROR", message="Invalid JSON response")

    # ============ Public Endpoints (no auth) ============

    async def get_ticker(self, book: str = "usdc_mxn") -> BitsoTicker:
        """
        Obtiene ticker actual de un libro.

        Args:
            book: Libro de ordenes (ej: usdc_mxn)

        Returns:
            BitsoTicker con precios actuales
        """
        # Verificar cache
        if book in self._rate_cache:
            cached = self._rate_cache[book]
            if not cached.is_expired:
                return BitsoTicker(
                    book=book,
                    volume=Decimal("0"),
                    high=cached.ask,
                    low=cached.bid,
                    last=cached.last,
                    bid=cached.bid,
                    ask=cached.ask,
                    created_at=cached.cached_at,
                )

        # Obtener de API
        data = await self._request(
            "GET",
            f"/ticker/",
            params={"book": book},
            auth_required=False,
        )

        ticker = BitsoTicker(
            book=data.get("book", book),
            volume=Decimal(str(data.get("volume", "0"))),
            high=Decimal(str(data.get("high", "0"))),
            low=Decimal(str(data.get("low", "0"))),
            last=Decimal(str(data.get("last", "0"))),
            bid=Decimal(str(data.get("bid", "0"))),
            ask=Decimal(str(data.get("ask", "0"))),
            vwap=Decimal(str(data.get("vwap", "0"))) if data.get("vwap") else None,
            created_at=datetime.utcnow(),
        )

        # Actualizar cache
        self._rate_cache[book] = BitsoRateCache(
            book=book,
            bid=ticker.bid,
            ask=ticker.ask,
            last=ticker.last,
            cached_at=datetime.utcnow(),
            ttl_seconds=self.config.rate_cache_ttl,
        )

        return ticker

    async def get_available_books(self) -> List[dict]:
        """Obtiene lista de libros disponibles."""
        data = await self._request("GET", "/available_books/", auth_required=False)
        return data

    # ============ Private Endpoints (auth required) ============

    async def get_account_status(self) -> BitsoAccountStatus:
        """Obtiene estado de la cuenta."""
        data = await self._request("GET", "/account_status/")

        return BitsoAccountStatus(
            client_id=data.get("client_id", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            status=data.get("status", ""),
            daily_limit=Decimal(str(data.get("daily_limit", "0"))),
            monthly_limit=Decimal(str(data.get("monthly_limit", "0"))),
            daily_remaining=Decimal(str(data.get("daily_remaining", "0"))),
            monthly_remaining=Decimal(str(data.get("monthly_remaining", "0"))),
            email=data.get("email", ""),
            is_verified=data.get("status") == "active",
        )

    async def get_balances(self) -> List[BitsoBalance]:
        """Obtiene balances de todas las monedas."""
        data = await self._request("GET", "/balance/")

        balances = []
        for item in data.get("balances", []):
            balances.append(BitsoBalance(
                currency=item.get("currency", ""),
                total=Decimal(str(item.get("total", "0"))),
                available=Decimal(str(item.get("available", "0"))),
                locked=Decimal(str(item.get("locked", "0"))),
            ))

        return balances

    async def get_balance(self, currency: str) -> Optional[BitsoBalance]:
        """Obtiene balance de una moneda especifica."""
        balances = await self.get_balances()
        for balance in balances:
            if balance.currency.lower() == currency.lower():
                return balance
        return None

    # ============ Trading ============

    async def place_order(self, request: PlaceOrderRequest) -> BitsoOrder:
        """
        Coloca una orden de compra/venta.

        Args:
            request: Datos de la orden

        Returns:
            BitsoOrder con resultado
        """
        payload = {
            "book": request.book.value,
            "side": request.side.value,
            "type": request.type.value,
        }

        if request.major:
            payload["major"] = str(request.major)
        if request.minor:
            payload["minor"] = str(request.minor)
        if request.price and request.type == BitsoOrderType.LIMIT:
            payload["price"] = str(request.price)

        data = await self._request("POST", "/orders/", json_data=payload)

        return BitsoOrder(
            oid=data.get("oid", ""),
            book=request.book.value,
            side=request.side,
            type=request.type,
            status=BitsoOrderStatus.OPEN,
            original_amount=request.major or request.minor or Decimal("0"),
            unfilled_amount=Decimal("0"),
            price=request.price,
            created_at=datetime.utcnow(),
        )

    async def get_order(self, order_id: str) -> Optional[BitsoOrder]:
        """Obtiene estado de una orden."""
        try:
            data = await self._request("GET", f"/orders/{order_id}/")

            if not data:
                return None

            return BitsoOrder(
                oid=data.get("oid", order_id),
                book=data.get("book", ""),
                side=BitsoOrderSide(data.get("side", "buy")),
                type=BitsoOrderType(data.get("type", "market")),
                status=BitsoOrderStatus(data.get("status", "open")),
                original_amount=Decimal(str(data.get("original_amount", "0"))),
                unfilled_amount=Decimal(str(data.get("unfilled_amount", "0"))),
                price=Decimal(str(data.get("price"))) if data.get("price") else None,
                created_at=datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00")),
            )
        except BitsoAPIError:
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancela una orden."""
        try:
            await self._request("DELETE", f"/orders/{order_id}/")
            return True
        except BitsoAPIError:
            return False

    async def get_trades(self, limit: int = 25) -> List[BitsoTrade]:
        """Obtiene historial de trades."""
        data = await self._request("GET", "/user_trades/", params={"limit": limit})

        trades = []
        for item in data:
            trades.append(BitsoTrade(
                tid=item.get("tid", ""),
                book=item.get("book", ""),
                side=BitsoOrderSide(item.get("side", "buy")),
                major=Decimal(str(item.get("major", "0"))),
                minor=Decimal(str(item.get("minor", "0"))),
                price=Decimal(str(item.get("price", "0"))),
                fees_amount=Decimal(str(item.get("fees_amount", "0"))),
                fees_currency=item.get("fees_currency", ""),
                created_at=datetime.fromisoformat(item.get("created_at", "").replace("Z", "+00:00")),
                oid=item.get("oid"),
            ))

        return trades

    # ============ Conversion ============

    async def get_quote(
        self,
        from_currency: BitsoCurrency,
        to_currency: BitsoCurrency,
        amount: Decimal,
    ) -> QuoteResponse:
        """
        Obtiene cotizacion para conversion.

        Args:
            from_currency: Moneda origen (usdc, btc, etc.)
            to_currency: Moneda destino (mxn, usd)
            amount: Cantidad a convertir

        Returns:
            QuoteResponse con tasa y monto resultante
        """
        # Determinar libro y lado
        book = f"{from_currency.value}_{to_currency.value}"
        inverse = False

        # Verificar si el libro existe en orden inverso
        try:
            ticker = await self.get_ticker(book)
        except BitsoAPIError:
            # Intentar libro inverso
            book = f"{to_currency.value}_{from_currency.value}"
            ticker = await self.get_ticker(book)
            inverse = True

        # Calcular conversion
        if inverse:
            # Comprando la moneda origen con la destino
            rate = Decimal("1") / ticker.ask
            result_amount = amount * rate
        else:
            # Vendiendo la moneda origen por la destino
            rate = ticker.bid
            result_amount = amount * rate

        # Aplicar comision de trading
        fee_rate = BITSO_FEES["trading"]
        fee = result_amount * fee_rate
        result_amount -= fee

        return QuoteResponse(
            from_currency=from_currency.value,
            to_currency=to_currency.value,
            amount=amount,
            rate=rate,
            inverse_rate=Decimal("1") / rate if rate > 0 else Decimal("0"),
            result_amount=result_amount.quantize(Decimal("0.01")),
            fee=fee.quantize(Decimal("0.01")),
            fee_percentage=fee_rate * 100,
            expires_at=datetime.utcnow() + timedelta(seconds=30),
            quote_id=f"quote_{uuid4().hex[:12]}",
        )

    async def convert_to_mxn(
        self,
        usdc_amount: Decimal,
        order_type: BitsoOrderType = BitsoOrderType.MARKET,
    ) -> ConvertResponse:
        """
        Convierte USDC a MXN.

        Ejecuta una orden de venta en el libro usdc_mxn.

        Args:
            usdc_amount: Cantidad de USDC a vender
            order_type: Tipo de orden (market o limit)

        Returns:
            ConvertResponse con resultado
        """
        # Validar monto minimo
        min_amount = BITSO_MIN_ORDER.get("usdc_mxn", Decimal("1"))
        if usdc_amount < min_amount:
            return ConvertResponse(
                success=False,
                from_currency="usdc",
                to_currency="mxn",
                from_amount=usdc_amount,
                to_amount=Decimal("0"),
                rate=Decimal("0"),
                fee=Decimal("0"),
                created_at=datetime.utcnow(),
                error=f"Monto minimo es {min_amount} USDC",
            )

        # Verificar balance
        balance = await self.get_balance("usdc")
        if not balance or balance.available < usdc_amount:
            return ConvertResponse(
                success=False,
                from_currency="usdc",
                to_currency="mxn",
                from_amount=usdc_amount,
                to_amount=Decimal("0"),
                rate=Decimal("0"),
                fee=Decimal("0"),
                created_at=datetime.utcnow(),
                error="Saldo USDC insuficiente",
            )

        # Obtener cotizacion
        ticker = await self.get_ticker("usdc_mxn")
        expected_mxn = usdc_amount * ticker.bid

        # Ejecutar orden
        try:
            order_request = PlaceOrderRequest(
                book=BitsoBook.USDC_MXN,
                side=BitsoOrderSide.SELL,
                type=order_type,
                major=usdc_amount,
            )

            order = await self.place_order(order_request)

            # Esperar ejecucion (para ordenes market)
            if order_type == BitsoOrderType.MARKET:
                # Consultar trades para obtener monto real
                await self._wait_for_order_completion(order.oid)
                trades = await self.get_trades(limit=5)

                mxn_received = Decimal("0")
                fee_total = Decimal("0")
                actual_rate = Decimal("0")

                for trade in trades:
                    if trade.oid == order.oid:
                        mxn_received += trade.minor
                        fee_total += trade.fees_amount
                        actual_rate = trade.price

                return ConvertResponse(
                    success=True,
                    order_id=order.oid,
                    from_currency="usdc",
                    to_currency="mxn",
                    from_amount=usdc_amount,
                    to_amount=mxn_received,
                    rate=actual_rate,
                    fee=fee_total,
                    created_at=datetime.utcnow(),
                )

            # Para ordenes limit, retornar inmediatamente
            return ConvertResponse(
                success=True,
                order_id=order.oid,
                from_currency="usdc",
                to_currency="mxn",
                from_amount=usdc_amount,
                to_amount=expected_mxn,
                rate=ticker.bid,
                fee=expected_mxn * BITSO_FEES["trading"],
                created_at=datetime.utcnow(),
            )

        except BitsoInsufficientFundsError as e:
            return ConvertResponse(
                success=False,
                from_currency="usdc",
                to_currency="mxn",
                from_amount=usdc_amount,
                to_amount=Decimal("0"),
                rate=Decimal("0"),
                fee=Decimal("0"),
                created_at=datetime.utcnow(),
                error=str(e),
            )

    async def _wait_for_order_completion(
        self,
        order_id: str,
        max_wait_seconds: int = 30,
    ) -> bool:
        """Espera a que una orden se complete."""
        import asyncio

        start = time.time()
        while time.time() - start < max_wait_seconds:
            order = await self.get_order(order_id)
            if order and order.status == BitsoOrderStatus.COMPLETED:
                return True
            await asyncio.sleep(1)

        return False

    # ============ Withdrawals ============

    async def withdraw_spei(
        self,
        amount: Decimal,
        clabe: str,
        beneficiary_name: str,
        notes_ref: Optional[str] = None,
        numeric_reference: Optional[str] = None,
    ) -> WithdrawalResponse:
        """
        Retira MXN via SPEI a una cuenta bancaria.

        Args:
            amount: Monto en MXN
            clabe: CLABE destino (18 digitos)
            beneficiary_name: Nombre del beneficiario
            notes_ref: Referencia/concepto
            numeric_reference: Referencia numerica (7 digitos)

        Returns:
            WithdrawalResponse con resultado
        """
        # Validaciones
        if amount < BITSO_MIN_SPEI_WITHDRAWAL:
            return WithdrawalResponse(
                success=False,
                amount=amount,
                fee=Decimal("0"),
                currency="mxn",
                method="spei",
                error=f"Monto minimo de retiro SPEI es ${BITSO_MIN_SPEI_WITHDRAWAL} MXN",
            )

        if len(clabe) != 18 or not clabe.isdigit():
            return WithdrawalResponse(
                success=False,
                amount=amount,
                fee=Decimal("0"),
                currency="mxn",
                method="spei",
                error="CLABE invalida",
            )

        # Verificar balance MXN
        balance = await self.get_balance("mxn")
        if not balance or balance.available < amount:
            return WithdrawalResponse(
                success=False,
                amount=amount,
                fee=Decimal("0"),
                currency="mxn",
                method="spei",
                error="Saldo MXN insuficiente",
            )

        # Crear retiro
        payload = {
            "method": "sp",  # SPEI
            "amount": str(amount),
            "clabe": clabe,
            "recipient_given_names": beneficiary_name[:40],
            "recipient_family_names": "",
        }

        if notes_ref:
            payload["notes_ref"] = notes_ref[:40]
        if numeric_reference:
            payload["numeric_ref"] = numeric_reference

        try:
            data = await self._request("POST", "/spei_withdrawal/", json_data=payload)

            return WithdrawalResponse(
                success=True,
                wid=data.get("wid", ""),
                status=BitsoWithdrawalStatus.PENDING,
                amount=amount,
                fee=BITSO_FEES["spei_withdrawal"],
                currency="mxn",
                method="spei",
                details={
                    "clabe": clabe,
                    "beneficiary_name": beneficiary_name,
                },
                created_at=datetime.utcnow(),
            )

        except BitsoAPIError as e:
            return WithdrawalResponse(
                success=False,
                amount=amount,
                fee=Decimal("0"),
                currency="mxn",
                method="spei",
                error=str(e),
            )

    async def get_withdrawal_status(self, wid: str) -> Optional[BitsoWithdrawal]:
        """Obtiene estado de un retiro."""
        try:
            data = await self._request("GET", f"/withdrawals/{wid}/")

            return BitsoWithdrawal(
                wid=data.get("wid", wid),
                status=BitsoWithdrawalStatus(data.get("status", "pending")),
                currency=data.get("currency", ""),
                method=data.get("method", ""),
                amount=Decimal(str(data.get("amount", "0"))),
                fee=Decimal(str(data.get("fee", "0"))) if data.get("fee") else None,
                created_at=datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00")),
            )
        except BitsoAPIError:
            return None

    # ============ Full Flow: USDC to Bank Account ============

    async def usdc_to_bank_account(
        self,
        usdc_amount: Decimal,
        clabe: str,
        beneficiary_name: str,
        concept: Optional[str] = None,
        remittance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Flujo completo: Convierte USDC a MXN y envia a cuenta bancaria.

        1. Vende USDC por MXN
        2. Retira MXN via SPEI

        Args:
            usdc_amount: Cantidad de USDC
            clabe: CLABE destino
            beneficiary_name: Nombre del beneficiario
            concept: Concepto/referencia
            remittance_id: ID de remesa asociada

        Returns:
            Dict con resultado completo
        """
        result = {
            "success": False,
            "remittance_id": remittance_id,
            "conversion": None,
            "withdrawal": None,
            "total_mxn": Decimal("0"),
            "total_fees_mxn": Decimal("0"),
            "error": None,
        }

        # Paso 1: Convertir USDC a MXN
        logger.info(f"Iniciando conversion {usdc_amount} USDC a MXN")
        conversion = await self.convert_to_mxn(usdc_amount)

        if not conversion.success:
            result["error"] = f"Error en conversion: {conversion.error}"
            result["conversion"] = conversion
            return result

        result["conversion"] = conversion
        mxn_amount = conversion.to_amount

        logger.info(f"Conversion exitosa: {usdc_amount} USDC -> ${mxn_amount} MXN")

        # Paso 2: Retirar MXN via SPEI
        logger.info(f"Iniciando retiro SPEI: ${mxn_amount} a {clabe[:6]}***")
        withdrawal = await self.withdraw_spei(
            amount=mxn_amount,
            clabe=clabe,
            beneficiary_name=beneficiary_name,
            notes_ref=concept,
        )

        result["withdrawal"] = withdrawal

        if not withdrawal.success:
            result["error"] = f"Error en retiro SPEI: {withdrawal.error}"
            return result

        # Exito
        result["success"] = True
        result["total_mxn"] = mxn_amount
        result["total_fees_mxn"] = conversion.fee + withdrawal.fee

        logger.info(
            f"Flujo USDC->SPEI completado: "
            f"{usdc_amount} USDC -> ${mxn_amount} MXN -> {clabe[:6]}*** "
            f"(fees: ${result['total_fees_mxn']})"
        )

        return result


# ============ Factory ============

_bitso_service: Optional[BitsoService] = None


def get_bitso_service(db: Session) -> BitsoService:
    """Factory para obtener instancia del servicio."""
    return BitsoService(db=db)


async def cleanup_bitso_service():
    """Limpia recursos del servicio."""
    global _bitso_service
    if _bitso_service:
        await _bitso_service.close()
        _bitso_service = None
