"""
Analizador de Estudios de Factibilidad con IA.
Extrae datos financieros de PDFs usando Claude API.
"""
import os
import json
import base64
from typing import Optional, Dict, Any, List
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

import anthropic
from PyPDF2 import PdfReader


class ProjectType(str, Enum):
    """Tipos de proyecto para indicadores especificos."""
    INMOBILIARIO = "inmobiliario"
    TECNOLOGIA = "tecnologia"
    ENERGIA = "energia"
    AGROTECH = "agrotech"
    FINTECH = "fintech"
    INDUSTRIAL = "industrial"
    COMERCIO = "comercio"
    INFRAESTRUCTURA = "infraestructura"
    OTRO = "otro"


@dataclass
class ExtractedProjectData:
    """Datos extraidos del estudio de factibilidad."""
    # Datos basicos
    nombre: str
    descripcion: str
    sector: str
    ubicacion: Optional[str] = None
    empresa_solicitante: Optional[str] = None

    # Configuracion financiera
    inversion_inicial: Decimal = Decimal("0")
    tasa_descuento: Decimal = Decimal("0.12")
    plazo_meses: int = 24
    tasa_rendimiento_esperado: Decimal = Decimal("0.15")
    tipo_periodo: str = "mensual"  # mensual o anual

    # Flujos de caja
    flujos_caja: List[Dict[str, Any]] = None

    # Datos adicionales por tipo de proyecto
    datos_adicionales: Dict[str, Any] = None

    # Indicadores pre-calculados del documento
    van_documento: Optional[Decimal] = None
    tir_documento: Optional[Decimal] = None
    payback_documento: Optional[int] = None

    # Confianza del analisis
    confianza_extraccion: float = 0.0
    notas_extraccion: str = ""

    def __post_init__(self):
        if self.flujos_caja is None:
            self.flujos_caja = []
        if self.datos_adicionales is None:
            self.datos_adicionales = {}


