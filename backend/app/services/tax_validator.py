"""
Servicio de Validacion Fiscal (KYC).
Integra con APIs de entes tributarios (SAT, AFIP, SII, etc.)
"""
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class PaisRegimen(str, Enum):
    """Paises soportados para validacion fiscal."""
    MEXICO = "MX"      # SAT
    ARGENTINA = "AR"   # AFIP
    CHILE = "CL"       # SII
    COLOMBIA = "CO"    # DIAN
    PERU = "PE"        # SUNAT
    ESPANA = "ES"      # AEAT


@dataclass
class ResultadoValidacion:
    """Resultado de la validacion fiscal."""
    es_valido: bool
    tax_id: str
    pais: str
    nombre_legal: Optional[str]
    tipo_persona: Optional[str]  # Fisica/Juridica
    situacion_tributaria: Optional[str]  # Activo/Suspendido/etc
    direccion_fiscal: Optional[str]
    actividad_economica: Optional[str]
    fecha_validacion: datetime
    raw_response: Dict
    mensaje_error: Optional[str] = None


class TaxValidator:
    """
    Validador de ID Fiscal contra entes reguladores.
    Soporta multiples paises con fallback a validacion de formato.
    """

    # Patrones de validacion por pais (regex)
    PATRONES = {
        PaisRegimen.MEXICO: r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$",  # RFC
        PaisRegimen.ARGENTINA: r"^\d{2}-\d{8}-\d{1}$",           # CUIT
        PaisRegimen.CHILE: r"^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$",   # RUT
        PaisRegimen.COLOMBIA: r"^\d{9,10}$",                     # NIT
        PaisRegimen.PERU: r"^\d{11}$",                           # RUC
        PaisRegimen.ESPANA: r"^[A-Z]\d{8}$|^\d{8}[A-Z]$",       # NIF/CIF
    }

    # URLs de APIs (configurables)
    API_URLS = {
        PaisRegimen.MEXICO: "https://api.sat.gob.mx/validar",
        PaisRegimen.ARGENTINA: "https://servicios.afip.gob.ar/wscdc",
    }

    def __init__(self):
        self.timeout = httpx.Timeout(30.0)

    def validar_formato(self, tax_id: str, pais: PaisRegimen) -> bool:
        """Valida formato del ID fiscal segun pais."""
        import re
        patron = self.PATRONES.get(pais)
        if not patron:
            return True  # Sin patron definido, aceptar
        return bool(re.match(patron, tax_id.upper()))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _consultar_api_externa(
        self,
        tax_id: str,
        pais: PaisRegimen
    ) -> Dict:
        """
        Consulta API externa del ente tributario.
        Con reintentos automaticos.
        """
        url = self.API_URLS.get(pais)
        if not url:
            raise ValueError(f"API no configurada para {pais}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json={"tax_id": tax_id},
                headers={
                    "Authorization": f"Bearer {settings.TAX_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()

    async def validar_mexico_sat(self, rfc: str) -> ResultadoValidacion:
        """
        Valida RFC contra el SAT de Mexico.
        En produccion, usar API real del SAT.
        """
        # Validar formato primero
        if not self.validar_formato(rfc, PaisRegimen.MEXICO):
            return ResultadoValidacion(
                es_valido=False,
                tax_id=rfc,
                pais=PaisRegimen.MEXICO.value,
                nombre_legal=None,
                tipo_persona=None,
                situacion_tributaria=None,
                direccion_fiscal=None,
                actividad_economica=None,
                fecha_validacion=datetime.utcnow(),
                raw_response={},
                mensaje_error="Formato de RFC invalido"
            )

        try:
            # En produccion: llamar API real
            # data = await self._consultar_api_externa(rfc, PaisRegimen.MEXICO)

            # Mock para desarrollo
            tipo_persona = "Juridica" if len(rfc) == 12 else "Fisica"

            return ResultadoValidacion(
                es_valido=True,
                tax_id=rfc.upper(),
                pais=PaisRegimen.MEXICO.value,
                nombre_legal="[Nombre pendiente validacion SAT]",
                tipo_persona=tipo_persona,
                situacion_tributaria="Activo",
                direccion_fiscal=None,
                actividad_economica=None,
                fecha_validacion=datetime.utcnow(),
                raw_response={"source": "mock", "rfc": rfc}
            )

        except Exception as e:
            return ResultadoValidacion(
                es_valido=False,
                tax_id=rfc,
                pais=PaisRegimen.MEXICO.value,
                nombre_legal=None,
                tipo_persona=None,
                situacion_tributaria=None,
                direccion_fiscal=None,
                actividad_economica=None,
                fecha_validacion=datetime.utcnow(),
                raw_response={},
                mensaje_error=str(e)
            )

    async def validar(
        self,
        tax_id: str,
        pais: str = "MX"
    ) -> ResultadoValidacion:
        """
        Valida ID fiscal contra el ente tributario del pais.
        """
        try:
            pais_enum = PaisRegimen(pais.upper())
        except ValueError:
            return ResultadoValidacion(
                es_valido=False,
                tax_id=tax_id,
                pais=pais,
                nombre_legal=None,
                tipo_persona=None,
                situacion_tributaria=None,
                direccion_fiscal=None,
                actividad_economica=None,
                fecha_validacion=datetime.utcnow(),
                raw_response={},
                mensaje_error=f"Pais no soportado: {pais}"
            )

        # Dispatch por pais
        if pais_enum == PaisRegimen.MEXICO:
            return await self.validar_mexico_sat(tax_id)

        # TODO: Implementar otros paises
        # Por ahora, validacion de formato
        es_valido = self.validar_formato(tax_id, pais_enum)

        return ResultadoValidacion(
            es_valido=es_valido,
            tax_id=tax_id,
            pais=pais,
            nombre_legal=None,
            tipo_persona=None,
            situacion_tributaria="Pendiente validacion",
            direccion_fiscal=None,
            actividad_economica=None,
            fecha_validacion=datetime.utcnow(),
            raw_response={"validated_format_only": True}
        )
