"""
Tests para el servicio Bitso (Exchange Cripto-Fiat).

Cubre:
- Autenticacion HMAC-SHA256
- Obtencion de ticker/cotizaciones
- Colocacion de ordenes
- Retiros SPEI
- Flujo completo USDC -> MXN -> SPEI
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
import time

from app.services.bitso_service import (
    BitsoService,
    BitsoConfig,
    BitsoError,
    BitsoAPIError,
    BitsoInsufficientFundsError,
)
from app.schemas.bitso import (
    BitsoTicker,
    BitsoBalance,
    BitsoOrder,
    BitsoWithdrawal,
    BitsoOrderSide,
    BitsoOrderType,
    BitsoOrderStatus,
    BitsoWithdrawalStatus,
    PlaceOrderRequest,
    SPEIWithdrawalRequest,
    ConvertResponse,
    BitsoBook,
)


# ==================== FIXTURES ====================

@pytest.fixture
def bitso_config():
    """Configuracion de Bitso para tests."""
    return BitsoConfig(
        api_key="test_api_key_12345",
        api_secret="test_api_secret_67890",
        use_production=False,
    )


@pytest.fixture
def bitso_service(bitso_config):
    """Servicio Bitso para tests."""
    return BitsoService(config=bitso_config)


@pytest.fixture
def mock_ticker_response():
    """Respuesta mock de ticker."""
    return {
        "success": True,
        "payload": {
            "book": "usdc_mxn",
            "volume": "1234567.89",
            "high": "17.50",
            "low": "17.20",
            "last": "17.35",
            "bid": "17.30",
            "ask": "17.40",
            "vwap": "17.33",
            "created_at": "2024-01-15T10:30:00+00:00"
        }
    }


@pytest.fixture
def mock_balances_response():
    """Respuesta mock de balances."""
    return {
        "success": True,
        "payload": {
            "balances": [
                {
                    "currency": "usdc",
                    "total": "1000.00",
                    "available": "950.00",
                    "locked": "50.00",
                    "pending_deposit": "0.00",
                    "pending_withdrawal": "0.00"
                },
                {
                    "currency": "mxn",
                    "total": "50000.00",
                    "available": "45000.00",
                    "locked": "5000.00",
                    "pending_deposit": "0.00",
                    "pending_withdrawal": "0.00"
                }
            ]
        }
    }


@pytest.fixture
def mock_order_response():
    """Respuesta mock de orden."""
    return {
        "success": True,
        "payload": {
            "oid": "abc123def456",
            "book": "usdc_mxn",
            "side": "sell",
            "type": "market",
            "status": "completed",
            "original_amount": "100.00",
            "unfilled_amount": "0.00",
            "price": None,
            "created_at": "2024-01-15T10:30:00+00:00",
            "updated_at": "2024-01-15T10:30:01+00:00"
        }
    }


@pytest.fixture
def mock_withdrawal_response():
    """Respuesta mock de retiro."""
    return {
        "success": True,
        "payload": {
            "wid": "xyz789",
            "status": "pending",
            "currency": "mxn",
            "method": "spei",
            "amount": "17300.00",
            "fee": "0.00",
            "created_at": "2024-01-15T10:35:00+00:00",
            "details": {
                "clabe": "012180015678912345",
                "beneficiary_name": "JUAN PEREZ"
            }
        }
    }


# ==================== TESTS: Configuracion ====================

class TestBitsoConfig:
    """Tests para configuracion de Bitso."""

    def test_config_sandbox(self):
        """Configuracion sandbox debe usar URL de desarrollo."""
        config = BitsoConfig(
            api_key="key",
            api_secret="secret",
            use_production=False
        )
        assert config.base_url == "https://api-dev.bitso.com"

    def test_config_production(self):
        """Configuracion produccion debe usar URL de produccion."""
        config = BitsoConfig(
            api_key="key",
            api_secret="secret",
            use_production=True
        )
        assert config.base_url == "https://api.bitso.com"

    def test_config_defaults(self):
        """Valores por defecto deben ser correctos."""
        config = BitsoConfig(
            api_key="key",
            api_secret="secret"
        )
        assert config.timeout == 30
        assert config.use_production is False


# ==================== TESTS: Autenticacion ====================

class TestBitsoAuthentication:
    """Tests para autenticacion HMAC-SHA256."""

    def test_generate_signature(self, bitso_service):
        """Firma debe generarse correctamente."""
        http_method = "GET"
        request_path = "/v3/balance/"
        payload = ""

        nonce, signature = bitso_service._generate_signature(
            http_method, request_path, payload
        )

        # Verificar que nonce es timestamp en milisegundos
        assert nonce.isdigit()
        assert len(nonce) >= 13  # Milisegundos

        # Verificar que firma es hex
        assert all(c in '0123456789abcdef' for c in signature)
        assert len(signature) == 64  # SHA256 hex

    def test_signature_changes_with_nonce(self, bitso_service):
        """Cada firma debe ser diferente por nonce."""
        nonce1, sig1 = bitso_service._generate_signature("GET", "/v3/balance/", "")
        # Esperar un milisegundo para diferente nonce
        time.sleep(0.001)
        nonce2, sig2 = bitso_service._generate_signature("GET", "/v3/balance/", "")

        assert nonce1 != nonce2
        assert sig1 != sig2

    def test_signature_with_payload(self, bitso_service):
        """Firma con payload debe ser diferente a sin payload."""
        _, sig_empty = bitso_service._generate_signature("POST", "/v3/orders/", "")
        _, sig_with_payload = bitso_service._generate_signature(
            "POST", "/v3/orders/", '{"book":"usdc_mxn"}'
        )

        assert sig_empty != sig_with_payload


# ==================== TESTS: Ticker ====================

class TestBitsoTicker:
    """Tests para obtencion de ticker."""

    @pytest.mark.asyncio
    async def test_get_ticker_success(self, bitso_service, mock_ticker_response):
        """Debe obtener ticker correctamente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_ticker_response
        ):
            ticker = await bitso_service.get_ticker("usdc_mxn")

            assert ticker is not None
            assert ticker.book == "usdc_mxn"
            assert ticker.bid == Decimal("17.30")
            assert ticker.ask == Decimal("17.40")
            assert ticker.last == Decimal("17.35")

    @pytest.mark.asyncio
    async def test_get_ticker_spread(self, bitso_service, mock_ticker_response):
        """Spread debe calcularse correctamente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_ticker_response
        ):
            ticker = await bitso_service.get_ticker("usdc_mxn")

            assert ticker.spread == Decimal("0.10")  # 17.40 - 17.30
            # Spread percentage ~ 0.57%
            assert ticker.spread_percentage > Decimal("0")

    @pytest.mark.asyncio
    async def test_get_ticker_cached(self, bitso_service, mock_ticker_response):
        """Ticker debe cachearse."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_ticker_response
        ) as mock_request:
            # Primera llamada
            await bitso_service.get_ticker("usdc_mxn")
            # Segunda llamada inmediata (debe usar cache)
            await bitso_service.get_ticker("usdc_mxn")

            # Solo debe haber hecho 1 request
            assert mock_request.call_count == 1


