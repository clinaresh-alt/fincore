"""
Integración con Cloudflare WAF.
Verificación de headers de Cloudflare y rate limiting adicional.
"""
import logging
import os
import ipaddress
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from functools import lru_cache
import httpx

logger = logging.getLogger(__name__)


@dataclass
class WAFConfig:
    """Configuración de WAF."""
    # Cloudflare
    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""
    verify_cf_connecting_ip: bool = True

    # Rate Limiting (backup si Cloudflare falla)
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # IP blocking
    block_known_bad_ips: bool = True
    allow_private_ips: bool = False  # Para desarrollo

    # Headers requeridos de Cloudflare
    require_cf_headers: bool = True

    # Geo blocking (lista de países bloqueados)
    blocked_countries: List[str] = None

    @classmethod
    def from_env(cls) -> "WAFConfig":
        """Crea configuración desde variables de entorno."""
        blocked = os.getenv("WAF_BLOCKED_COUNTRIES", "")
        return cls(
            cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN", ""),
            cloudflare_zone_id=os.getenv("CLOUDFLARE_ZONE_ID", ""),
            verify_cf_connecting_ip=os.getenv(
                "WAF_VERIFY_CF_IP", "true"
            ).lower() == "true",
            rate_limit_requests=int(os.getenv("WAF_RATE_LIMIT_REQUESTS", "100")),
            rate_limit_window_seconds=int(
                os.getenv("WAF_RATE_LIMIT_WINDOW", "60")
            ),
            block_known_bad_ips=os.getenv(
                "WAF_BLOCK_BAD_IPS", "true"
            ).lower() == "true",
            allow_private_ips=os.getenv(
                "WAF_ALLOW_PRIVATE_IPS", "false"
            ).lower() == "true",
            require_cf_headers=os.getenv(
                "WAF_REQUIRE_CF_HEADERS", "true"
            ).lower() == "true",
            blocked_countries=blocked.split(",") if blocked else None,
        )


# IPs de Cloudflare (se actualiza periódicamente)
# https://www.cloudflare.com/ips/
CLOUDFLARE_IPV4_RANGES = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

CLOUDFLARE_IPV6_RANGES = [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]


