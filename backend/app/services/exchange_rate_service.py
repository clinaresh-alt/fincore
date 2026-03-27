"""
Servicio de Tasas de Cambio con Cache Redis.

Proporciona cotizaciones en tiempo real para conversiones:
- Cripto a Fiat (USDC -> MXN via Bitso)
- Fiat a USD (para cotizaciones internas)
- Cache en Redis para reducir llamadas API

Integraciones:
- Bitso: USDC/MXN, BTC/MXN, ETH/MXN (principal)
- Banxico: USD/MXN tipo de cambio oficial (referencia)
- CoinGecko: Precios cripto globales (fallback)
"""
import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateSource(str, Enum):
    """Fuente de la tasa de cambio."""
    BITSO = "bitso"
    BANXICO = "banxico"
    COINGECKO = "coingecko"
    INTERNAL = "internal"
    CACHED = "cached"


class CurrencyPair(str, Enum):
    """Pares de monedas soportados."""
    USDC_MXN = "usdc_mxn"
    USDT_MXN = "usdt_mxn"
    BTC_MXN = "btc_mxn"
    ETH_MXN = "eth_mxn"
    USD_MXN = "usd_mxn"
    # Cross rates
    USDC_USD = "usdc_usd"
    MXN_USD = "mxn_usd"