# ==================== TESTS: Balances ====================

class TestBitsoBalances:
    """Tests para obtencion de balances."""

    @pytest.mark.asyncio
    async def test_get_balance_success(self, bitso_service, mock_balances_response):
        """Debe obtener balance correctamente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_balances_response
        ):
            balance = await bitso_service.get_balance("usdc")

            assert balance is not None
            assert balance.currency == "usdc"
            assert balance.total == Decimal("1000.00")
            assert balance.available == Decimal("950.00")
            assert balance.locked == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_get_all_balances(self, bitso_service, mock_balances_response):
        """Debe obtener todos los balances."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_balances_response
        ):
            balances = await bitso_service.get_balances()

            assert len(balances) == 2
            assert any(b.currency == "usdc" for b in balances)
            assert any(b.currency == "mxn" for b in balances)

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, bitso_service, mock_balances_response):
        """Debe retornar None para moneda inexistente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_balances_response
        ):
            balance = await bitso_service.get_balance("btc")

            assert balance is None


# ==================== TESTS: Ordenes ====================

class TestBitsoOrders:
    """Tests para colocacion de ordenes."""

    @pytest.mark.asyncio
    async def test_place_market_order(self, bitso_service, mock_order_response):
        """Debe colocar orden market correctamente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_order_response
        ):
            order = await bitso_service.place_order(
                book=BitsoBook.USDC_MXN,
                side=BitsoOrderSide.SELL,
                order_type=BitsoOrderType.MARKET,
                major=Decimal("100")
            )

            assert order is not None
            assert order.oid == "abc123def456"
            assert order.status == BitsoOrderStatus.COMPLETED
            assert order.side == BitsoOrderSide.SELL

    @pytest.mark.asyncio
    async def test_place_order_validation_zero_amount(self, bitso_service):
        """Debe rechazar orden con monto cero."""
        with pytest.raises(BitsoError) as exc_info:
            await bitso_service.place_order(
                book=BitsoBook.USDC_MXN,
                side=BitsoOrderSide.SELL,
                order_type=BitsoOrderType.MARKET,
                major=Decimal("0")
            )

        assert "mayor a cero" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_place_order_validation_no_amount(self, bitso_service):
        """Debe rechazar orden sin monto."""
        with pytest.raises(BitsoError):
            await bitso_service.place_order(
                book=BitsoBook.USDC_MXN,
                side=BitsoOrderSide.SELL,
                order_type=BitsoOrderType.MARKET,
            )


