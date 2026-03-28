"""
Servicio de Monitoreo de Transacciones en Tiempo Real.

Integración con:
- Tenderly: Monitoreo de transacciones y simulación
- Forta: Detección de amenazas en tiempo real
- Alertas personalizadas via webhooks
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.core.config import settings


class AlertSeverity(str, Enum):
    """Niveles de severidad para alertas."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Tipos de alertas."""
    LARGE_TRANSACTION = "large_transaction"
    UNUSUAL_GAS = "unusual_gas"
    CONTRACT_INTERACTION = "contract_interaction"
    FAILED_TRANSACTION = "failed_transaction"
    REENTRANCY_DETECTED = "reentrancy_detected"
    FLASH_LOAN = "flash_loan"
    PRICE_MANIPULATION = "price_manipulation"
    ADMIN_FUNCTION_CALL = "admin_function_call"
    BLACKLISTED_ADDRESS = "blacklisted_address"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"


@dataclass
class Alert:
    """Estructura de una alerta."""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    value: Optional[Decimal] = None
    network: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


class MonitoringRule(BaseModel):
    """Regla de monitoreo personalizada."""
    id: str
    name: str
    description: str
    enabled: bool = True

    # Condiciones
    min_value: Optional[Decimal] = None  # Valor mínimo en ETH/MATIC
    max_gas_price: Optional[int] = None  # Gas price máximo en gwei
    contract_addresses: list[str] = []  # Contratos a monitorear
    function_signatures: list[str] = []  # Funciones específicas
    blacklisted_addresses: list[str] = []  # Direcciones bloqueadas

    # Acciones
    alert_severity: AlertSeverity = AlertSeverity.MEDIUM
    notify_webhook: Optional[str] = None
    auto_pause: bool = False  # Activar circuit breaker automáticamente


