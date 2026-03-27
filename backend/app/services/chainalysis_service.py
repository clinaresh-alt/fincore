"""
Servicio de integracion con Chainalysis para analisis on-chain.

Chainalysis es el proveedor lider de compliance blockchain que permite:
- Screening de direcciones contra listas de sanciones (OFAC, ONU, etc.)
- Deteccion de exposicion a entidades de riesgo (mixers, darknet, ransomware)
- Analisis de clustering para identificar wallets relacionadas
- Trazabilidad de fondos (taint analysis)

Documentacion API: https://docs.chainalysis.com/

Alternativas soportadas:
- Elliptic (failover)
- TRM Labs (futuro)
"""
import logging
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.schemas.compliance_screening import (
    RiskLevel,
    RiskCategory,
    ScreeningStatus,
    ScreeningAction,
    BlockchainNetwork,
    RiskIndicator,
    ExposureDetail,
    AddressScreeningResponse,
)

logger = logging.getLogger(__name__)


class ChainalysisError(Exception):
    """Error base de Chainalysis."""
    pass


class ChainalysisAPIError(ChainalysisError):
    """Error de comunicacion con API."""
    def __init__(self, status_code: int, message: str, response_body: Optional[dict] = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Chainalysis API Error ({status_code}): {message}")


class ChainalysisRateLimitError(ChainalysisError):
    """Rate limit excedido."""
    pass


class ChainalysisTimeoutError(ChainalysisError):
    """Timeout en la solicitud."""
    pass


@dataclass
class ChainalysisConfig:
    """Configuracion del cliente Chainalysis."""
    api_key: str
    api_url: str = "https://api.chainalysis.com/api"
    kyt_api_url: str = "https://api.chainalysis.com/api/kyt/v2"
    sanctions_api_url: str = "https://api.chainalysis.com/api/sanctions/v1"
    timeout_seconds: int = 30
    max_retries: int = 3
    cache_ttl_seconds: int = 3600  # 1 hora


class ChainalysisService:
    """
    Cliente para la API de Chainalysis.

    Implementa:
    - KYT (Know Your Transaction) para screening de direcciones
    - Sanctions API para verificacion contra listas de sanciones
    - Address clustering para identificar wallets relacionadas

    Uso:
        service = ChainalysisService()
        result = await service.screen_address(
            address="0x742d35Cc...",
            network=BlockchainNetwork.POLYGON
        )
        if result.risk_level == RiskLevel.HIGH:
            # Bloquear transaccion
    """

    # Mapeo de redes a identificadores de Chainalysis
    NETWORK_MAPPING = {
        BlockchainNetwork.POLYGON: "POLYGON",
        BlockchainNetwork.ETHEREUM: "ETHEREUM",
        BlockchainNetwork.ARBITRUM: "ARBITRUM",
        BlockchainNetwork.BASE: "BASE",
        BlockchainNetwork.BITCOIN: "BITCOIN",
        BlockchainNetwork.TRON: "TRON",
    }

    # Mapeo de categorias de Chainalysis a nuestras categorias
    CATEGORY_MAPPING = {
        "sanctions": RiskCategory.SANCTIONS,
        "darknet market": RiskCategory.DARKNET_MARKET,
        "mixer": RiskCategory.MIXER,
        "ransomware": RiskCategory.RANSOMWARE,
        "stolen funds": RiskCategory.STOLEN_FUNDS,
        "terrorism financing": RiskCategory.TERRORISM,
        "scam": RiskCategory.SCAM,
        "child abuse material": RiskCategory.CHILD_EXPLOITATION,
        "high risk exchange": RiskCategory.HIGH_RISK_EXCHANGE,
        "gambling": RiskCategory.GAMBLING,
        "illicit actor": RiskCategory.FRAUD,
        "fraud shop": RiskCategory.FRAUD,
    }

    def __init__(self, config: Optional[ChainalysisConfig] = None):
        """
        Inicializa el servicio de Chainalysis.

        Args:
            config: Configuracion opcional. Si no se provee, usa settings.
        """
        self.config = config or ChainalysisConfig(
            api_key=getattr(settings, 'CHAINALYSIS_API_KEY', ''),
            api_url=getattr(settings, 'CHAINALYSIS_API_URL', 'https://api.chainalysis.com/api'),
            kyt_api_url=getattr(settings, 'CHAINALYSIS_KYT_URL', 'https://api.chainalysis.com/api/kyt/v2'),
            sanctions_api_url=getattr(settings, 'CHAINALYSIS_SANCTIONS_URL', 'https://api.chainalysis.com/api/sanctions/v1'),
            timeout_seconds=int(getattr(settings, 'CHAINALYSIS_TIMEOUT', 30)),
        )

        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, Tuple[datetime, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtiene o crea el cliente HTTP."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers={
                    "Token": self.config.api_key,
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

    def _get_cache_key(self, address: str, network: BlockchainNetwork) -> str:
        """Genera clave de cache para una direccion."""
        return hashlib.sha256(f"{address}:{network.value}".encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[AddressScreeningResponse]:
        """Obtiene resultado cacheado si existe y no ha expirado."""
        if cache_key in self._cache:
            cached_time, result = self._cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.config.cache_ttl_seconds):
                logger.debug(f"Cache hit para screening: {cache_key[:16]}...")
                return result
            else:
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, result: AddressScreeningResponse):
        """Guarda resultado en cache."""
        self._cache[cache_key] = (datetime.utcnow(), result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Realiza solicitud HTTP a la API de Chainalysis.

        Args:
            method: Metodo HTTP (GET, POST, etc.)
            url: URL completa del endpoint
            json_data: Cuerpo de la solicitud (para POST/PUT)
            params: Parametros de query string

        Returns:
            Respuesta JSON parseada

        Raises:
            ChainalysisAPIError: Error de la API
            ChainalysisRateLimitError: Rate limit excedido
            ChainalysisTimeoutError: Timeout
        """
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
            )

            # Manejar rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise ChainalysisRateLimitError(f"Rate limit excedido. Retry after: {retry_after}s")

            # Manejar errores
            if response.status_code >= 400:
                error_body = None
                try:
                    error_body = response.json()
                except Exception:
                    pass
                raise ChainalysisAPIError(
                    status_code=response.status_code,
                    message=response.text[:200],
                    response_body=error_body,
                )

            return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout en Chainalysis API: {e}")
            raise ChainalysisTimeoutError(f"Timeout: {e}")

    # ============ KYT API (Know Your Transaction) ============

    async def register_address(
        self,
        address: str,
        network: BlockchainNetwork,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Registra una direccion en Chainalysis para monitoreo continuo.

        Args:
            address: Direccion blockchain
            network: Red (polygon, ethereum, etc.)
            user_id: ID interno del usuario

        Returns:
            ID de registro en Chainalysis
        """
        url = f"{self.config.kyt_api_url}/users"
        chain = self.NETWORK_MAPPING.get(network, "ETHEREUM")

        payload = {
            "userId": user_id or f"fincore_{address[:10]}",
            "address": address,
            "asset": chain,
        }

        response = await self._make_request("POST", url, json_data=payload)
        return response.get("userId", "")

    async def screen_address(
        self,
        address: str,
        network: BlockchainNetwork,
        user_id: Optional[str] = None,
        amount_usd: Optional[Decimal] = None,
        direction: str = "inbound",
        use_cache: bool = True,
    ) -> AddressScreeningResponse:
        """
        Realiza screening completo de una direccion blockchain.

        Combina:
        1. KYT API para riesgo transaccional
        2. Sanctions API para verificacion OFAC
        3. Clustering para entidades relacionadas

        Args:
            address: Direccion a analizar
            network: Red blockchain
            user_id: ID del usuario asociado
            amount_usd: Monto de la transaccion en USD
            direction: "inbound" (recibiendo) o "outbound" (enviando)
            use_cache: Si usar cache

        Returns:
            AddressScreeningResponse con analisis completo
        """
        screening_id = hashlib.sha256(
            f"{address}:{network.value}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:24]

        # Verificar cache
        if use_cache:
            cache_key = self._get_cache_key(address, network)
            cached = self._get_cached_result(cache_key)
            if cached:
                # Actualizar screening_id para que sea unico
                cached.screening_id = screening_id
                return cached

        logger.info(f"Iniciando screening de direccion: {address[:10]}... en {network.value}")

        try:
            # 1. Verificar contra sanciones (prioritario)
            sanctions_result = await self._check_sanctions(address)

            if sanctions_result.get("is_sanctioned", False):
                # Direccion sancionada - rechazar inmediatamente
                result = self._create_sanctions_response(
                    screening_id=screening_id,
                    address=address,
                    network=network,
                    sanctions_data=sanctions_result,
                )
                if use_cache:
                    self._set_cache(self._get_cache_key(address, network), result)
                return result

            # 2. Obtener analisis de riesgo KYT
            kyt_result = await self._get_address_risk(address, network, user_id, direction)

            # 3. Obtener exposicion a entidades
            exposure_result = await self._get_address_exposure(address, network)

            # 4. Combinar resultados y calcular score
            result = self._build_screening_response(
                screening_id=screening_id,
                address=address,
                network=network,
                kyt_data=kyt_result,
                exposure_data=exposure_result,
                amount_usd=amount_usd,
            )

            # Guardar en cache
            if use_cache:
                self._set_cache(self._get_cache_key(address, network), result)

            logger.info(
                f"Screening completado para {address[:10]}...: "
                f"score={result.risk_score}, level={result.risk_level.value}"
            )

            return result

        except ChainalysisError as e:
            logger.error(f"Error en screening: {e}")
            # Retornar resultado de error que requiere revision manual
            return self._create_error_response(
                screening_id=screening_id,
                address=address,
                network=network,
                error=str(e),
            )

    async def _check_sanctions(self, address: str) -> dict:
        """
        Verifica direccion contra la Sanctions API.

        Returns:
            Dict con is_sanctioned, programs, etc.
        """
        url = f"{self.config.sanctions_api_url}/address/{address}"

        try:
            response = await self._make_request("GET", url)

            identifications = response.get("identifications", [])
            is_sanctioned = len(identifications) > 0

            programs = []
            entities = []
            for ident in identifications:
                programs.extend(ident.get("programs", []))
                if "entity" in ident:
                    entities.append(ident["entity"])

            return {
                "is_sanctioned": is_sanctioned,
                "programs": list(set(programs)),
                "entities": entities,
                "raw_response": response,
            }

        except ChainalysisAPIError as e:
            if e.status_code == 404:
                # No encontrada = no sancionada
                return {"is_sanctioned": False, "programs": [], "entities": []}
            raise

    async def _get_address_risk(
        self,
        address: str,
        network: BlockchainNetwork,
        user_id: Optional[str],
        direction: str,
    ) -> dict:
        """
        Obtiene analisis de riesgo KYT para una direccion.
        """
        chain = self.NETWORK_MAPPING.get(network, "ETHEREUM")

        # Registrar transferencia para analisis
        url = f"{self.config.kyt_api_url}/users/{user_id or 'default'}/transfers"

        payload = {
            "network": chain,
            "asset": "USDC",  # Por defecto analizamos USDC
            "transferReference": f"scr_{datetime.utcnow().timestamp()}",
            "direction": direction.upper(),
            "transferTimestamp": datetime.utcnow().isoformat() + "Z",
            "assetAmount": 1.0,  # Monto dummy para analisis
            "outputAddress" if direction == "outbound" else "inputAddress": address,
        }

        try:
            response = await self._make_request("POST", url, json_data=payload)

            # Obtener alertas
            external_id = response.get("externalId", "")
            if external_id:
                alerts = await self._get_transfer_alerts(external_id)
                response["alerts"] = alerts

            return response

        except ChainalysisAPIError as e:
            if e.status_code == 404:
                return {"risk_score": 0, "alerts": []}
            raise

    async def _get_transfer_alerts(self, external_id: str) -> List[dict]:
        """Obtiene alertas de una transferencia."""
        url = f"{self.config.kyt_api_url}/transfers/{external_id}/alerts"

        try:
            response = await self._make_request("GET", url)
            return response.get("alerts", [])
        except Exception:
            return []

    async def _get_address_exposure(
        self,
        address: str,
        network: BlockchainNetwork,
    ) -> dict:
        """
        Obtiene exposicion de la direccion a entidades de riesgo.
        """
        chain = self.NETWORK_MAPPING.get(network, "ETHEREUM")
        url = f"{self.config.kyt_api_url}/addresses/{address}/exposure"

        params = {"network": chain}

        try:
            response = await self._make_request("GET", url, params=params)
            return response
        except ChainalysisAPIError as e:
            if e.status_code == 404:
                return {"direct": [], "indirect": []}
            raise

    def _create_sanctions_response(
        self,
        screening_id: str,
        address: str,
        network: BlockchainNetwork,
        sanctions_data: dict,
    ) -> AddressScreeningResponse:
        """Crea respuesta para direccion sancionada."""
        programs = sanctions_data.get("programs", [])
        entities = sanctions_data.get("entities", [])

        indicators = [
            RiskIndicator(
                category=RiskCategory.SANCTIONS,
                severity=100,
                description=f"Direccion en lista de sanciones: {', '.join(programs)}",
                source="chainalysis_sanctions",
                confidence=1.0,
            )
        ]

        return AddressScreeningResponse(
            screening_id=screening_id,
            address=address,
            network=network,
            status=ScreeningStatus.COMPLETED,
            risk_score=100,
            risk_level=RiskLevel.SEVERE,
            risk_indicators=indicators,
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.BLOCK,
            action_reason=f"Direccion sancionada por: {', '.join(programs)}",
            address_metadata={"sanction_entities": entities},
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=True,
            requires_sar=True,
            pep_match=False,
        )

    def _create_error_response(
        self,
        screening_id: str,
        address: str,
        network: BlockchainNetwork,
        error: str,
    ) -> AddressScreeningResponse:
        """Crea respuesta de error que requiere revision manual."""
        return AddressScreeningResponse(
            screening_id=screening_id,
            address=address,
            network=network,
            status=ScreeningStatus.FAILED,
            risk_score=50,  # Score medio por precaucion
            risk_level=RiskLevel.MEDIUM,
            risk_indicators=[
                RiskIndicator(
                    category=RiskCategory.UNKNOWN,
                    severity=50,
                    description=f"Error en screening: {error}",
                    source="chainalysis",
                    confidence=0.0,
                )
            ],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.REVIEW,
            action_reason=f"Screening fallido, requiere revision manual: {error}",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

    def _build_screening_response(
        self,
        screening_id: str,
        address: str,
        network: BlockchainNetwork,
        kyt_data: dict,
        exposure_data: dict,
        amount_usd: Optional[Decimal],
    ) -> AddressScreeningResponse:
        """
        Construye la respuesta de screening combinando todos los datos.
        """
        # Procesar alertas KYT
        risk_indicators: List[RiskIndicator] = []
        alerts = kyt_data.get("alerts", [])

        for alert in alerts:
            category_str = alert.get("category", "").lower()
            category = self.CATEGORY_MAPPING.get(category_str, RiskCategory.UNKNOWN)

            risk_indicators.append(
                RiskIndicator(
                    category=category,
                    severity=alert.get("severity", 50),
                    description=alert.get("message", "Alerta detectada"),
                    source="chainalysis_kyt",
                    confidence=alert.get("confidence", 0.8),
                )
            )

        # Procesar exposicion directa
        direct_exposure: List[ExposureDetail] = []
        for exp in exposure_data.get("direct", []):
            category_str = exp.get("category", "").lower()
            category = self.CATEGORY_MAPPING.get(category_str, RiskCategory.UNKNOWN)

            direct_exposure.append(
                ExposureDetail(
                    entity_name=exp.get("name", "Unknown"),
                    entity_type=exp.get("type", "unknown"),
                    category=category,
                    exposure_amount_usd=Decimal(str(exp.get("amount", 0))),
                    exposure_percentage=exp.get("percentage", 0),
                    transaction_count=exp.get("txCount", 0),
                )
            )

            # Agregar como indicador de riesgo
            risk_indicators.append(
                RiskIndicator(
                    category=category,
                    severity=min(int(exp.get("percentage", 0)), 100),
                    description=f"Exposicion directa a {exp.get('name', 'Unknown')}",
                    source="chainalysis_exposure",
                    confidence=0.9,
                )
            )

        # Procesar exposicion indirecta
        indirect_exposure: List[ExposureDetail] = []
        for exp in exposure_data.get("indirect", []):
            category_str = exp.get("category", "").lower()
            category = self.CATEGORY_MAPPING.get(category_str, RiskCategory.UNKNOWN)

            indirect_exposure.append(
                ExposureDetail(
                    entity_name=exp.get("name", "Unknown"),
                    entity_type=exp.get("type", "unknown"),
                    category=category,
                    exposure_amount_usd=Decimal(str(exp.get("amount", 0))),
                    exposure_percentage=exp.get("percentage", 0),
                    transaction_count=exp.get("txCount", 0),
                )
            )

        # Calcular score de riesgo combinado
        risk_score = self._calculate_combined_risk_score(
            risk_indicators, direct_exposure, indirect_exposure, amount_usd
        )

        # Determinar nivel de riesgo
        risk_level = self._score_to_risk_level(risk_score)

        # Determinar accion recomendada
        recommended_action, action_reason = self._determine_action(
            risk_score, risk_level, risk_indicators
        )

        # Determinar si requiere SAR
        requires_sar = risk_score >= 70 or any(
            ind.category in [
                RiskCategory.SANCTIONS,
                RiskCategory.TERRORISM,
                RiskCategory.RANSOMWARE,
                RiskCategory.CHILD_EXPLOITATION,
            ]
            for ind in risk_indicators
        )

        return AddressScreeningResponse(
            screening_id=screening_id,
            address=address,
            network=network,
            status=ScreeningStatus.COMPLETED,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_indicators=risk_indicators,
            direct_exposure=direct_exposure,
            indirect_exposure=indirect_exposure,
            recommended_action=recommended_action,
            action_reason=action_reason,
            address_metadata=kyt_data.get("metadata", {}),
            cluster_info=kyt_data.get("cluster", None),
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=requires_sar,
            pep_match=False,
        )

    def _calculate_combined_risk_score(
        self,
        indicators: List[RiskIndicator],
        direct_exposure: List[ExposureDetail],
        indirect_exposure: List[ExposureDetail],
        amount_usd: Optional[Decimal],
    ) -> int:
        """
        Calcula score de riesgo combinado (0-100).

        Ponderacion:
        - Indicadores de riesgo: 50%
        - Exposicion directa: 30%
        - Exposicion indirecta: 10%
        - Factor de monto: 10%
        """
        # Score base de indicadores
        if indicators:
            indicator_score = sum(ind.severity * ind.confidence for ind in indicators) / len(indicators)
        else:
            indicator_score = 0

        # Score de exposicion directa
        if direct_exposure:
            direct_score = min(
                sum(exp.exposure_percentage for exp in direct_exposure),
                100
            )
        else:
            direct_score = 0

        # Score de exposicion indirecta (menos peso)
        if indirect_exposure:
            indirect_score = min(
                sum(exp.exposure_percentage * 0.5 for exp in indirect_exposure),
                50
            )
        else:
            indirect_score = 0

        # Factor de monto (transacciones grandes tienen mas riesgo)
        amount_factor = 0
        if amount_usd:
            if amount_usd > 10000:
                amount_factor = 20
            elif amount_usd > 5000:
                amount_factor = 10
            elif amount_usd > 1000:
                amount_factor = 5

        # Combinar con ponderacion
        combined_score = (
            indicator_score * 0.5 +
            direct_score * 0.3 +
            indirect_score * 0.1 +
            amount_factor
        )

        return min(int(combined_score), 100)

    def _score_to_risk_level(self, score: int) -> RiskLevel:
        """Convierte score numerico a nivel de riesgo."""
        if score >= 90:
            return RiskLevel.SEVERE
        elif score >= 70:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 10:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _determine_action(
        self,
        score: int,
        level: RiskLevel,
        indicators: List[RiskIndicator],
    ) -> Tuple[ScreeningAction, str]:
        """Determina la accion recomendada basada en el analisis."""
        # Categorias que siempre bloquean
        blocking_categories = {
            RiskCategory.SANCTIONS,
            RiskCategory.TERRORISM,
            RiskCategory.CHILD_EXPLOITATION,
            RiskCategory.RANSOMWARE,
        }

        for ind in indicators:
            if ind.category in blocking_categories:
                return (
                    ScreeningAction.BLOCK,
                    f"Categoria de riesgo critico detectada: {ind.category.value}"
                )

        # Basado en score
        if score >= 90:
            return (
                ScreeningAction.BLOCK,
                "Score de riesgo severo (>=90)"
            )
        elif score >= 70:
            return (
                ScreeningAction.REJECT,
                "Score de riesgo alto (>=70)"
            )
        elif score >= 40:
            return (
                ScreeningAction.REVIEW,
                "Score de riesgo medio - requiere revision manual"
            )
        elif score >= 20:
            return (
                ScreeningAction.ENHANCED_DUE_DILIGENCE,
                "Riesgo bajo pero detectable - due diligence mejorado recomendado"
            )
        else:
            return (
                ScreeningAction.APPROVE,
                "Sin indicadores de riesgo significativos"
            )

    # ============ Metodos de monitoreo continuo ============

    async def get_ongoing_alerts(
        self,
        user_id: str,
        since: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Obtiene alertas de monitoreo continuo para un usuario.
        """
        url = f"{self.config.kyt_api_url}/users/{user_id}/alerts"

        params = {}
        if since:
            params["createdAt_gte"] = since.isoformat() + "Z"

        try:
            response = await self._make_request("GET", url, params=params)
            return response.get("alerts", [])
        except ChainalysisAPIError as e:
            if e.status_code == 404:
                return []
            raise

    async def acknowledge_alert(self, alert_id: str, notes: str) -> bool:
        """Marca una alerta como reconocida."""
        url = f"{self.config.kyt_api_url}/alerts/{alert_id}/acknowledge"

        payload = {"notes": notes}

        try:
            await self._make_request("POST", url, json_data=payload)
            return True
        except ChainalysisAPIError:
            return False


# ============ Singleton y Factory ============

_chainalysis_service: Optional[ChainalysisService] = None


def get_chainalysis_service() -> ChainalysisService:
    """Obtiene instancia singleton del servicio."""
    global _chainalysis_service
    if _chainalysis_service is None:
        _chainalysis_service = ChainalysisService()
    return _chainalysis_service


async def cleanup_chainalysis_service():
    """Limpia recursos del servicio."""
    global _chainalysis_service
    if _chainalysis_service:
        await _chainalysis_service.close()
        _chainalysis_service = None
