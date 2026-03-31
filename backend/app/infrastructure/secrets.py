"""
Gestión de Secrets con AWS Secrets Manager.
Soporte para rotación automática y cache local.
"""
import os
import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
from functools import lru_cache
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

# Cache thread-safe para secrets
_secrets_cache: Dict[str, "CachedSecret"] = {}
_cache_lock = threading.Lock()


@dataclass
class CachedSecret:
    """Representa un secret en cache."""
    value: Any
    expires_at: datetime
    version_id: Optional[str] = None


class SecretsManager:
    """
    Gestor de secrets con soporte para múltiples backends.
    Soporta: AWS Secrets Manager, HashiCorp Vault, Environment Variables.
    """

    def __init__(
        self,
        backend: str = "auto",
        region: str = "us-east-1",
        cache_ttl_seconds: int = 300,
        prefix: str = "fincore",
    ):
        """
        Inicializa el gestor de secrets.

        Args:
            backend: Backend a usar ('aws', 'vault', 'env', 'auto')
            region: Región de AWS
            cache_ttl_seconds: TTL del cache en segundos
            prefix: Prefijo para nombres de secrets
        """
        self.region = region
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.prefix = prefix
        self._client = None
        self._vault_client = None

        # Auto-detectar backend
        if backend == "auto":
            if os.getenv("AWS_SECRETS_MANAGER_ENABLED", "").lower() == "true":
                backend = "aws"
            elif os.getenv("VAULT_ADDR"):
                backend = "vault"
            else:
                backend = "env"

        self.backend = backend
        logger.info(f"SecretsManager initialized with backend: {backend}")

    @property
    def aws_client(self):
        """Cliente de AWS Secrets Manager (lazy loading)."""
        if self._client is None and self.backend == "aws":
            try:
                import boto3
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self.region,
                )
            except ImportError:
                logger.error("boto3 not installed. Run: pip install boto3")
                raise
            except Exception as e:
                logger.error(f"Failed to create AWS Secrets Manager client: {e}")
                raise
        return self._client

    @property
    def vault_client(self):
        """Cliente de HashiCorp Vault (lazy loading)."""
        if self._vault_client is None and self.backend == "vault":
            try:
                import hvac
                vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
                vault_token = os.getenv("VAULT_TOKEN")
                vault_role_id = os.getenv("VAULT_ROLE_ID")
                vault_secret_id = os.getenv("VAULT_SECRET_ID")

                self._vault_client = hvac.Client(url=vault_addr)

                if vault_token:
                    self._vault_client.token = vault_token
                elif vault_role_id and vault_secret_id:
                    self._vault_client.auth.approle.login(
                        role_id=vault_role_id,
                        secret_id=vault_secret_id,
                    )
            except ImportError:
                logger.error("hvac not installed. Run: pip install hvac")
                raise
            except Exception as e:
                logger.error(f"Failed to create Vault client: {e}")
                raise
        return self._vault_client

    def _get_full_name(self, name: str) -> str:
        """Construye el nombre completo del secret."""
        if self.prefix and not name.startswith(self.prefix):
            return f"{self.prefix}/{name}"
        return name

    def _get_from_cache(self, name: str) -> Optional[Any]:
        """Obtiene un secret del cache si existe y no ha expirado."""
        with _cache_lock:
            cached = _secrets_cache.get(name)
            if cached and cached.expires_at > datetime.utcnow():
                return cached.value
            elif cached:
                del _secrets_cache[name]
        return None

    def _set_in_cache(
        self,
        name: str,
        value: Any,
        version_id: Optional[str] = None,
    ) -> None:
        """Guarda un secret en cache."""
        with _cache_lock:
            _secrets_cache[name] = CachedSecret(
                value=value,
                expires_at=datetime.utcnow() + self.cache_ttl,
                version_id=version_id,
            )

    def get_secret(
        self,
        name: str,
        use_cache: bool = True,
        parse_json: bool = True,
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Obtiene un secret.

        Args:
            name: Nombre del secret
            use_cache: Si usar cache
            parse_json: Si parsear como JSON automáticamente

        Returns:
            Valor del secret (string o dict si es JSON)
        """
        full_name = self._get_full_name(name)

        # Intentar cache primero
        if use_cache:
            cached = self._get_from_cache(full_name)
            if cached is not None:
                logger.debug(f"Secret '{name}' retrieved from cache")
                return cached

        value = None
        version_id = None

        try:
            if self.backend == "aws":
                value, version_id = self._get_from_aws(full_name)
            elif self.backend == "vault":
                value = self._get_from_vault(full_name)
            else:
                value = self._get_from_env(name)

            if value is None:
                return None

            # Parsear JSON si es necesario
            if parse_json and isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass  # No es JSON, mantener como string

            # Guardar en cache
            if use_cache:
                self._set_in_cache(full_name, value, version_id)

            logger.info(f"Secret '{name}' retrieved successfully")
            return value

        except Exception as e:
            logger.error(f"Failed to get secret '{name}': {e}")
            raise

    def _get_from_aws(self, name: str) -> tuple[Optional[str], Optional[str]]:
        """Obtiene un secret de AWS Secrets Manager."""
        try:
            response = self.aws_client.get_secret_value(SecretId=name)
            version_id = response.get("VersionId")

            if "SecretString" in response:
                return response["SecretString"], version_id
            else:
                # Secret binario
                import base64
                return base64.b64decode(response["SecretBinary"]).decode("utf-8"), version_id
        except self.aws_client.exceptions.ResourceNotFoundException:
            logger.warning(f"Secret not found in AWS: {name}")
            return None, None
        except Exception as e:
            logger.error(f"AWS Secrets Manager error: {e}")
            raise

    def _get_from_vault(self, name: str) -> Optional[str]:
        """Obtiene un secret de HashiCorp Vault."""
        try:
            # Asumir KV v2
            mount_point = os.getenv("VAULT_MOUNT", "secret")
            response = self.vault_client.secrets.kv.v2.read_secret_version(
                path=name,
                mount_point=mount_point,
            )
            data = response.get("data", {}).get("data", {})
            # Si solo hay un valor, retornarlo directamente
            if len(data) == 1 and "value" in data:
                return data["value"]
            return json.dumps(data)
        except Exception as e:
            logger.error(f"Vault error: {e}")
            raise

    def _get_from_env(self, name: str) -> Optional[str]:
        """Obtiene un secret de variables de entorno."""
        # Convertir nombre a formato de variable de entorno
        env_name = name.upper().replace("/", "_").replace("-", "_")
        return os.getenv(env_name)

    def set_secret(
        self,
        name: str,
        value: Union[str, Dict[str, Any]],
        description: Optional[str] = None,
    ) -> bool:
        """
        Crea o actualiza un secret.

        Args:
            name: Nombre del secret
            value: Valor del secret
            description: Descripción opcional

        Returns:
            True si fue exitoso
        """
        full_name = self._get_full_name(name)

        # Convertir dict a JSON string
        if isinstance(value, dict):
            value = json.dumps(value)

        try:
            if self.backend == "aws":
                return self._set_in_aws(full_name, value, description)
            elif self.backend == "vault":
                return self._set_in_vault(full_name, value)
            else:
                logger.warning("Cannot set secrets in env backend")
                return False
        except Exception as e:
            logger.error(f"Failed to set secret '{name}': {e}")
            raise

    def _set_in_aws(
        self,
        name: str,
        value: str,
        description: Optional[str] = None,
    ) -> bool:
        """Crea o actualiza un secret en AWS."""
        try:
            # Intentar actualizar
            self.aws_client.put_secret_value(
                SecretId=name,
                SecretString=value,
            )
            logger.info(f"Secret '{name}' updated in AWS")
            return True
        except self.aws_client.exceptions.ResourceNotFoundException:
            # Crear nuevo
            self.aws_client.create_secret(
                Name=name,
                SecretString=value,
                Description=description or f"FinCore secret: {name}",
            )
            logger.info(f"Secret '{name}' created in AWS")
            return True

    def _set_in_vault(self, name: str, value: str) -> bool:
        """Crea o actualiza un secret en Vault."""
        mount_point = os.getenv("VAULT_MOUNT", "secret")
        self.vault_client.secrets.kv.v2.create_or_update_secret(
            path=name,
            secret={"value": value},
            mount_point=mount_point,
        )
        logger.info(f"Secret '{name}' stored in Vault")
        return True

    def delete_secret(self, name: str, force: bool = False) -> bool:
        """
        Elimina un secret.

        Args:
            name: Nombre del secret
            force: Si True, elimina permanentemente

        Returns:
            True si fue exitoso
        """
        full_name = self._get_full_name(name)

        try:
            if self.backend == "aws":
                if force:
                    self.aws_client.delete_secret(
                        SecretId=full_name,
                        ForceDeleteWithoutRecovery=True,
                    )
                else:
                    self.aws_client.delete_secret(
                        SecretId=full_name,
                        RecoveryWindowInDays=7,
                    )
                logger.info(f"Secret '{name}' deleted from AWS")
                return True
            elif self.backend == "vault":
                mount_point = os.getenv("VAULT_MOUNT", "secret")
                self.vault_client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=full_name,
                    mount_point=mount_point,
                )
                logger.info(f"Secret '{name}' deleted from Vault")
                return True
            else:
                logger.warning("Cannot delete secrets in env backend")
                return False
        except Exception as e:
            logger.error(f"Failed to delete secret '{name}': {e}")
            return False

    def clear_cache(self, name: Optional[str] = None) -> None:
        """Limpia el cache de secrets."""
        with _cache_lock:
            if name:
                full_name = self._get_full_name(name)
                _secrets_cache.pop(full_name, None)
            else:
                _secrets_cache.clear()
        logger.debug(f"Cache cleared: {name or 'all'}")


# Singleton global
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Obtiene la instancia singleton del SecretsManager."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(
            backend=os.getenv("SECRETS_BACKEND", "auto"),
            region=os.getenv("AWS_REGION", "us-east-1"),
            cache_ttl_seconds=int(os.getenv("SECRETS_CACHE_TTL", "300")),
            prefix=os.getenv("SECRETS_PREFIX", "fincore"),
        )
    return _secrets_manager


def get_secret(
    name: str,
    default: Optional[str] = None,
    required: bool = False,
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Función helper para obtener un secret.

    Args:
        name: Nombre del secret
        default: Valor por defecto si no existe
        required: Si True, lanza excepción si no existe

    Returns:
        Valor del secret o default
    """
    try:
        value = get_secrets_manager().get_secret(name)
        if value is None:
            if required:
                raise ValueError(f"Required secret '{name}' not found")
            return default
        return value
    except Exception as e:
        if required:
            raise
        logger.warning(f"Failed to get secret '{name}', using default: {e}")
        return default