class TransactionMonitoringService:
    """
    Servicio de monitoreo de transacciones en tiempo real.

    Capacidades:
    1. Monitoreo de transacciones grandes
    2. Detección de patrones sospechosos
    3. Alertas en tiempo real
    4. Integración con Tenderly/Forta
    5. Circuit breaker automático
    """

    def __init__(self):
        self.rules: dict[str, MonitoringRule] = {}
        self.alerts: list[Alert] = []
        self.alert_handlers: list[Callable] = []
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None

        # Configuración por defecto
        self.default_thresholds = {
            "large_transaction_eth": Decimal("10"),  # 10 ETH
            "large_transaction_matic": Decimal("10000"),  # 10,000 MATIC
            "max_gas_gwei": 500,  # 500 gwei
            "max_failed_tx_per_hour": 10,
        }

        # Cache de transacciones recientes para detección de patrones
        self._recent_transactions: dict[str, list] = {}
        self._failed_tx_count: dict[str, int] = {}

        # Direcciones conocidas como maliciosas (ejemplo)
        self.known_malicious_addresses: set[str] = set()

        # API clients
        self.tenderly_api_key = getattr(settings, 'TENDERLY_API_KEY', None)
        self.forta_api_key = getattr(settings, 'FORTA_API_KEY', None)

        self._setup_default_rules()

    def _setup_default_rules(self):
        """Configura reglas de monitoreo por defecto."""

        # Regla: Transacciones grandes
        self.add_rule(MonitoringRule(
            id="rule_large_tx",
            name="Transacciones Grandes",
            description="Alerta cuando una transacción supera el umbral de valor",
            min_value=self.default_thresholds["large_transaction_eth"],
            alert_severity=AlertSeverity.HIGH,
        ))

        # Regla: Gas excesivo
        self.add_rule(MonitoringRule(
            id="rule_high_gas",
            name="Gas Excesivo",
            description="Alerta cuando el gas price es muy alto",
            max_gas_price=self.default_thresholds["max_gas_gwei"],
            alert_severity=AlertSeverity.MEDIUM,
        ))

        # Regla: Funciones administrativas
        self.add_rule(MonitoringRule(
            id="rule_admin_functions",
            name="Funciones Administrativas",
            description="Monitorea llamadas a funciones de admin",
            function_signatures=[
                "0x8456cb59",  # pause()
                "0x3f4ba83a",  # unpause()
                "0x715018a6",  # renounceOwnership()
                "0xf2fde38b",  # transferOwnership(address)
                "0x2f2ff15d",  # grantRole(bytes32,address)
                "0xd547741f",  # revokeRole(bytes32,address)
            ],
            alert_severity=AlertSeverity.HIGH,
        ))

    def add_rule(self, rule: MonitoringRule) -> None:
        """Agrega una regla de monitoreo."""
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Elimina una regla de monitoreo."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False

    def register_alert_handler(self, handler: Callable) -> None:
        """Registra un handler para alertas."""
        self.alert_handlers.append(handler)

    async def _emit_alert(self, alert: Alert) -> None:
        """Emite una alerta a todos los handlers registrados."""
        self.alerts.append(alert)

        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Error en alert handler: {e}")

        # Enviar webhook si está configurado
        for rule in self.rules.values():
            if rule.notify_webhook:
                await self._send_webhook(rule.notify_webhook, alert)

    async def _send_webhook(self, url: str, alert: Alert) -> None:
        """Envía una alerta via webhook."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "alert_id": alert.id,
                    "type": alert.type.value,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "description": alert.description,
                    "transaction_hash": alert.transaction_hash,
                    "contract_address": alert.contract_address,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata,
                }
                await client.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando webhook: {e}")

    async def analyze_transaction(
        self,
        tx_hash: str,
        from_address: str,
        to_address: str,
        value: Decimal,
        gas_price: int,
        input_data: str,
        network: str = "ethereum",
    ) -> list[Alert]:
        """
        Analiza una transacción y genera alertas si es necesario.

        Args:
            tx_hash: Hash de la transacción
            from_address: Dirección origen
            to_address: Dirección destino
            value: Valor en ETH/MATIC
            gas_price: Gas price en gwei
            input_data: Datos de la transacción (hex)
            network: Red blockchain

        Returns:
            Lista de alertas generadas
        """
        alerts_generated: list[Alert] = []

        # Normalizar direcciones
        from_addr = from_address.lower()
        to_addr = to_address.lower() if to_address else ""

        # Obtener function signature (primeros 4 bytes)
        func_sig = input_data[:10] if input_data and len(input_data) >= 10 else ""

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            alert = await self._check_rule(
                rule=rule,
                tx_hash=tx_hash,
                from_addr=from_addr,
                to_addr=to_addr,
                value=value,
                gas_price=gas_price,
                func_sig=func_sig,
                network=network,
            )

            if alert:
                alerts_generated.append(alert)
                await self._emit_alert(alert)

                # Auto-pause si está configurado
                if rule.auto_pause:
                    await self._trigger_circuit_breaker(alert)

        # Verificar dirección blacklisted
        if from_addr in self.known_malicious_addresses or to_addr in self.known_malicious_addresses:
            alert = Alert(
                id=self._generate_alert_id(tx_hash, "blacklist"),
                type=AlertType.BLACKLISTED_ADDRESS,
                severity=AlertSeverity.CRITICAL,
                title="Dirección Maliciosa Detectada",
                description=f"Transacción involucra dirección conocida como maliciosa",
                transaction_hash=tx_hash,
                from_address=from_address,
                to_address=to_address,
                value=value,
                network=network,
            )
            alerts_generated.append(alert)
            await self._emit_alert(alert)

        # Guardar en cache para detección de patrones
        self._cache_transaction(from_addr, tx_hash)

        return alerts_generated

    async def _check_rule(
        self,
        rule: MonitoringRule,
        tx_hash: str,
        from_addr: str,
        to_addr: str,
        value: Decimal,
        gas_price: int,
        func_sig: str,
        network: str,
    ) -> Optional[Alert]:
        """Verifica si una transacción viola una regla."""

        # Check: Valor mínimo
        if rule.min_value and value >= rule.min_value:
            return Alert(
                id=self._generate_alert_id(tx_hash, rule.id),
                type=AlertType.LARGE_TRANSACTION,
                severity=rule.alert_severity,
                title=f"Transacción Grande: {value} ETH",
                description=f"Transacción supera umbral de {rule.min_value} ETH",
                transaction_hash=tx_hash,
                from_address=from_addr,
                to_address=to_addr,
                value=value,
                network=network,
                metadata={"rule_id": rule.id, "threshold": str(rule.min_value)},
            )

        # Check: Gas price máximo
        if rule.max_gas_price and gas_price > rule.max_gas_price:
            return Alert(
                id=self._generate_alert_id(tx_hash, rule.id),
                type=AlertType.UNUSUAL_GAS,
                severity=rule.alert_severity,
                title=f"Gas Excesivo: {gas_price} gwei",
                description=f"Gas price supera umbral de {rule.max_gas_price} gwei",
                transaction_hash=tx_hash,
                from_address=from_addr,
                to_address=to_addr,
                network=network,
                metadata={"rule_id": rule.id, "gas_price": gas_price},
            )

        # Check: Contratos específicos
        if rule.contract_addresses:
            if to_addr in [addr.lower() for addr in rule.contract_addresses]:
                return Alert(
                    id=self._generate_alert_id(tx_hash, rule.id),
                    type=AlertType.CONTRACT_INTERACTION,
                    severity=rule.alert_severity,
                    title=f"Interacción con Contrato Monitoreado",
                    description=f"Transacción hacia contrato en lista de monitoreo",
                    transaction_hash=tx_hash,
                    from_address=from_addr,
                    to_address=to_addr,
                    contract_address=to_addr,
                    network=network,
                    metadata={"rule_id": rule.id},
                )

        # Check: Funciones específicas
        if rule.function_signatures:
            if func_sig in rule.function_signatures:
                return Alert(
                    id=self._generate_alert_id(tx_hash, rule.id),
                    type=AlertType.ADMIN_FUNCTION_CALL,
                    severity=rule.alert_severity,
                    title=f"Llamada a Función Administrativa",
                    description=f"Función {func_sig} detectada",
                    transaction_hash=tx_hash,
                    from_address=from_addr,
                    to_address=to_addr,
                    network=network,
                    metadata={"rule_id": rule.id, "function_signature": func_sig},
                )

        # Check: Direcciones blacklisted
        if rule.blacklisted_addresses:
            blacklist_lower = [addr.lower() for addr in rule.blacklisted_addresses]
            if from_addr in blacklist_lower or to_addr in blacklist_lower:
                return Alert(
                    id=self._generate_alert_id(tx_hash, rule.id),
                    type=AlertType.BLACKLISTED_ADDRESS,
                    severity=AlertSeverity.CRITICAL,
                    title=f"Dirección Blacklisted Detectada",
                    description=f"Transacción involucra dirección en blacklist de la regla",
                    transaction_hash=tx_hash,
                    from_address=from_addr,
                    to_address=to_addr,
                    network=network,
                    metadata={"rule_id": rule.id},
                )

        return None

    def _generate_alert_id(self, tx_hash: str, rule_id: str) -> str:
        """Genera un ID único para una alerta."""
        data = f"{tx_hash}:{rule_id}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _cache_transaction(self, from_addr: str, tx_hash: str) -> None:
        """Cachea una transacción para detección de patrones."""
        if from_addr not in self._recent_transactions:
            self._recent_transactions[from_addr] = []

        self._recent_transactions[from_addr].append({
            "tx_hash": tx_hash,
            "timestamp": datetime.utcnow(),
        })

        # Limpiar transacciones antiguas (más de 1 hora)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self._recent_transactions[from_addr] = [
            tx for tx in self._recent_transactions[from_addr]
            if tx["timestamp"] > cutoff
        ]

    async def _trigger_circuit_breaker(self, alert: Alert) -> None:
        """Activa el circuit breaker automáticamente."""
        circuit_alert = Alert(
            id=self._generate_alert_id(alert.id, "circuit_breaker"),
            type=AlertType.CIRCUIT_BREAKER_TRIGGERED,
            severity=AlertSeverity.CRITICAL,
            title="Circuit Breaker Activado Automáticamente",
            description=f"Activado por alerta: {alert.title}",
            metadata={
                "trigger_alert_id": alert.id,
                "trigger_alert_type": alert.type.value,
            },
        )
        await self._emit_alert(circuit_alert)
        # TODO: Integrar con EmergencyControl.sol para pausar contratos

    async def detect_reentrancy_pattern(
        self,
        contract_address: str,
        recent_calls: list[dict],
    ) -> Optional[Alert]:
        """
        Detecta patrones de reentrancy basándose en llamadas recientes.

        Args:
            contract_address: Dirección del contrato
            recent_calls: Lista de llamadas recientes al contrato

        Returns:
            Alerta si se detecta patrón sospechoso
        """
        if len(recent_calls) < 3:
            return None

        # Buscar patrón: múltiples llamadas al mismo contrato en rápida sucesión
        # con valores similares (típico de reentrancy)
        time_window = timedelta(seconds=15)
        suspicious_calls = []

        for i, call in enumerate(recent_calls[:-1]):
            next_call = recent_calls[i + 1]
            time_diff = next_call.get("timestamp") - call.get("timestamp")

            if time_diff < time_window:
                if call.get("function") == next_call.get("function"):
                    suspicious_calls.append((call, next_call))

        if len(suspicious_calls) >= 2:
            return Alert(
                id=self._generate_alert_id(contract_address, "reentrancy"),
                type=AlertType.REENTRANCY_DETECTED,
                severity=AlertSeverity.CRITICAL,
                title="Posible Ataque de Reentrancy Detectado",
                description=f"Múltiples llamadas recursivas detectadas en {contract_address}",
                contract_address=contract_address,
                metadata={
                    "suspicious_calls_count": len(suspicious_calls),
                    "pattern": "recursive_calls",
                },
            )

        return None

    async def check_flash_loan_pattern(
        self,
        tx_hash: str,
        events: list[dict],
    ) -> Optional[Alert]:
        """
        Detecta patrones de flash loan.

        Args:
            tx_hash: Hash de la transacción
            events: Eventos emitidos en la transacción

        Returns:
            Alerta si se detecta flash loan sospechoso
        """
        flash_loan_signatures = [
            "FlashLoan",
            "FlashBorrow",
            "FlashMint",
        ]

        has_flash_loan = any(
            event.get("name") in flash_loan_signatures
            for event in events
        )

        if has_flash_loan:
            # Verificar si hay manipulación de precio en la misma tx
            swap_events = [e for e in events if "Swap" in e.get("name", "")]

            if len(swap_events) >= 3:  # Múltiples swaps sospechosos
                return Alert(
                    id=self._generate_alert_id(tx_hash, "flash_loan"),
                    type=AlertType.FLASH_LOAN,
                    severity=AlertSeverity.HIGH,
                    title="Flash Loan con Múltiples Swaps Detectado",
                    description=f"Posible ataque de manipulación de precio via flash loan",
                    transaction_hash=tx_hash,
                    metadata={
                        "swap_count": len(swap_events),
                        "events": [e.get("name") for e in events],
                    },
                )

        return None

    # ============ API Tenderly ============

    async def simulate_transaction_tenderly(
        self,
        network: str,
        from_address: str,
        to_address: str,
        value: int,
        data: str,
    ) -> dict[str, Any]:
        """
        Simula una transacción usando Tenderly API.

        Útil para:
        - Verificar resultado antes de enviar
        - Detectar reverts potenciales
        - Analizar gas usage
        """
        if not self.tenderly_api_key:
            return {"error": "Tenderly API key not configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tenderly.co/api/v1/simulate",
                    headers={
                        "X-Access-Key": self.tenderly_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "network_id": network,
                        "from": from_address,
                        "to": to_address,
                        "value": value,
                        "input": data,
                        "save": True,
                        "save_if_fails": True,
                    },
                    timeout=30,
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ============ API Forta ============

    async def get_forta_alerts(
        self,
        addresses: list[str],
        start_date: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Obtiene alertas de Forta para direcciones específicas.

        Forta es una red descentralizada de bots que monitorean
        actividad sospechosa en blockchain.
        """
        if not self.forta_api_key:
            return []

        try:
            start = start_date or (datetime.utcnow() - timedelta(days=7))

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.forta.network/graphql",
                    headers={
                        "Authorization": f"Bearer {self.forta_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": """
                            query alerts($addresses: [String!], $after: DateTime) {
                                alerts(
                                    addresses: $addresses,
                                    after: $after
                                ) {
                                    alerts {
                                        alertId
                                        severity
                                        name
                                        description
                                        protocol
                                        source {
                                            transactionHash
                                            block {
                                                number
                                            }
                                        }
                                    }
                                }
                            }
                        """,
                        "variables": {
                            "addresses": addresses,
                            "after": start.isoformat(),
                        },
                    },
                    timeout=30,
                )
                data = response.json()
                return data.get("data", {}).get("alerts", {}).get("alerts", [])
        except Exception as e:
            logger.error(f"Error fetching Forta alerts: {e}")
            return []

    # ============ Estadísticas ============

    def get_alert_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas de alertas."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        alerts_24h = [a for a in self.alerts if a.timestamp > last_24h]
        alerts_7d = [a for a in self.alerts if a.timestamp > last_7d]

        severity_counts = {s.value: 0 for s in AlertSeverity}
        type_counts = {t.value: 0 for t in AlertType}

        for alert in self.alerts:
            severity_counts[alert.severity.value] += 1
            type_counts[alert.type.value] += 1

        return {
            "total_alerts": len(self.alerts),
            "alerts_last_24h": len(alerts_24h),
            "alerts_last_7d": len(alerts_7d),
            "unresolved_alerts": len([a for a in self.alerts if not a.resolved]),
            "critical_alerts": severity_counts.get("critical", 0),
            "by_severity": severity_counts,
            "by_type": type_counts,
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
        }

    def get_recent_alerts(
        self,
        limit: int = 50,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
    ) -> list[Alert]:
        """Obtiene alertas recientes con filtros opcionales."""
        filtered = self.alerts

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if alert_type:
            filtered = [a for a in filtered if a.type == alert_type]

        # Ordenar por timestamp descendente
        sorted_alerts = sorted(filtered, key=lambda a: a.timestamp, reverse=True)

        return sorted_alerts[:limit]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Marca una alerta como reconocida."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Marca una alerta como resuelta."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False
