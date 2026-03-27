"""
Tests para el servicio de tasas de cambio.

Cubre:
- Obtencion de tasas desde Bitso
- Cache Redis
- Cotizaciones de conversion
- Cross-rates
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import json

from app.services.exchange_rate_service import (
    ExchangeRateService,
    ExchangeRate,
    ConversionQuote,
    RateSource,
    CurrencyPair,
    get_exchange_rate_service,
    get_usdc_mxn_rate,
    convert_usdc_to_mxn,
)


# ==================== FIXTURES ====================

@pytest.fixture
def exchange_service():
    """Servicio de tasas de cambio para tests."""
    service = ExchangeRateService()
    return service


@pytest.fixture
def mock_rate():
    """Tasa de cambio mock."""
    now = datetime.utcnow()
    return ExchangeRate(
        pair="usdc_mxn",
        bid=Decimal("17.30"),
        ask=Decimal("17.40"),
        mid=Decimal("17.35"),
        spread=Decimal("0.10"),
        spread_percentage=Decimal("0.58"),
        source=RateSource.BITSO,
        timestamp=now,
        expires_at=now + timedelta(seconds=30),
        cached=False,
    )


@pytest.fixture
def mock_redis():
    """Mock de cliente Redis."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    return redis_mock


# ==================== TESTS: ExchangeRate Model ====================

class TestExchangeRateModel:
    """Tests para el modelo ExchangeRate."""

    def test_is_expired_false(self, mock_rate):
        """Tasa no expirada debe retornar False."""
        assert mock_rate.is_expired is False

    def test_is_expired_true(self):
        """Tasa expirada debe retornar True."""
        now = datetime.utcnow()
        rate = ExchangeRate(
            pair="usdc_mxn",
            bid=Decimal("17.30"),
            ask=Decimal("17.40"),
            mid=Decimal("17.35"),
            spread=Decimal("0.10"),
            spread_percentage=Decimal("0.58"),
            source=RateSource.BITSO,
            timestamp=now - timedelta(minutes=5),
            expires_at=now - timedelta(minutes=1),
            cached=False,
        )
        assert rate.is_expired is True

    def test_to_dict_serialization(self, mock_rate):
        """Serializacion a dict debe ser correcta."""
        data = mock_rate.to_dict()

        assert data["pair"] == "usdc_mxn"
        assert data["bid"] == "17.30"
        assert data["ask"] == "17.40"
        assert data["mid"] == "17.35"
        assert data["source"] == "bitso"
        assert "timestamp" in data
        assert "expires_at" in data

    def test_from_dict_deserialization(self, mock_rate):
        """Deserializacion desde dict debe ser correcta."""
        data = mock_rate.to_dict()
        restored = ExchangeRate.from_dict(data)

        assert restored.pair == mock_rate.pair
        assert restored.bid == mock_rate.bid
        assert restored.ask == mock_rate.ask
        assert restored.mid == mock_rate.mid
        assert restored.source == mock_rate.source
        assert restored.cached is True  # from_dict siempre marca como cached


# ==================== TESTS: Get Rate ====================

class TestGetRate:
    """Tests para obtencion de tasas."""

    @pytest.mark.asyncio
    async def test_get_rate_from_bitso(self, exchange_service):
        """Debe obtener tasa de Bitso cuando no hay cache."""
        mock_ticker = MagicMock()
        mock_ticker.bid = Decimal("17.30")
        mock_ticker.ask = Decimal("17.40")

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=None
        ):
            with patch.object(
                exchange_service, '_fetch_from_bitso',
                new_callable=AsyncMock,
                return_value=MagicMock(
                    pair="usdc_mxn",
                    bid=Decimal("17.30"),
                    ask=Decimal("17.40"),
                    mid=Decimal("17.35"),
                    source=RateSource.BITSO,
                    is_expired=False,
                )
            ) as mock_fetch:
                rate = await exchange_service.get_rate(CurrencyPair.USDC_MXN)

                mock_fetch.assert_called_once_with("usdc_mxn")
                assert rate is not None

    @pytest.mark.asyncio
    async def test_get_rate_from_cache(self, exchange_service, mock_rate, mock_redis):
        """Debe usar cache cuando esta disponible."""
        # Simular rate en cache
        mock_redis.get = AsyncMock(return_value=json.dumps(mock_rate.to_dict()))

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            rate = await exchange_service.get_rate(CurrencyPair.USDC_MXN)

            assert rate is not None
            assert rate.cached is True
            assert rate.pair == "usdc_mxn"

    @pytest.mark.asyncio
    async def test_get_rate_force_refresh(self, exchange_service, mock_rate, mock_redis):
        """Force refresh debe ignorar cache."""
        mock_redis.get = AsyncMock(return_value=json.dumps(mock_rate.to_dict()))

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            with patch.object(
                exchange_service, '_fetch_rate_from_api',
                new_callable=AsyncMock,
                return_value=mock_rate
            ) as mock_fetch:
                rate = await exchange_service.get_rate(
                    CurrencyPair.USDC_MXN,
                    force_refresh=True
                )

                mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rate_usdc_usd_stable(self, exchange_service):
        """USDC/USD debe ser siempre ~1:1."""
        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=None
        ):
            rate = await exchange_service.get_rate(CurrencyPair.USDC_USD)

            assert rate is not None
            assert rate.mid == Decimal("1.0")
            assert rate.source == RateSource.INTERNAL