# ==================== TESTS: Conversion ====================

class TestBitsoConversion:
    """Tests para conversion USDC -> MXN."""

    @pytest.mark.asyncio
    async def test_convert_to_mxn_success(self, bitso_service):
        """Debe convertir USDC a MXN correctamente."""
        mock_ticker = {
            "success": True,
            "payload": {
                "book": "usdc_mxn",
                "bid": "17.30",
                "ask": "17.40",
                "last": "17.35",
                "volume": "1000000",
                "high": "17.50",
                "low": "17.20"
            }
        }

        mock_order = {
            "success": True,
            "payload": {
                "oid": "conv123",
                "book": "usdc_mxn",
                "side": "sell",
                "type": "market",
                "status": "completed",
                "original_amount": "100.00",
                "unfilled_amount": "0.00",
                "created_at": "2024-01-15T10:30:00+00:00"
            }
        }

        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            side_effect=[mock_ticker, mock_order]
        ):
            result = await bitso_service.convert_to_mxn(Decimal("100"))

            assert result.success is True
            assert result.from_currency == "usdc"
            assert result.to_currency == "mxn"
            assert result.from_amount == Decimal("100")
            # to_amount ~ 100 * 17.30 = 1730 MXN
            assert result.to_amount > Decimal("1700")

    @pytest.mark.asyncio
    async def test_convert_to_mxn_insufficient_funds(self, bitso_service):
        """Debe manejar fondos insuficientes."""
        mock_error = {
            "success": False,
            "error": {
                "code": "0301",
                "message": "Insufficient funds"
            }
        }

        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            side_effect=BitsoInsufficientFundsError("Fondos insuficientes")
        ):
            with pytest.raises(BitsoInsufficientFundsError):
                await bitso_service.convert_to_mxn(Decimal("100000"))


# ==================== TESTS: Retiros SPEI ====================

class TestBitsoSPEIWithdrawal:
    """Tests para retiros SPEI."""

    @pytest.mark.asyncio
    async def test_withdraw_spei_success(self, bitso_service, mock_withdrawal_response):
        """Debe procesar retiro SPEI correctamente."""
        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            return_value=mock_withdrawal_response
        ):
            withdrawal = await bitso_service.withdraw_spei(
                amount=Decimal("17300"),
                clabe="012180015678912345",
                beneficiary_name="JUAN PEREZ",
                notes_ref="PAGO REMESA"
            )

            assert withdrawal is not None
            assert withdrawal.wid == "xyz789"
            assert withdrawal.status == BitsoWithdrawalStatus.PENDING
            assert withdrawal.currency == "mxn"
            assert withdrawal.method == "spei"

    @pytest.mark.asyncio
    async def test_withdraw_spei_invalid_clabe(self, bitso_service):
        """Debe rechazar CLABE invalida."""
        with pytest.raises(BitsoError) as exc_info:
            await bitso_service.withdraw_spei(
                amount=Decimal("1000"),
                clabe="12345",  # Muy corta
                beneficiary_name="JUAN PEREZ"
            )

        assert "clabe" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_withdraw_spei_below_minimum(self, bitso_service):
        """Debe rechazar monto menor al minimo."""
        with pytest.raises(BitsoError) as exc_info:
            await bitso_service.withdraw_spei(
                amount=Decimal("5"),  # Menor a 10 MXN
                clabe="012180015678912345",
                beneficiary_name="JUAN PEREZ"
            )

        assert "minimo" in str(exc_info.value).lower()


# ==================== TESTS: Flujo Completo ====================

class TestBitsoFullFlow:
    """Tests para flujo completo USDC -> MXN -> SPEI."""

    @pytest.mark.asyncio
    async def test_usdc_to_bank_account(self, bitso_service):
        """Debe completar flujo USDC -> cuenta bancaria."""
        mock_ticker = {
            "success": True,
            "payload": {
                "book": "usdc_mxn",
                "bid": "17.30",
                "ask": "17.40",
                "last": "17.35",
                "volume": "1000000",
                "high": "17.50",
                "low": "17.20"
            }
        }

        mock_order = {
            "success": True,
            "payload": {
                "oid": "full123",
                "book": "usdc_mxn",
                "side": "sell",
                "type": "market",
                "status": "completed",
                "original_amount": "100.00",
                "unfilled_amount": "0.00",
                "created_at": "2024-01-15T10:30:00+00:00"
            }
        }

        mock_withdrawal = {
            "success": True,
            "payload": {
                "wid": "full_wd_456",
                "status": "pending",
                "currency": "mxn",
                "method": "spei",
                "amount": "1725.00",
                "fee": "0.00",
                "created_at": "2024-01-15T10:35:00+00:00"
            }
        }

        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            side_effect=[mock_ticker, mock_order, mock_withdrawal]
        ):
            result = await bitso_service.usdc_to_bank_account(
                amount_usdc=Decimal("100"),
                clabe="012180015678912345",
                beneficiary_name="JUAN PEREZ",
                notes_ref="REMESA FRC-123"
            )

            assert result["success"] is True
            assert result["conversion"]["order_id"] == "full123"
            assert result["withdrawal"]["wid"] == "full_wd_456"