@lru_cache(maxsize=1)
def get_cloudflare_networks() -> Set[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Obtiene las redes de Cloudflare (cacheado)."""
    networks = set()
    for cidr in CLOUDFLARE_IPV4_RANGES:
        networks.add(ipaddress.ip_network(cidr))
    for cidr in CLOUDFLARE_IPV6_RANGES:
        networks.add(ipaddress.ip_network(cidr))
    return networks


def is_cloudflare_ip(ip: str) -> bool:
    """Verifica si una IP pertenece a Cloudflare."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        for network in get_cloudflare_networks():
            if ip_obj in network:
                return True
        return False
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    """Verifica si es una IP privada."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback
    except ValueError:
        return False


class CloudflareWAF:
    """
    Integración con Cloudflare WAF.
    Proporciona verificación de headers, geo blocking y rate limiting.
    """

    def __init__(self, config: Optional[WAFConfig] = None):
        """
        Inicializa la integración WAF.

        Args:
            config: Configuración de WAF
        """
        self.config = config or WAFConfig.from_env()
        self._client: Optional[httpx.AsyncClient] = None

        # Rate limiting local (backup)
        self._request_counts: Dict[str, List[float]] = {}

        logger.info(
            f"CloudflareWAF initialized. "
            f"Verify CF IP: {self.config.verify_cf_connecting_ip}, "
            f"Require CF headers: {self.config.require_cf_headers}"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtiene el cliente HTTP para la API de Cloudflare."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.cloudflare.com/client/v4",
                headers={
                    "Authorization": f"Bearer {self.config.cloudflare_api_token}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
        return self._client

    def validate_request(
        self,
        remote_ip: str,
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Valida una request contra las reglas WAF.

        Args:
            remote_ip: IP del cliente (o proxy)
            headers: Headers de la request

        Returns:
            Dict con resultado de validación
        """
        result = {
            "allowed": True,
            "reason": None,
            "cf_ray": headers.get("cf-ray"),
            "cf_connecting_ip": headers.get("cf-connecting-ip"),
            "cf_ipcountry": headers.get("cf-ipcountry"),
            "client_ip": None,
        }

        # 1. Verificar si la request viene de Cloudflare
        if self.config.verify_cf_connecting_ip:
            if not is_cloudflare_ip(remote_ip):
                # Permitir IPs privadas en desarrollo
                if not (self.config.allow_private_ips and is_private_ip(remote_ip)):
                    result["allowed"] = False
                    result["reason"] = "request_not_from_cloudflare"
                    logger.warning(
                        f"Request not from Cloudflare: {remote_ip}"
                    )
                    return result

        # 2. Obtener IP real del cliente
        cf_connecting_ip = headers.get("cf-connecting-ip")
        x_forwarded_for = headers.get("x-forwarded-for", "").split(",")[0].strip()

        result["client_ip"] = cf_connecting_ip or x_forwarded_for or remote_ip

        # 3. Verificar headers requeridos de Cloudflare
        if self.config.require_cf_headers:
            required_headers = ["cf-ray", "cf-connecting-ip"]
            missing = [h for h in required_headers if h not in headers]
            if missing and not self.config.allow_private_ips:
                result["allowed"] = False
                result["reason"] = f"missing_cf_headers: {missing}"
                return result

        # 4. Geo blocking
        if self.config.blocked_countries:
            country = headers.get("cf-ipcountry", "").upper()
            if country in self.config.blocked_countries:
                result["allowed"] = False
                result["reason"] = f"country_blocked: {country}"
                logger.warning(f"Request blocked from country: {country}")
                return result

        # 5. Rate limiting local (backup)
        if not self._check_rate_limit(result["client_ip"]):
            result["allowed"] = False
            result["reason"] = "rate_limit_exceeded"
            return result

        return result

    def _check_rate_limit(self, client_ip: str) -> bool:
        """Verifica rate limit local (backup de Cloudflare)."""
        now = time.time()
        window_start = now - self.config.rate_limit_window_seconds

        # Limpiar entradas antiguas
        if client_ip in self._request_counts:
            self._request_counts[client_ip] = [
                t for t in self._request_counts[client_ip]
                if t > window_start
            ]
        else:
            self._request_counts[client_ip] = []

        # Verificar límite
        if len(self._request_counts[client_ip]) >= self.config.rate_limit_requests:
            return False

        # Registrar request
        self._request_counts[client_ip].append(now)
        return True

    async def create_firewall_rule(
        self,
        expression: str,
        action: str = "block",
        description: str = "",
    ) -> Optional[str]:
        """
        Crea una regla de firewall en Cloudflare.

        Args:
            expression: Expresión de la regla (Cloudflare filter expression)
            action: Acción (block, challenge, js_challenge, managed_challenge)
            description: Descripción de la regla

        Returns:
            ID de la regla creada o None si falla
        """
        if not self.config.cloudflare_api_token or not self.config.cloudflare_zone_id:
            logger.warning("Cloudflare API not configured")
            return None

        client = await self._get_client()

        # Primero crear el filtro
        filter_response = await client.post(
            f"/zones/{self.config.cloudflare_zone_id}/filters",
            json={
                "expression": expression,
                "description": description,
            },
        )

        if filter_response.status_code != 200:
            logger.error(
                f"Failed to create filter: {filter_response.text}"
            )
            return None

        filter_data = filter_response.json()
        filter_id = filter_data["result"][0]["id"]

        # Luego crear la regla de firewall
        rule_response = await client.post(
            f"/zones/{self.config.cloudflare_zone_id}/firewall/rules",
            json=[{
                "filter": {"id": filter_id},
                "action": action,
                "description": description,
            }],
        )

        if rule_response.status_code != 200:
            logger.error(
                f"Failed to create firewall rule: {rule_response.text}"
            )
            return None

        rule_data = rule_response.json()
        rule_id = rule_data["result"][0]["id"]

        logger.info(f"Created Cloudflare firewall rule: {rule_id}")
        return rule_id

    async def block_ip(
        self,
        ip: str,
        reason: str = "Blocked by FinCore",
    ) -> bool:
        """
        Bloquea una IP en Cloudflare.

        Args:
            ip: IP a bloquear
            reason: Razón del bloqueo

        Returns:
            True si fue exitoso
        """
        if not self.config.cloudflare_api_token or not self.config.cloudflare_zone_id:
            logger.warning("Cloudflare API not configured")
            return False

        client = await self._get_client()

        response = await client.post(
            f"/zones/{self.config.cloudflare_zone_id}/firewall/access_rules/rules",
            json={
                "mode": "block",
                "configuration": {
                    "target": "ip",
                    "value": ip,
                },
                "notes": reason,
            },
        )

        if response.status_code == 200:
            logger.info(f"Blocked IP in Cloudflare: {ip}")
            return True
        else:
            logger.error(f"Failed to block IP: {response.text}")
            return False

    async def get_security_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene eventos de seguridad de Cloudflare.

        Args:
            start_time: Inicio del período
            end_time: Fin del período
            limit: Máximo de eventos

        Returns:
            Lista de eventos de seguridad
        """
        if not self.config.cloudflare_api_token or not self.config.cloudflare_zone_id:
            return []

        client = await self._get_client()

        # Default: última hora
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            start_time = end_time - timedelta(hours=1)

        params = {
            "since": start_time.isoformat() + "Z",
            "until": end_time.isoformat() + "Z",
            "per_page": limit,
        }

        response = await client.get(
            f"/zones/{self.config.cloudflare_zone_id}/security/events",
            params=params,
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("result", [])
        else:
            logger.error(f"Failed to get security events: {response.text}")
            return []

    async def get_waf_rules(self) -> List[Dict[str, Any]]:
        """Obtiene las reglas WAF activas."""
        if not self.config.cloudflare_api_token or not self.config.cloudflare_zone_id:
            return []

        client = await self._get_client()

        response = await client.get(
            f"/zones/{self.config.cloudflare_zone_id}/firewall/rules",
        )

        if response.status_code == 200:
            return response.json().get("result", [])
        return []

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Reglas WAF recomendadas para FinCore
RECOMMENDED_WAF_RULES = [
    {
        "expression": '(http.request.uri.path contains "/api/" and http.request.method eq "POST" and not cf.bot_management.verified_bot)',
        "action": "managed_challenge",
        "description": "Challenge suspicious POST to API",
    },
    {
        "expression": '(http.request.uri.path contains "/auth" and http.request.method eq "POST" and cf.threat_score gt 10)',
        "action": "block",
        "description": "Block high threat score auth requests",
    },
    {
        "expression": '(http.request.uri.path contains "/admin" and not ip.src in $allowed_admin_ips)',
        "action": "block",
        "description": "Restrict admin access to allowed IPs",
    },
    {
        "expression": '(http.request.uri.query contains "UNION" or http.request.uri.query contains "SELECT" or http.request.uri.query contains "DROP")',
        "action": "block",
        "description": "Block SQL injection attempts",
    },
    {
        "expression": '(http.request.headers["user-agent"] contains "sqlmap" or http.request.headers["user-agent"] contains "nikto")',
        "action": "block",
        "description": "Block known attack tools",
    },
]