# ==================== TESTS: Conversion Quote ====================

class TestConversionQuote:
    """Tests para cotizaciones de conversion."""

    @pytest.mark.asyncio
    async def test_get_conversion_quote_usdc_mxn(self, exchange_service, mock_rate):
        """Debe calcular cotizacion USDC -> MXN correctamente."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mock_rate
        ):
            quote = await exchange_service.get_conversion_quote(
                from_currency="usdc",
                to_currency="mxn",
                amount=Decimal("100"),
                include_fee=True
            )

            assert quote is not None
            assert quote.from_currency == "usdc"
            assert quote.to_currency == "mxn"
            assert quote.from_amount == Decimal("100")
            # 100 * 17.30 (bid) = 1730 MXN bruto
            assert quote.to_amount == Decimal("1730.00")
            # Fee = 0.5% de 1730 = 8.65
            assert quote.fee > Decimal("0")
            # Net amount = 1730 - fee
            assert quote.net_amount < quote.to_amount

    @pytest.mark.asyncio
    async def test_get_conversion_quote_without_fee(self, exchange_service, mock_rate):
        """Cotizacion sin fee debe tener net_amount = to_amount."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mock_rate
        ):
            quote = await exchange_service.get_conversion_quote(
                from_currency="usdc",
                to_currency="mxn",
                amount=Decimal("100"),
                include_fee=False
            )

            assert quote.fee == Decimal("0")
            assert quote.net_amount == quote.to_amount

    @pytest.mark.asyncio
    async def test_get_conversion_quote_inverse(self, exchange_service, mock_rate):
        """Debe manejar conversion inversa (MXN -> USDC)."""
        # Crear rate MXN/USD
        mxn_usd_rate = ExchangeRate(
            pair="mxn_usd",
            bid=Decimal("0.0575"),
            ask=Decimal("0.0580"),
            mid=Decimal("0.0577"),
            spread=Decimal("0.0005"),
            spread_percentage=Decimal("0.87"),
            source=RateSource.INTERNAL,
            timestamp=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            cached=False,
        )

        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mxn_usd_rate
        ):
            quote = await exchange_service.get_conversion_quote(
                from_currency="mxn",
                to_currency="usd",
                amount=Decimal("1000"),
                include_fee=True
            )

            assert quote is not None
            assert quote.from_currency == "mxn"
            assert quote.to_currency == "usd"
            # 1000 MXN * 0.0575 = ~57.50 USD
            assert quote.to_amount > Decimal("50")
            assert quote.to_amount < Decimal("60")

    @pytest.mark.asyncio
    async def test_get_conversion_quote_minimum_fee(self, exchange_service, mock_rate):
        """Fee debe respetar minimo de $0.01."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mock_rate
        ):
            # Monto muy pequeno donde 0.5% seria < $0.01
            quote = await exchange_service.get_conversion_quote(
                from_currency="usdc",
                to_currency="mxn",
                amount=Decimal("0.10"),  # 10 centavos
                include_fee=True
            )

            assert quote.fee >= Decimal("0.01")


# ==================== TESTS: Cross Rates ====================

class TestCrossRates:
    """Tests para tasas cruzadas."""

    @pytest.mark.asyncio
    async def test_cross_rate_cop_mxn(self, exchange_service):
        """Debe calcular cross-rate COP -> MXN via USD."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=None  # No hay rate directo
        ):
            rate = await exchange_service._get_cross_rate("cop", "mxn")

            assert rate is not None
            assert rate.source == RateSource.INTERNAL
            # COP/MXN deberia ser muy pequeno (1 COP = ~0.004 MXN)
            assert rate.mid > Decimal("0")
            assert rate.mid < Decimal("1")

    @pytest.mark.asyncio
    async def test_cross_rate_unsupported(self, exchange_service):
        """Debe retornar None para monedas no soportadas."""
        rate = await exchange_service._get_cross_rate("xyz", "abc")
        assert rate is None


# ==================== TESTS: Cache Operations ====================