@dataclass
class ExchangeRate:
    """Tasa de cambio con metadata."""
    pair: str
    bid: Decimal  # Precio de compra
    ask: Decimal  # Precio de venta
    mid: Decimal  # Precio medio
    spread: Decimal  # Diferencia bid-ask
    spread_percentage: Decimal
    source: RateSource
    timestamp: datetime
    expires_at: datetime
    cached: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "mid": str(self.mid),
            "spread": str(self.spread),
            "spread_percentage": str(self.spread_percentage),
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "cached": self.cached,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExchangeRate":
        return cls(
            pair=data["pair"],
            bid=Decimal(data["bid"]),
            ask=Decimal(data["ask"]),
            mid=Decimal(data["mid"]),
            spread=Decimal(data["spread"]),
            spread_percentage=Decimal(data["spread_percentage"]),
            source=RateSource(data["source"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            cached=True,
        )


@dataclass
class ConversionQuote:
    """Cotizacion de conversion."""
    from_currency: str
    to_currency: str
    from_amount: Decimal
    to_amount: Decimal
    rate: Decimal
    inverse_rate: Decimal
    fee: Decimal
    fee_percentage: Decimal
    net_amount: Decimal  # Monto final despues de fees
    source: RateSource
    expires_at: datetime
    quote_id: str


class ExchangeRateService:
    """
    Servicio de tasas de cambio con cache Redis.

    Flujo:
    1. Buscar en cache Redis
    2. Si expiro, obtener de Bitso API
    3. Almacenar en cache
    4. Retornar tasa

    Cache TTL por defecto: 30 segundos (tasas son volatiles)
    """

    # Configuracion de cache
    DEFAULT_CACHE_TTL = 30  # segundos
    FIAT_CACHE_TTL = 300  # 5 minutos para fiat
    CACHE_KEY_PREFIX = "fincore:exchange_rate:"

    # Fees de conversion
    CONVERSION_FEE_PERCENT = Decimal("0.005")  # 0.5%
    MIN_CONVERSION_FEE = Decimal("0.01")  # $0.01 USD minimo

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self._bitso_service = None
        self._connected = False

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Obtiene conexion Redis con lazy init."""
        if self.redis is None:
            try:
                self.redis = await aioredis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                    encoding="utf-8",
                    decode_responses=True,
                )
                self._connected = True
            except Exception as e:
                logger.warning(f"No se pudo conectar a Redis: {e}")
                self._connected = False
                return None
        return self.redis

    def _get_bitso_service(self):
        """Lazy init del servicio Bitso."""
        if self._bitso_service is None:
            from app.services.bitso_service import BitsoService, BitsoConfig
            config = BitsoConfig(
                api_key=settings.BITSO_API_KEY,
                api_secret=settings.BITSO_API_SECRET,
                use_production=settings.BITSO_USE_PRODUCTION,
            )
            self._bitso_service = BitsoService(config)
        return self._bitso_service

    # ============ Core Rate Methods ============

    async def get_rate(
        self,
        pair: CurrencyPair,
        force_refresh: bool = False,
    ) -> Optional[ExchangeRate]:
        """
        Obtiene tasa de cambio para un par.

        Args:
            pair: Par de monedas (ej: USDC_MXN)
            force_refresh: Ignorar cache y obtener de API

        Returns:
            ExchangeRate o None si no disponible
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}{pair.value}"

        # 1. Intentar obtener de cache
        if not force_refresh:
            cached_rate = await self._get_from_cache(cache_key)
            if cached_rate and not cached_rate.is_expired:
                return cached_rate

        # 2. Obtener de API segun el par
        rate = await self._fetch_rate_from_api(pair)
        if rate is None:
            # Si fallo API, retornar cache expirado si existe
            if not force_refresh:
                cached_rate = await self._get_from_cache(cache_key)
                if cached_rate:
                    logger.warning(f"Usando tasa expirada para {pair.value}")
                    return cached_rate
            return None

        # 3. Guardar en cache
        await self._save_to_cache(cache_key, rate)

        return rate

    async def _fetch_rate_from_api(self, pair: CurrencyPair) -> Optional[ExchangeRate]:
        """Obtiene tasa de API externa segun el par."""
        try:
            # Pares de Bitso (cripto/MXN)
            bitso_pairs = {
                CurrencyPair.USDC_MXN: "usdc_mxn",
                CurrencyPair.USDT_MXN: "usdt_mxn",
                CurrencyPair.BTC_MXN: "btc_mxn",
                CurrencyPair.ETH_MXN: "eth_mxn",
            }

            if pair in bitso_pairs:
                return await self._fetch_from_bitso(bitso_pairs[pair])

            # USD/MXN - usar Bitso o fallback interno
            if pair == CurrencyPair.USD_MXN:
                return await self._get_usd_mxn_rate()

            # USDC/USD - siempre 1:1 (stablecoin)
            if pair == CurrencyPair.USDC_USD:
                return self._create_stable_rate(pair.value, Decimal("1.0"))

            # MXN/USD - inverso de USD/MXN
            if pair == CurrencyPair.MXN_USD:
                usd_mxn = await self.get_rate(CurrencyPair.USD_MXN)
                if usd_mxn:
                    inverse = Decimal("1") / usd_mxn.mid
                    return self._create_rate_from_mid(
                        pair.value,
                        inverse,
                        RateSource.INTERNAL,
                        self.FIAT_CACHE_TTL,
                    )

            return None

        except Exception as e:
            logger.error(f"Error obteniendo tasa para {pair.value}: {e}")
            return None

    async def _fetch_from_bitso(self, book: str) -> Optional[ExchangeRate]:
        """Obtiene tasa de Bitso."""
        try:
            bitso = self._get_bitso_service()
            ticker = await bitso.get_ticker(book)

            if ticker is None:
                return None

            now = datetime.utcnow()
            spread = ticker.ask - ticker.bid
            mid = (ticker.ask + ticker.bid) / 2
            spread_pct = (spread / mid * 100) if mid > 0 else Decimal("0")

            return ExchangeRate(
                pair=book,
                bid=ticker.bid,
                ask=ticker.ask,
                mid=mid.quantize(Decimal("0.0001")),
                spread=spread.quantize(Decimal("0.0001")),
                spread_percentage=spread_pct.quantize(Decimal("0.01")),
                source=RateSource.BITSO,
                timestamp=now,
                expires_at=now + timedelta(seconds=self.DEFAULT_CACHE_TTL),
                cached=False,
            )

        except Exception as e:
            logger.error(f"Error obteniendo tasa de Bitso {book}: {e}")
            return None

    async def _get_usd_mxn_rate(self) -> ExchangeRate:
        """
        Obtiene tasa USD/MXN.

        Estrategia:
        1. Calcular de USDC/MXN de Bitso (USDC ≈ 1 USD)
        2. Fallback: tasa fija de referencia
        """
        # Intentar obtener de USDC/MXN (USDC ≈ $1 USD)
        usdc_rate = await self.get_rate(CurrencyPair.USDC_MXN)
        if usdc_rate:
            # USDC/MXN es practicamente igual a USD/MXN
            return ExchangeRate(
                pair=CurrencyPair.USD_MXN.value,
                bid=usdc_rate.bid,
                ask=usdc_rate.ask,
                mid=usdc_rate.mid,
                spread=usdc_rate.spread,
                spread_percentage=usdc_rate.spread_percentage,
                source=RateSource.BITSO,  # Derivado de Bitso
                timestamp=usdc_rate.timestamp,
                expires_at=usdc_rate.expires_at,
                cached=usdc_rate.cached,
            )

        # Fallback: tasa fija de referencia
        logger.warning("Usando tasa USD/MXN de fallback")
        return self._create_rate_from_mid(
            CurrencyPair.USD_MXN.value,
            Decimal("17.50"),  # Tasa de referencia aproximada
            RateSource.INTERNAL,
            self.FIAT_CACHE_TTL,
        )

    def _create_stable_rate(self, pair: str, rate: Decimal) -> ExchangeRate:
        """Crea tasa para stablecoins (spread minimo)."""
        now = datetime.utcnow()
        spread = Decimal("0.001")  # 0.1% spread para stables
        bid = rate - (spread / 2)
        ask = rate + (spread / 2)

        return ExchangeRate(
            pair=pair,
            bid=bid,
            ask=ask,
            mid=rate,
            spread=spread,
            spread_percentage=Decimal("0.1"),
            source=RateSource.INTERNAL,
            timestamp=now,
            expires_at=now + timedelta(seconds=3600),  # 1 hora para stables
            cached=False,
        )

    def _create_rate_from_mid(
        self,
        pair: str,
        mid: Decimal,
        source: RateSource,
        ttl: int,
    ) -> ExchangeRate:
        """Crea ExchangeRate a partir de precio medio."""
        now = datetime.utcnow()
        spread_pct = Decimal("0.005")  # 0.5% spread por defecto
        half_spread = mid * spread_pct / 2

        return ExchangeRate(
            pair=pair,
            bid=(mid - half_spread).quantize(Decimal("0.0001")),
            ask=(mid + half_spread).quantize(Decimal("0.0001")),
            mid=mid.quantize(Decimal("0.0001")),
            spread=(mid * spread_pct).quantize(Decimal("0.0001")),
            spread_percentage=(spread_pct * 100).quantize(Decimal("0.01")),
            source=source,
            timestamp=now,
            expires_at=now + timedelta(seconds=ttl),
            cached=False,
        )

    # ============ Conversion Methods ============

    async def get_conversion_quote(
        self,
        from_currency: str,
        to_currency: str,
        amount: Decimal,
        include_fee: bool = True,
    ) -> Optional[ConversionQuote]:
        """
        Obtiene cotizacion para conversion de monedas.

        Args:
            from_currency: Moneda origen (ej: "usdc")
            to_currency: Moneda destino (ej: "mxn")
            amount: Monto a convertir
            include_fee: Incluir fee de plataforma

        Returns:
            ConversionQuote con todos los detalles
        """
        # Normalizar monedas
        from_cur = from_currency.lower()
        to_cur = to_currency.lower()

        # Determinar par y direccion
        pair_str = f"{from_cur}_{to_cur}"
        inverse_pair_str = f"{to_cur}_{from_cur}"

        # Buscar par directo
        rate = None
        inverse = False

        try:
            pair_enum = CurrencyPair(pair_str)
            rate = await self.get_rate(pair_enum)
        except ValueError:
            # Intentar par inverso
            try:
                pair_enum = CurrencyPair(inverse_pair_str)
                rate = await self.get_rate(pair_enum)
                inverse = True
            except ValueError:
                # Par no soportado, intentar cross-rate
                rate = await self._get_cross_rate(from_cur, to_cur)
                if rate:
                    pair_str = f"{from_cur}_{to_cur}"

        if rate is None:
            logger.warning(f"No se encontro tasa para {from_cur}/{to_cur}")
            return None

        # Calcular conversion
        if inverse:
            # Usar ask para vender (usuario recibe menos)
            conversion_rate = Decimal("1") / rate.ask
            result_amount = amount * conversion_rate
        else:
            # Usar bid para vender cripto (usuario recibe MXN)
            conversion_rate = rate.bid
            result_amount = amount * conversion_rate

        # Calcular fee
        fee = Decimal("0")
        if include_fee:
            fee = max(
                result_amount * self.CONVERSION_FEE_PERCENT,
                self.MIN_CONVERSION_FEE
            ).quantize(Decimal("0.01"))

        net_amount = (result_amount - fee).quantize(Decimal("0.01"))

        # Generar quote ID
        import secrets
        quote_id = secrets.token_urlsafe(16)

        return ConversionQuote(
            from_currency=from_cur,
            to_currency=to_cur,
            from_amount=amount,
            to_amount=result_amount.quantize(Decimal("0.01")),
            rate=conversion_rate.quantize(Decimal("0.0001")),
            inverse_rate=(Decimal("1") / conversion_rate).quantize(Decimal("0.000001")),
            fee=fee,
            fee_percentage=self.CONVERSION_FEE_PERCENT * 100,
            net_amount=net_amount,
            source=rate.source,
            expires_at=rate.expires_at,
            quote_id=quote_id,
        )

    async def _get_cross_rate(
        self,
        from_currency: str,
        to_currency: str,
    ) -> Optional[ExchangeRate]:
        """
        Calcula tasa cruzada usando USD como intermediario.

        Ej: COP -> MXN = COP -> USD -> MXN
        """
        # Por ahora solo soportamos monedas que pasan por USD
        # TODO: Implementar mas pares

        # Tasas internas aproximadas a USD
        rates_to_usd = {
            "mxn": Decimal("0.058"),
            "cop": Decimal("0.00025"),
            "clp": Decimal("0.0011"),
            "pen": Decimal("0.27"),
            "brl": Decimal("0.20"),
            "ars": Decimal("0.0012"),
            "eur": Decimal("1.08"),
            "usd": Decimal("1.0"),
            "usdc": Decimal("1.0"),
            "usdt": Decimal("1.0"),
        }

        from_rate = rates_to_usd.get(from_currency)
        to_rate = rates_to_usd.get(to_currency)

        if from_rate is None or to_rate is None:
            return None

        cross_rate = from_rate / to_rate

        return self._create_rate_from_mid(
            f"{from_currency}_{to_currency}",
            cross_rate,
            RateSource.INTERNAL,
            self.FIAT_CACHE_TTL,
        )

    # ============ Cache Methods ============

    async def _get_from_cache(self, key: str) -> Optional[ExchangeRate]:
        """Obtiene tasa de cache Redis."""
        try:
            redis = await self._get_redis()
            if redis is None:
                return None

            data = await redis.get(key)
            if data:
                return ExchangeRate.from_dict(json.loads(data))
            return None

        except Exception as e:
            logger.warning(f"Error leyendo cache: {e}")
            return None

    async def _save_to_cache(self, key: str, rate: ExchangeRate) -> bool:
        """Guarda tasa en cache Redis."""
        try:
            redis = await self._get_redis()
            if redis is None:
                return False

            ttl = int((rate.expires_at - datetime.utcnow()).total_seconds())
            if ttl <= 0:
                ttl = self.DEFAULT_CACHE_TTL

            await redis.setex(
                key,
                ttl,
                json.dumps(rate.to_dict()),
            )
            return True

        except Exception as e:
            logger.warning(f"Error guardando en cache: {e}")
            return False

    async def clear_cache(self, pair: Optional[CurrencyPair] = None) -> int:
        """
        Limpia cache de tasas.

        Args:
            pair: Par especifico o None para todos

        Returns:
            Numero de keys eliminadas
        """
        try:
            redis = await self._get_redis()
            if redis is None:
                return 0

            if pair:
                key = f"{self.CACHE_KEY_PREFIX}{pair.value}"
                return await redis.delete(key)
            else:
                # Eliminar todas las tasas
                pattern = f"{self.CACHE_KEY_PREFIX}*"
                keys = await redis.keys(pattern)
                if keys:
                    return await redis.delete(*keys)
                return 0

        except Exception as e:
            logger.error(f"Error limpiando cache: {e}")
            return 0

    # ============ Batch Methods ============

    async def get_all_rates(self) -> Dict[str, ExchangeRate]:
        """Obtiene todas las tasas disponibles."""
        rates = {}
        pairs = [
            CurrencyPair.USDC_MXN,
            CurrencyPair.USDT_MXN,
            CurrencyPair.USD_MXN,
            CurrencyPair.BTC_MXN,
            CurrencyPair.ETH_MXN,
        ]

        # Obtener en paralelo
        tasks = [self.get_rate(pair) for pair in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for pair, result in zip(pairs, results):
            if isinstance(result, ExchangeRate):
                rates[pair.value] = result
            elif isinstance(result, Exception):
                logger.warning(f"Error obteniendo {pair.value}: {result}")

        return rates

    async def refresh_all_rates(self) -> Dict[str, ExchangeRate]:
        """Refresca todas las tasas (ignora cache)."""
        rates = {}
        pairs = [
            CurrencyPair.USDC_MXN,
            CurrencyPair.USDT_MXN,
            CurrencyPair.USD_MXN,
        ]

        for pair in pairs:
            rate = await self.get_rate(pair, force_refresh=True)
            if rate:
                rates[pair.value] = rate

        return rates


# ============ Factory Function ============

_exchange_rate_service: Optional[ExchangeRateService] = None


async def get_exchange_rate_service() -> ExchangeRateService:
    """Factory function para obtener instancia singleton."""
    global _exchange_rate_service
    if _exchange_rate_service is None:
        _exchange_rate_service = ExchangeRateService()
    return _exchange_rate_service


# ============ Utility Functions ============

async def get_usdc_mxn_rate() -> Optional[Decimal]:
    """Convenience function para obtener tasa USDC/MXN."""
    service = await get_exchange_rate_service()
    rate = await service.get_rate(CurrencyPair.USDC_MXN)
    return rate.mid if rate else None


async def convert_usdc_to_mxn(amount: Decimal) -> Optional[ConversionQuote]:
    """Convenience function para cotizar USDC a MXN."""
    service = await get_exchange_rate_service()
    return await service.get_conversion_quote("usdc", "mxn", amount)
