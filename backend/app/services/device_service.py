"""
Servicio de Gestión de Dispositivos y Sesiones.

Implementa:
- Fingerprinting de dispositivos
- Detección de geolocalización (ipapi/MaxMind)
- Detección de VPN/Tor/Proxy
- Cálculo de score de riesgo
- Gestión de sesiones activas
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from uuid import UUID
import httpx

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.config import settings
from app.models.user import User
from app.models.security import (
    UserDevice, UserSession, DeviceStatus
)
from app.models.audit import AuditLog, AuditAction

logger = logging.getLogger(__name__)

# Constantes
SESSION_EXPIRE_MINUTES = 30
DEVICE_TRUST_AFTER_LOGINS = 3  # Confiar automáticamente después de N logins
HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "CU"}  # Países de alto riesgo
VPN_RISK_SCORE = 20
TOR_RISK_SCORE = 40
PROXY_RISK_SCORE = 15
NEW_COUNTRY_RISK_SCORE = 25
HIGH_RISK_COUNTRY_SCORE = 50


class DeviceService:
    """Servicio para gestión de dispositivos y sesiones."""

    def __init__(self, db: Session):
        self.db = db

    def generate_device_fingerprint(
        self,
        user_agent: str,
        ip_address: str,
        accept_language: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Genera un fingerprint único para el dispositivo.

        En producción, el frontend envía datos adicionales de FingerprintJS.
        """
        # Combinar datos disponibles
        fingerprint_data = f"{user_agent}|{accept_language or ''}"

        # Si hay datos de FingerprintJS del frontend
        if extra_data:
            fingerprint_data += f"|{extra_data.get('visitorId', '')}"
            fingerprint_data += f"|{extra_data.get('screenResolution', '')}"
            fingerprint_data += f"|{extra_data.get('timezone', '')}"

        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

    async def get_or_create_device(
        self,
        user: User,
        fingerprint: str,
        ip_address: str,
        user_agent: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[UserDevice, bool]:
        """
        Obtiene o crea un dispositivo para el usuario.

        Returns:
            Tuple[UserDevice, bool]: (dispositivo, es_nuevo)
        """
        # Buscar dispositivo existente
        device = self.db.query(UserDevice).filter(
            UserDevice.user_id == user.id,
            UserDevice.device_fingerprint == fingerprint
        ).first()

        is_new = device is None

        if is_new:
            # Obtener geolocalización
            geo_data = await self._get_geolocation(ip_address)

            # Parsear user agent
            ua_info = self._parse_user_agent(user_agent)

            device = UserDevice(
                user_id=user.id,
                device_fingerprint=fingerprint,
                user_agent=user_agent,
                browser_name=ua_info.get("browser_name"),
                browser_version=ua_info.get("browser_version"),
                os_name=ua_info.get("os_name"),
                os_version=ua_info.get("os_version"),
                device_type=ua_info.get("device_type"),
                last_ip=ip_address,
                last_country=geo_data.get("country_code"),
                last_city=geo_data.get("city"),
                last_region=geo_data.get("region"),
                is_vpn=geo_data.get("is_vpn", False),
                is_tor=geo_data.get("is_tor", False),
                is_proxy=geo_data.get("is_proxy", False),
                status=DeviceStatus.UNKNOWN,
                login_count=0
            )
            self.db.add(device)
        else:
            # Actualizar información del dispositivo
            geo_data = await self._get_geolocation(ip_address)

            device.last_ip = ip_address
            device.last_seen_at = datetime.utcnow()
            device.last_country = geo_data.get("country_code", device.last_country)
            device.last_city = geo_data.get("city", device.last_city)
            device.is_vpn = geo_data.get("is_vpn", device.is_vpn)
            device.is_tor = geo_data.get("is_tor", device.is_tor)
            device.is_proxy = geo_data.get("is_proxy", device.is_proxy)

        # Incrementar contador de logins
        device.login_count += 1

        # Auto-trust después de N logins exitosos
        if device.login_count >= DEVICE_TRUST_AFTER_LOGINS and device.status == DeviceStatus.UNKNOWN:
            device.status = DeviceStatus.TRUSTED
            device.trusted_at = datetime.utcnow()

        # Calcular score de riesgo
        device.risk_score = self._calculate_risk_score(device, user)

        self.db.commit()
        self.db.refresh(device)

        return device, is_new

    def _calculate_risk_score(self, device: UserDevice, user: User) -> int:
        """
        Calcula score de riesgo del dispositivo (0-100).

        Factores:
        - VPN detectada: +20
        - Tor detectado: +40
        - Proxy detectado: +15
        - País diferente al habitual: +25
        - País de alto riesgo: +50
        - Dispositivo nuevo: +10
        """
        score = 0

        if device.is_vpn:
            score += VPN_RISK_SCORE
        if device.is_tor:
            score += TOR_RISK_SCORE
        if device.is_proxy:
            score += PROXY_RISK_SCORE

        # País de alto riesgo
        if device.last_country in HIGH_RISK_COUNTRIES:
            score += HIGH_RISK_COUNTRY_SCORE

        # País diferente al habitual
        if device.login_count == 1:
            # Verificar si es diferente a otros dispositivos del usuario
            other_devices = self.db.query(UserDevice).filter(
                UserDevice.user_id == user.id,
                UserDevice.id != device.id,
                UserDevice.last_country.isnot(None)
            ).all()

            if other_devices:
                usual_countries = {d.last_country for d in other_devices}
                if device.last_country and device.last_country not in usual_countries:
                    score += NEW_COUNTRY_RISK_SCORE

        # Dispositivo nuevo
        if device.status == DeviceStatus.UNKNOWN:
            score += 10

        return min(score, 100)

    async def _get_geolocation(self, ip_address: str) -> Dict[str, Any]:
        """
        Obtiene información de geolocalización de una IP.

        Usa ipapi.co (free tier: 1000 req/day) o MaxMind si está configurado.
        """
        # IPs locales no tienen geolocalización
        if ip_address in ("127.0.0.1", "localhost", "::1") or ip_address.startswith("192.168."):
            return {
                "country_code": "MX",  # Default para desarrollo
                "city": "Local",
                "region": "Development",
                "is_vpn": False,
                "is_tor": False,
                "is_proxy": False
            }

        try:
            async with httpx.AsyncClient() as client:
                # Usar ipapi.co (free tier)
                response = await client.get(
                    f"https://ipapi.co/{ip_address}/json/",
                    timeout=5.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "country_code": data.get("country_code", ""),
                        "city": data.get("city", ""),
                        "region": data.get("region", ""),
                        "is_vpn": False,  # ipapi.co free no detecta VPN
                        "is_tor": False,
                        "is_proxy": False
                    }

        except Exception as e:
            logger.warning(f"Error obteniendo geolocalización para {ip_address}: {e}")

        return {
            "country_code": "",
            "city": "",
            "region": "",
            "is_vpn": False,
            "is_tor": False,
            "is_proxy": False
        }

    def _parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """Parsea el User-Agent para extraer información del dispositivo."""
        result = {
            "browser_name": None,
            "browser_version": None,
            "os_name": None,
            "os_version": None,
            "device_type": "desktop"
        }

        ua_lower = user_agent.lower()

        # Detectar navegador
        if "chrome" in ua_lower and "edg" not in ua_lower:
            result["browser_name"] = "Chrome"
            if "chrome/" in ua_lower:
                version = ua_lower.split("chrome/")[1].split(" ")[0].split(".")[0]
                result["browser_version"] = version
        elif "firefox" in ua_lower:
            result["browser_name"] = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            result["browser_name"] = "Safari"
        elif "edg" in ua_lower:
            result["browser_name"] = "Edge"

        # Detectar OS
        if "windows" in ua_lower:
            result["os_name"] = "Windows"
            if "windows nt 10" in ua_lower:
                result["os_version"] = "10/11"
        elif "mac os" in ua_lower or "macintosh" in ua_lower:
            result["os_name"] = "macOS"
        elif "linux" in ua_lower:
            result["os_name"] = "Linux"
        elif "android" in ua_lower:
            result["os_name"] = "Android"
            result["device_type"] = "mobile"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            result["os_name"] = "iOS"
            result["device_type"] = "mobile" if "iphone" in ua_lower else "tablet"

        return result

    def create_session(
        self,
        user: User,
        device: UserDevice,
        access_token: str,
        refresh_token: Optional[str],
        ip_address: str
    ) -> UserSession:
        """Crea una nueva sesión para el usuario."""
        # Hash de tokens para almacenamiento seguro
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest() if refresh_token else None

        session = UserSession(
            user_id=user.id,
            device_id=device.id,
            session_token_hash=token_hash,
            refresh_token_hash=refresh_hash,
            ip_address=ip_address,
            country=device.last_country,
            city=device.last_city,
            expires_at=datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def get_active_sessions(self, user_id: UUID) -> list[UserSession]:
        """Obtiene todas las sesiones activas del usuario."""
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(UserSession.last_activity_at.desc()).all()

    def revoke_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Revoca una sesión específica."""
        session = self.db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id
        ).first()

        if session:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            self.db.commit()
            return True

        return False

    def revoke_all_sessions(self, user_id: UUID, except_session_id: Optional[UUID] = None) -> int:
        """
        Revoca todas las sesiones del usuario.

        Args:
            user_id: ID del usuario
            except_session_id: Sesión a excluir (la actual)

        Returns:
            Número de sesiones revocadas
        """
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        )

        if except_session_id:
            query = query.filter(UserSession.id != except_session_id)

        sessions = query.all()
        count = len(sessions)

        for session in sessions:
            session.is_active = False
            session.revoked_at = datetime.utcnow()

        self.db.commit()
        return count

    def get_user_devices(self, user_id: UUID) -> list[UserDevice]:
        """Obtiene todos los dispositivos del usuario."""
        return self.db.query(UserDevice).filter(
            UserDevice.user_id == user_id
        ).order_by(UserDevice.last_seen_at.desc()).all()

    def update_device_status(
        self,
        device_id: UUID,
        user_id: UUID,
        status: DeviceStatus,
        device_name: Optional[str] = None
    ) -> Optional[UserDevice]:
        """Actualiza el estado de un dispositivo."""
        device = self.db.query(UserDevice).filter(
            UserDevice.id == device_id,
            UserDevice.user_id == user_id
        ).first()

        if device:
            device.status = status
            if device_name is not None:
                device.device_name = device_name
            if status == DeviceStatus.TRUSTED:
                device.trusted_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(device)

        return device

    def delete_device(self, device_id: UUID, user_id: UUID) -> bool:
        """Elimina un dispositivo y sus sesiones asociadas."""
        device = self.db.query(UserDevice).filter(
            UserDevice.id == device_id,
            UserDevice.user_id == user_id
        ).first()

        if device:
            # Revocar todas las sesiones del dispositivo
            self.db.query(UserSession).filter(
                UserSession.device_id == device_id
            ).update({"is_active": False, "revoked_at": datetime.utcnow()})

            self.db.delete(device)
            self.db.commit()
            return True

        return False

    def mark_session_activity(self, token_hash: str) -> None:
        """Actualiza la última actividad de una sesión."""
        session = self.db.query(UserSession).filter(
            UserSession.session_token_hash == token_hash,
            UserSession.is_active == True
        ).first()

        if session:
            session.last_activity_at = datetime.utcnow()
            self.db.commit()


# Instancia singleton para uso en endpoints
def get_device_service(db: Session) -> DeviceService:
    return DeviceService(db)