class FeasibilityAnalyzer:
    """
    Analizador de estudios de factibilidad usando Claude AI.
    Extrae datos estructurados de PDFs para cargar automaticamente en el sistema.
    """

    EXTRACTION_PROMPT = """Analiza el siguiente estudio de factibilidad y extrae los datos financieros en formato JSON estructurado.

IMPORTANTE: Extrae TODOS los datos financieros que encuentres, incluyendo:

1. **Datos Basicos del Proyecto:**
   - nombre: Nombre del proyecto
   - descripcion: Descripcion detallada
   - sector: Sector (inmobiliario, tecnologia, energia, agrotech, fintech, industrial, comercio, infraestructura, otro)
   - ubicacion: Ubicacion geografica
   - empresa_solicitante: Nombre de la empresa

2. **Configuracion Financiera:**
   - inversion_inicial: Monto total de inversion inicial (CAPEX + pre-operativos)
   - tasa_descuento: Tasa de descuento o WACC (como decimal, ej: 0.12 para 12%)
   - plazo_meses: Duracion del proyecto en meses
   - tasa_rendimiento_esperado: Rendimiento esperado (como decimal)
   - tipo_periodo: "mensual" o "anual" segun como esten los flujos

3. **Flujos de Caja Proyectados:**
   Array de objetos con:
   - periodo: Numero del periodo (1, 2, 3...)
   - ingresos: Ingresos proyectados
   - costos: Costos/egresos proyectados
   - descripcion: Descripcion del periodo

4. **Indicadores del Documento (si los menciona):**
   - van_documento: VAN calculado en el documento
   - tir_documento: TIR calculada (como decimal)
   - payback_documento: Periodo de recuperacion en meses

5. **Datos Adicionales segun Tipo de Proyecto:**
   Para INMOBILIARIO: metros_cuadrados, precio_m2, ocupacion_esperada
   Para TECNOLOGIA: usuarios_proyectados, arpu, cac, ltv
   Para ENERGIA: capacidad_mw, factor_planta, precio_kwh
   Para AGROTECH: hectareas, rendimiento_ha, precio_tonelada
   Para FINTECH: volumen_transacciones, comision_promedio, usuarios_activos
   Para INDUSTRIAL: capacidad_produccion, costo_unitario, precio_venta
   Para COMERCIO: ventas_m2, ticket_promedio, rotacion_inventario
   Para INFRAESTRUCTURA: usuarios_diarios, tarifa_promedio, vida_util_anos

6. **Confianza de Extraccion:**
   - confianza_extraccion: Numero de 0 a 1 indicando que tan seguro estas de los datos
   - notas_extraccion: Notas sobre datos faltantes o supuestos

Responde SOLO con el JSON, sin texto adicional. Si no encuentras un dato, usa null.

CONTENIDO DEL DOCUMENTO:
{content}
"""

    INDICATORS_BY_PROJECT_TYPE = {
        ProjectType.INMOBILIARIO: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "cap_rate", "precio_m2", "yield_bruto", "yield_neto",
            "loan_to_value", "debt_service_coverage"
        ],
        ProjectType.TECNOLOGIA: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "ltv_cac_ratio", "burn_rate", "runway_meses",
            "mrr", "arr", "churn_rate", "nps"
        ],
        ProjectType.ENERGIA: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "lcoe", "factor_capacidad", "ingresos_kwh",
            "costo_instalacion_kw", "vida_util_anos"
        ],
        ProjectType.AGROTECH: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "rendimiento_hectarea", "margen_bruto",
            "costo_produccion_ton", "punto_equilibrio"
        ],
        ProjectType.FINTECH: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "take_rate", "volumen_procesado", "costo_adquisicion",
            "lifetime_value", "default_rate"
        ],
        ProjectType.INDUSTRIAL: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "margen_operativo", "utilizacion_capacidad",
            "costo_unitario", "punto_equilibrio_unidades"
        ],
        ProjectType.COMERCIO: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "ventas_m2", "margen_bruto", "rotacion_inventario",
            "ticket_promedio", "conversion_rate"
        ],
        ProjectType.INFRAESTRUCTURA: [
            "van", "tir", "roi", "payback", "indice_rentabilidad",
            "eirr", "firr", "beneficio_costo_ratio",
            "trafico_proyectado", "tarifa_promedio"
        ],
        ProjectType.OTRO: [
            "van", "tir", "roi", "payback", "indice_rentabilidad"
        ]
    }

    def __init__(self, api_key: Optional[str] = None, db_session = None):
        """Inicializa el analizador con la API key de Anthropic."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Si no hay API key en env, buscar en la base de datos
        if not self.api_key and db_session:
            self.api_key = self._get_api_key_from_db(db_session)

        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def _get_api_key_from_db(self, db_session) -> Optional[str]:
        """Obtiene la API key de la tabla system_config."""
        try:
            from app.models.system_config import SystemConfig
            config = db_session.query(SystemConfig).filter(
                SystemConfig.config_key == "anthropic_api_key",
                SystemConfig.is_active == True
            ).first()
            return config.config_value if config else None
        except Exception:
            return None

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extrae texto de un PDF."""
        import io
        reader = PdfReader(io.BytesIO(pdf_content))
        text_parts = []

        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        return "\n\n".join(text_parts)

    async def analyze_pdf(self, pdf_content: bytes) -> ExtractedProjectData:
        """
        Analiza un PDF de estudio de factibilidad y extrae datos estructurados.
        """
        if not self.client:
            raise ValueError("API key de Anthropic no configurada")

        # Extraer texto del PDF
        text_content = self.extract_text_from_pdf(pdf_content)

        if not text_content or len(text_content) < 100:
            raise ValueError("No se pudo extraer texto suficiente del PDF")

        # Limitar texto para no exceder limites de tokens
        max_chars = 50000
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n...[documento truncado]..."

        # Llamar a Claude para analizar
        prompt = self.EXTRACTION_PROMPT.format(content=text_content)

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parsear respuesta JSON
        response_text = message.content[0].text

        # Limpiar respuesta (a veces viene con markdown)
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        try:
            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parseando respuesta de IA: {e}")

        # Construir objeto de datos extraidos
        return self._build_extracted_data(data)

    def _build_extracted_data(self, data: Dict[str, Any]) -> ExtractedProjectData:
        """Construye el objeto ExtractedProjectData desde el JSON."""
        flujos = []
        if data.get("flujos_caja"):
            for f in data["flujos_caja"]:
                flujos.append({
                    "periodo": f.get("periodo", 1),
                    "ingresos": Decimal(str(f.get("ingresos", 0))),
                    "costos": Decimal(str(f.get("costos", 0))),
                    "descripcion": f.get("descripcion", "")
                })

        return ExtractedProjectData(
            nombre=data.get("nombre", "Proyecto sin nombre"),
            descripcion=data.get("descripcion", ""),
            sector=data.get("sector", "otro"),
            ubicacion=data.get("ubicacion"),
            empresa_solicitante=data.get("empresa_solicitante"),
            inversion_inicial=Decimal(str(data.get("inversion_inicial", 0))),
            tasa_descuento=Decimal(str(data.get("tasa_descuento", 0.12))),
            plazo_meses=int(data.get("plazo_meses", 24)),
            tasa_rendimiento_esperado=Decimal(str(data.get("tasa_rendimiento_esperado", 0.15))),
            tipo_periodo=data.get("tipo_periodo", "mensual"),
            flujos_caja=flujos,
            datos_adicionales=data.get("datos_adicionales", {}),
            van_documento=Decimal(str(data["van_documento"])) if data.get("van_documento") else None,
            tir_documento=Decimal(str(data["tir_documento"])) if data.get("tir_documento") else None,
            payback_documento=int(data["payback_documento"]) if data.get("payback_documento") else None,
            confianza_extraccion=float(data.get("confianza_extraccion", 0.5)),
            notas_extraccion=data.get("notas_extraccion", "")
        )

    @classmethod
    def get_indicators_for_project_type(cls, project_type: str) -> List[str]:
        """Obtiene la lista de indicadores relevantes para un tipo de proyecto."""
        try:
            ptype = ProjectType(project_type.lower())
        except ValueError:
            ptype = ProjectType.OTRO

        return cls.INDICATORS_BY_PROJECT_TYPE.get(ptype, cls.INDICATORS_BY_PROJECT_TYPE[ProjectType.OTRO])

    @classmethod
    def get_all_extended_indicators(cls) -> Dict[str, str]:
        """Retorna todos los indicadores extendidos con sus descripciones."""
        return {
            # Basicos
            "van": "Valor Actual Neto",
            "tir": "Tasa Interna de Retorno",
            "roi": "Retorno sobre Inversion",
            "payback": "Periodo de Recuperacion",
            "indice_rentabilidad": "Indice de Rentabilidad (PI)",

            # Inmobiliario
            "cap_rate": "Tasa de Capitalizacion",
            "precio_m2": "Precio por Metro Cuadrado",
            "yield_bruto": "Rendimiento Bruto",
            "yield_neto": "Rendimiento Neto",
            "loan_to_value": "Relacion Prestamo/Valor",
            "debt_service_coverage": "Cobertura de Servicio de Deuda",

            # Tecnologia
            "ltv_cac_ratio": "Ratio LTV/CAC",
            "burn_rate": "Tasa de Quema Mensual",
            "runway_meses": "Runway en Meses",
            "mrr": "Ingresos Recurrentes Mensuales",
            "arr": "Ingresos Recurrentes Anuales",
            "churn_rate": "Tasa de Cancelacion",
            "nps": "Net Promoter Score",

            # Energia
            "lcoe": "Costo Nivelado de Energia",
            "factor_capacidad": "Factor de Capacidad",
            "ingresos_kwh": "Ingresos por kWh",
            "costo_instalacion_kw": "Costo Instalacion por kW",
            "vida_util_anos": "Vida Util en Anos",

            # Agrotech
            "rendimiento_hectarea": "Rendimiento por Hectarea",
            "margen_bruto": "Margen Bruto",
            "costo_produccion_ton": "Costo Produccion por Tonelada",
            "punto_equilibrio": "Punto de Equilibrio",

            # Fintech
            "take_rate": "Take Rate",
            "volumen_procesado": "Volumen Procesado",
            "costo_adquisicion": "Costo de Adquisicion",
            "lifetime_value": "Valor de Vida del Cliente",
            "default_rate": "Tasa de Default",

            # Industrial
            "margen_operativo": "Margen Operativo",
            "utilizacion_capacidad": "Utilizacion de Capacidad",
            "costo_unitario": "Costo Unitario",
            "punto_equilibrio_unidades": "Punto Equilibrio en Unidades",

            # Comercio
            "ventas_m2": "Ventas por M2",
            "rotacion_inventario": "Rotacion de Inventario",
            "ticket_promedio": "Ticket Promedio",
            "conversion_rate": "Tasa de Conversion",

            # Infraestructura
            "eirr": "Tasa Retorno Economica",
            "firr": "Tasa Retorno Financiera",
            "beneficio_costo_ratio": "Ratio Beneficio/Costo",
            "trafico_proyectado": "Trafico Proyectado",
            "tarifa_promedio": "Tarifa Promedio"
        }