class TestCacheOperations:
    """Tests para operaciones de cache."""

    @pytest.mark.asyncio
    async def test_save_to_cache(self, exchange_service, mock_rate, mock_redis):
        """Debe guardar tasa en cache."""
        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            result = await exchange_service._save_to_cache(
                "fincore:exchange_rate:usdc_mxn",
                mock_rate
            )

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_from_cache_miss(self, exchange_service, mock_redis):
        """Debe retornar None cuando no hay cache."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            result = await exchange_service._get_from_cache(
                "fincore:exchange_rate:usdc_mxn"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_clear_cache_specific(self, exchange_service, mock_redis):
        """Debe limpiar cache de par especifico."""
        mock_redis.delete = AsyncMock(return_value=1)

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            count = await exchange_service.clear_cache(CurrencyPair.USDC_MXN)

            assert count == 1
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache_all(self, exchange_service, mock_redis):
        """Debe limpiar todo el cache."""
        mock_redis.keys = AsyncMock(return_value=[
            "fincore:exchange_rate:usdc_mxn",
            "fincore:exchange_rate:btc_mxn"
        ])
        mock_redis.delete = AsyncMock(return_value=2)

        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            return_value=mock_redis
        ):
            count = await exchange_service.clear_cache()

            assert count == 2


# ==================== TESTS: Batch Operations ====================

class TestBatchOperations:
    """Tests para operaciones batch."""

    @pytest.mark.asyncio
    async def test_get_all_rates(self, exchange_service, mock_rate):
        """Debe obtener todas las tasas disponibles."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mock_rate
        ):
            rates = await exchange_service.get_all_rates()

            assert len(rates) > 0
            assert "usdc_mxn" in rates

    @pytest.mark.asyncio
    async def test_refresh_all_rates(self, exchange_service, mock_rate):
        """Debe refrescar todas las tasas."""
        with patch.object(
            exchange_service, 'get_rate',
            new_callable=AsyncMock,
            return_value=mock_rate
        ) as mock_get:
            rates = await exchange_service.refresh_all_rates()

            # Debe llamar con force_refresh=True
            for call in mock_get.call_args_list:
                _, kwargs = call
                assert kwargs.get('force_refresh') is True


# ==================== TESTS: Utility Functions ====================

class TestUtilityFunctions:
    """Tests para funciones de utilidad."""

    @pytest.mark.asyncio
    async def test_get_usdc_mxn_rate(self):
        """Convenience function debe retornar tasa USDC/MXN."""
        mock_rate = ExchangeRate(
            pair="usdc_mxn",
            bid=Decimal("17.30"),
            ask=Decimal("17.40"),
            mid=Decimal("17.35"),
            spread=Decimal("0.10"),
            spread_percentage=Decimal("0.58"),
            source=RateSource.BITSO,
            timestamp=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=30),
            cached=False,
        )

        with patch(
            'app.services.exchange_rate_service.get_exchange_rate_service',
            new_callable=AsyncMock
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate = AsyncMock(return_value=mock_rate)
            mock_get_service.return_value = mock_service

            rate = await get_usdc_mxn_rate()

            assert rate == Decimal("17.35")

    @pytest.mark.asyncio
    async def test_convert_usdc_to_mxn(self):
        """Convenience function debe retornar cotizacion."""
        mock_quote = ConversionQuote(
            from_currency="usdc",
            to_currency="mxn",
            from_amount=Decimal("100"),
            to_amount=Decimal("1730"),
            rate=Decimal("17.30"),
            inverse_rate=Decimal("0.0578"),
            fee=Decimal("8.65"),
            fee_percentage=Decimal("0.5"),
            net_amount=Decimal("1721.35"),
            source=RateSource.BITSO,
            expires_at=datetime.utcnow() + timedelta(seconds=30),
            quote_id="test123"
        )

        with patch(
            'app.services.exchange_rate_service.get_exchange_rate_service',
            new_callable=AsyncMock
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_conversion_quote = AsyncMock(return_value=mock_quote)
            mock_get_service.return_value = mock_service

            quote = await convert_usdc_to_mxn(Decimal("100"))

            assert quote is not None
            assert quote.from_amount == Decimal("100")
            assert quote.to_currency == "mxn"


# ==================== TESTS: Error Handling ====================

class TestErrorHandling:
    """Tests para manejo de errores."""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, exchange_service):
        """Debe funcionar sin Redis (fallback)."""
        with patch.object(
            exchange_service, '_get_redis',
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused")
        ):
            with patch.object(
                exchange_service, '_fetch_rate_from_api',
                new_callable=AsyncMock,
                return_value=MagicMock(
                    mid=Decimal("17.35"),
                    is_expired=False
                )
            ):
                rate = await exchange_service.get_rate(CurrencyPair.USDC_MXN)

                # Debe funcionar sin cache
                assert rate is not None

    @pytest.mark.asyncio
    async def test_api_failure_uses_expired_cache(self, exchange_service, mock_rate):
        """Debe usar cache expirado si API falla."""
        # Rate expirado en cache
        expired_rate = ExchangeRate(
            pair="usdc_mxn",
            bid=Decimal("17.30"),
            ask=Decimal("17.40"),
            mid=Decimal("17.35"),
            spread=Decimal("0.10"),
            spread_percentage=Decimal("0.58"),
            source=RateSource.BITSO,
            timestamp=datetime.utcnow() - timedelta(minutes=10),
            expires_at=datetime.utcnow() - timedelta(minutes=5),
            cached=True,
        )

        with patch.object(
            exchange_service, '_get_from_cache',
            new_callable=AsyncMock,
            return_value=expired_rate
        ):
            with patch.object(
                exchange_service, '_fetch_rate_from_api',
                new_callable=AsyncMock,
                return_value=None  # API falla
            ):
                rate = await exchange_service.get_rate(CurrencyPair.USDC_MXN)

                # Debe retornar rate expirado como fallback
                assert rate is not None
                assert rate.cached is True