# ==================== TESTS: Manejo de Errores ====================

class TestBitsoErrorHandling:
    """Tests para manejo de errores."""

    @pytest.mark.asyncio
    async def test_api_error_response(self, bitso_service):
        """Debe manejar errores de API correctamente."""
        mock_error = {
            "success": False,
            "error": {
                "code": "0101",
                "message": "Invalid API key"
            }
        }

        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            side_effect=BitsoAPIError("Invalid API key", "0101")
        ):
            with pytest.raises(BitsoAPIError) as exc_info:
                await bitso_service.get_ticker("usdc_mxn")

            assert exc_info.value.code == "0101"

    @pytest.mark.asyncio
    async def test_network_timeout(self, bitso_service):
        """Debe manejar timeout de red."""
        import asyncio

        with patch.object(
            bitso_service, '_make_request',
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError()
        ):
            with pytest.raises(BitsoError):
                await bitso_service.get_ticker("usdc_mxn")


# ==================== TESTS: Schemas ====================

class TestBitsoSchemas:
    """Tests para schemas de Bitso."""

    def test_ticker_spread_calculation(self):
        """Spread de ticker debe calcularse correctamente."""
        ticker = BitsoTicker(
            book="usdc_mxn",
            volume=Decimal("1000000"),
            high=Decimal("17.50"),
            low=Decimal("17.20"),
            last=Decimal("17.35"),
            bid=Decimal("17.30"),
            ask=Decimal("17.40")
        )

        assert ticker.spread == Decimal("0.10")
        assert ticker.spread_percentage > Decimal("0")
        assert ticker.spread_percentage < Decimal("1")  # Menos de 1%

    def test_order_fill_percentage(self):
        """Porcentaje de llenado debe calcularse correctamente."""
        # Orden completamente ejecutada
        order_full = BitsoOrder(
            oid="123",
            book="usdc_mxn",
            side=BitsoOrderSide.SELL,
            type=BitsoOrderType.MARKET,
            status=BitsoOrderStatus.COMPLETED,
            original_amount=Decimal("100"),
            unfilled_amount=Decimal("0"),
            created_at=datetime.utcnow()
        )
        assert order_full.fill_percentage == Decimal("100")
        assert order_full.filled_amount == Decimal("100")

        # Orden parcialmente ejecutada
        order_partial = BitsoOrder(
            oid="456",
            book="usdc_mxn",
            side=BitsoOrderSide.BUY,
            type=BitsoOrderType.LIMIT,
            status=BitsoOrderStatus.PARTIALLY_FILLED,
            original_amount=Decimal("100"),
            unfilled_amount=Decimal("25"),
            price=Decimal("17.50"),
            created_at=datetime.utcnow()
        )
        assert order_partial.fill_percentage == Decimal("75")
        assert order_partial.filled_amount == Decimal("75")

    def test_spei_withdrawal_request_validation(self):
        """Solicitud de retiro SPEI debe validar CLABE."""
        # CLABE valida
        request = SPEIWithdrawalRequest(
            amount=Decimal("1000"),
            clabe="012180015678912345",
            beneficiary_name="JUAN PEREZ"
        )
        assert request.clabe == "012180015678912345"

        # CLABE invalida (no numerica)
        with pytest.raises(ValueError):
            SPEIWithdrawalRequest(
                amount=Decimal("1000"),
                clabe="01218001567891234A",
                beneficiary_name="JUAN PEREZ"
            )

    def test_place_order_request_validation(self):
        """Solicitud de orden debe validar montos."""
        # Monto valido
        request = PlaceOrderRequest(
            book=BitsoBook.USDC_MXN,
            side=BitsoOrderSide.SELL,
            type=BitsoOrderType.MARKET,
            major=Decimal("100")
        )
        assert request.major == Decimal("100")

        # Monto negativo
        with pytest.raises(ValueError):
            PlaceOrderRequest(
                book=BitsoBook.USDC_MXN,
                side=BitsoOrderSide.SELL,
                type=BitsoOrderType.MARKET,
                major=Decimal("-100")
            )
