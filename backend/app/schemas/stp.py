"""
Schemas Pydantic para integracion con STP (Sistema de Transferencias y Pagos).

STP es la infraestructura de pagos en Mexico que opera:
- SPEI: Sistema de Pagos Electronicos Interbancarios (tiempo real)
- SPID: Sistema de Pagos Interbancarios en Dolares

Documentacion STP: https://stpmex.com/documentacion

Notas importantes:
- CLABE: Clave Bancaria Estandarizada (18 digitos)
- RFC: Registro Federal de Contribuyentes
- Todos los montos en centavos (sin decimales)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re


# ============ Enums ============

class STPOperationType(str, Enum):
    """Tipos de operacion STP."""
    SPEI_OUT = "spei_out"           # Envio de dinero via SPEI
    SPEI_IN = "spei_in"             # Recepcion de dinero via SPEI
    SPID_OUT = "spid_out"           # Envio de dolares
    SPID_IN = "spid_in"             # Recepcion de dolares
    DEVOLUCION = "devolucion"       # Devolucion de fondos


class STPTransactionStatus(str, Enum):
    """Estados de transaccion STP."""
    PENDING = "pending"             # Pendiente de envio
    SENT = "sent"                   # Enviada a STP
    PROCESSING = "processing"       # En proceso en STP
    LIQUIDATED = "liquidated"       # Liquidada exitosamente
    CANCELLED = "cancelled"         # Cancelada
    RETURNED = "returned"           # Devuelta
    FAILED = "failed"               # Fallida
    REJECTED = "rejected"           # Rechazada por STP


class STPAccountType(str, Enum):
    """Tipos de cuenta bancaria."""
    CLABE = "40"                    # CLABE interbancaria
    DEBIT_CARD = "03"               # Tarjeta de debito
    PHONE = "10"                    # Numero celular


class STPPaymentType(str, Enum):
    """Tipos de pago SPEI."""
    ORDINARY = "1"                  # Pago ordinario
    THIRD_PARTY = "2"               # Pago por cuenta de terceros


# Catalogo de bancos Mexico (principales)
BANK_CODES = {
    "002": "BANAMEX",
    "012": "BBVA MEXICO",
    "014": "SANTANDER",
    "021": "HSBC",
    "030": "BAJIO",
    "036": "INBURSA",
    "044": "SCOTIABANK",
    "058": "BANREGIO",
    "072": "BANORTE",
    "106": "BANK OF AMERICA",
    "127": "AZTECA",
    "128": "AUTOFIN",
    "130": "COMPARTAMOS",
    "136": "INTERCAM BANCO",
    "137": "BANCOPPEL",
    "138": "ABC CAPITAL",
    "140": "CONSUBANCO",
    "143": "CIBANCO",
    "145": "BBASE",
    "166": "BANSEFI",
    "168": "HIPOTECARIA FED",
    "600": "MONEXCB",
    "602": "MASARI",
    "606": "FINAMEX",
    "608": "VALUE",
    "610": "VECTOR",
    "614": "ACCIVAL",
    "616": "MERRILL LYNCH",
    "617": "ASEGURADORES",
    "618": "BULLTICK CB",
    "619": "STERLING",
    "620": "FINCOMUN",
    "621": "HDI SEGUROS",
    "622": "SEGMTY",
    "623": "ZURICH",
    "626": "ZURICHVI",
    "627": "SKANDIA",
    "628": "GBM",
    "629": "GE MONEY",
    "630": "CB INTERCAM",
    "631": "CI BOLSA",
    "632": "BULLTICK CB",
    "633": "STERLING",
    "634": "FINCOMUN",
    "636": "STP",
    "637": "KUSPIT",
    "638": "TRANSFER",
    "640": "CB JPMORGAN",
    "642": "REFORMA",
    "646": "STP",  # Cuenta concentradora STP
    "647": "TELECOMUNICACIONES",
    "648": "EVERCORE",
    "649": "SKANDIA",
    "651": "SEGMTY",
    "652": "ASEA",
    "653": "KUSPIT",
    "655": "UNAGRA",
    "656": "SOFIEXPRESS",
    "659": "ASP INTEGRA OPC",
    "670": "LIBERTAD",
    "677": "CAJA POP MEXICA",
    "680": "CRISTOBAL COLON",
    "683": "CAJA TELEFONIST",
    "684": "TRANSFER",
    "685": "FONDO (FIRA)",
    "686": "INVERCAP",
    "689": "FOMPED",
    "699": "FONACOT",
    "703": "TESORED",
    "706": "ARCUS",
    "710": "NVIO",
    "722": "MERCADO PAGO",
    "723": "CUENCA",
    "846": "STP",
    "901": "CLS",
    "902": "INDEVAL",
    "903": "CoDi Valida",
}


# ============ Validation Helpers ============

def validate_clabe(clabe: str) -> bool:
    """
    Valida una CLABE mexicana.

    Estructura: BBB-SSS-CCCCCCCCCCC-D
    - BBB: Codigo de banco (3 digitos)
    - SSS: Codigo de plaza (3 digitos)
    - CCCCCCCCCCC: Numero de cuenta (11 digitos)
    - D: Digito verificador (1 digito)
    """
    if not clabe or len(clabe) != 18:
        return False

    if not clabe.isdigit():
        return False

    # Validar digito verificador
    weights = [3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7]
    total = sum(int(clabe[i]) * weights[i] for i in range(17))
    check_digit = (10 - (total % 10)) % 10

    return int(clabe[17]) == check_digit


def get_bank_from_clabe(clabe: str) -> Optional[str]:
    """Obtiene el nombre del banco desde una CLABE."""
    if not clabe or len(clabe) < 3:
        return None
    bank_code = clabe[:3]
    return BANK_CODES.get(bank_code)


# ============ Request Schemas ============

class STPBeneficiary(BaseModel):
    """Datos del beneficiario para transferencia SPEI."""
    name: str = Field(..., min_length=1, max_length=40, description="Nombre completo")
    rfc: Optional[str] = Field(None, max_length=13, description="RFC del beneficiario")
    account: str = Field(..., min_length=10, max_length=20, description="CLABE o cuenta")
    account_type: STPAccountType = Field(STPAccountType.CLABE, description="Tipo de cuenta")
    bank_code: Optional[str] = Field(None, min_length=3, max_length=3, description="Codigo banco")

    @field_validator('account')
    @classmethod
    def validate_account(cls, v, info):
        """Valida la cuenta segun el tipo."""
        # Si es CLABE, validar formato
        if len(v) == 18 and v.isdigit():
            if not validate_clabe(v):
                raise ValueError('CLABE invalida (digito verificador incorrecto)')
        return v

    @field_validator('rfc')
    @classmethod
    def validate_rfc(cls, v):
        """Valida formato de RFC."""
        if v:
            # RFC persona fisica: 4 letras + 6 digitos + 3 alfanumericos
            # RFC persona moral: 3 letras + 6 digitos + 3 alfanumericos
            pattern = r'^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$'
            if not re.match(pattern, v.upper()):
                raise ValueError('Formato de RFC invalido')
        return v.upper() if v else v

    @property
    def bank_name(self) -> Optional[str]:
        """Nombre del banco derivado de la CLABE."""
        if len(self.account) == 18:
            return get_bank_from_clabe(self.account)
        return None


class STPOrderRequest(BaseModel):
    """
    Solicitud de orden de pago SPEI.

    Nota: STP requiere montos en centavos (sin decimales).
    """
    # Identificadores
    reference: str = Field(..., min_length=1, max_length=7, description="Referencia numerica (7 digitos)")
    tracking_key: Optional[str] = Field(None, max_length=30, description="Clave de rastreo unica")

    # Beneficiario
    beneficiary: STPBeneficiary

    # Monto
    amount: Decimal = Field(..., gt=0, description="Monto en MXN (con decimales)")

    # Concepto
    concept: str = Field(..., min_length=1, max_length=40, description="Concepto de pago")
    payment_type: STPPaymentType = Field(STPPaymentType.ORDINARY)

    # Ordenante (quien envia)
    sender_name: Optional[str] = Field(None, max_length=40)
    sender_rfc: Optional[str] = Field(None, max_length=13)
    sender_account: Optional[str] = Field(None, max_length=20)

    # Metadata
    remittance_id: Optional[str] = Field(None, description="ID de remesa asociada")
    user_id: Optional[str] = Field(None, description="ID del usuario")

    @field_validator('reference')
    @classmethod
    def validate_reference(cls, v):
        """Referencia debe ser numerica."""
        if not v.isdigit():
            raise ValueError('Referencia debe contener solo digitos')
        return v.zfill(7)  # Pad con ceros a la izquierda

    @property
    def amount_cents(self) -> int:
        """Monto en centavos para STP."""
        return int(self.amount * 100)

    class Config:
        json_schema_extra = {
            "example": {
                "reference": "1234567",
                "beneficiary": {
                    "name": "JUAN PEREZ GARCIA",
                    "account": "012180015678912345",
                    "account_type": "40",
                    "rfc": "PEGJ800101ABC"
                },
                "amount": 1500.50,
                "concept": "PAGO REMESA FRC-ABC123",
                "payment_type": "1"
            }
        }


class STPOrderCancelRequest(BaseModel):
    """Solicitud de cancelacion de orden SPEI."""
    tracking_key: str = Field(..., description="Clave de rastreo de la orden")
    reason: str = Field(..., max_length=100, description="Motivo de cancelacion")


class STPBalanceRequest(BaseModel):
    """Solicitud de consulta de saldo."""
    account: Optional[str] = Field(None, description="CLABE de cuenta (default: concentradora)")


# ============ Response Schemas ============

class STPOrderResponse(BaseModel):
    """Respuesta de orden SPEI."""
    # Identificadores
    id: str = Field(..., description="ID interno de la transaccion")
    stp_id: Optional[int] = Field(None, description="ID asignado por STP")
    tracking_key: str = Field(..., description="Clave de rastreo")
    reference: str = Field(..., description="Referencia numerica")

    # Estado
    status: STPTransactionStatus
    status_description: Optional[str] = None

    # Detalles
    amount: Decimal
    currency: str = "MXN"
    beneficiary_name: str
    beneficiary_account: str
    beneficiary_bank: Optional[str] = None
    concept: str

    # Timestamps
    created_at: datetime
    sent_at: Optional[datetime] = None
    liquidated_at: Optional[datetime] = None

    # Errores
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Metadata
    remittance_id: Optional[str] = None

    class Config:
        from_attributes = True


class STPWebhookPayload(BaseModel):
    """
    Payload de webhook recibido de STP.

    STP envia notificaciones cuando:
    - Orden es liquidada
    - Orden es devuelta
    - Se recibe un deposito entrante
    """
    # Identificacion
    id: int = Field(..., description="ID de operacion STP")
    clave_rastreo: str = Field(..., alias="claveRastreo", description="Clave de rastreo")

    # Tipo de operacion
    tipo_operacion: int = Field(..., alias="tipoOperacion")

    # Estado
    estado: int = Field(..., description="Codigo de estado STP")

    # Monto (en centavos)
    monto: int = Field(..., description="Monto en centavos")

    # Ordenante
    cuenta_ordenante: Optional[str] = Field(None, alias="cuentaOrdenante")
    nombre_ordenante: Optional[str] = Field(None, alias="nombreOrdenante")
    rfc_ordenante: Optional[str] = Field(None, alias="rfcCurpOrdenante")

    # Beneficiario
    cuenta_beneficiario: str = Field(..., alias="cuentaBeneficiario")
    nombre_beneficiario: Optional[str] = Field(None, alias="nombreBeneficiario")
    rfc_beneficiario: Optional[str] = Field(None, alias="rfcCurpBeneficiario")

    # Concepto y referencia
    concepto: Optional[str] = None
    referencia_numerica: Optional[int] = Field(None, alias="referenciaNumerica")

    # Timestamps
    fecha_operacion: Optional[int] = Field(None, alias="fechaOperacion", description="YYYYMMDD")
    hora_operacion: Optional[str] = Field(None, alias="horaOperacion", description="HH:MM:SS")

    # Causa de devolucion (si aplica)
    causa_devolucion: Optional[int] = Field(None, alias="causaDevolucion")

    class Config:
        populate_by_name = True

    @property
    def amount_decimal(self) -> Decimal:
        """Monto en formato decimal."""
        return Decimal(self.monto) / Decimal(100)

    @property
    def is_liquidated(self) -> bool:
        """Verifica si la operacion fue liquidada."""
        return self.estado == 0 or self.estado == 1

    @property
    def is_returned(self) -> bool:
        """Verifica si la operacion fue devuelta."""
        return self.causa_devolucion is not None and self.causa_devolucion > 0


class STPBalanceResponse(BaseModel):
    """Respuesta de consulta de saldo."""
    account: str
    balance: Decimal
    available_balance: Decimal
    currency: str = "MXN"
    as_of: datetime

    class Config:
        from_attributes = True


class STPTransactionListResponse(BaseModel):
    """Lista de transacciones STP."""
    items: List[STPOrderResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ============ Internal Models ============

class STPSignatureData(BaseModel):
    """Datos para generar firma digital STP."""
    operation_type: str
    tracking_key: str
    sender_account: str
    beneficiary_account: str
    amount_cents: int
    sender_name: str
    payment_type: str
    beneficiary_name: str
    beneficiary_rfc: Optional[str] = None
    concept: str
    reference: str

    def to_sign_string(self) -> str:
        """
        Genera la cadena a firmar segun especificacion STP.

        Formato: ||campo1|campo2|...|campoN||
        """
        fields = [
            self.operation_type,
            self.tracking_key,
            self.sender_account,
            self.beneficiary_account,
            str(self.amount_cents),
            self.sender_name,
            self.payment_type,
            self.beneficiary_name,
            self.beneficiary_rfc or "",
            self.concept,
            self.reference,
        ]
        return "||" + "|".join(fields) + "||"


class STPReconciliationRecord(BaseModel):
    """Registro de conciliacion STP."""
    date: datetime
    tracking_key: str
    stp_id: int
    amount: Decimal
    status: STPTransactionStatus
    internal_id: Optional[str] = None
    matched: bool = False
    discrepancy: Optional[str] = None


# ============ Error Codes ============

STP_ERROR_CODES = {
    0: "Operacion exitosa",
    1: "Error de firma digital",
    2: "Cuenta ordenante no existe",
    3: "Cuenta beneficiario no existe",
    4: "Saldo insuficiente",
    5: "Cuenta bloqueada",
    6: "Monto excede limite",
    7: "Horario no permitido",
    8: "Operacion duplicada",
    9: "Tipo de cuenta invalido",
    10: "RFC invalido",
    11: "Nombre invalido",
    12: "Concepto invalido",
    13: "Referencia invalida",
    14: "Error de comunicacion",
    15: "Timeout",
    99: "Error desconocido",
}


# Causas de devolucion SPEI
STP_RETURN_CAUSES = {
    1: "Cuenta inexistente/bloqueada",
    2: "Cuenta cancelada",
    3: "Datos del beneficiario incorrectos",
    4: "Tipo de cuenta no corresponde",
    5: "Cuenta no acepta depositos",
    6: "Cuenta inhabilitada para SPEI",
    7: "Error en institucion destino",
    8: "Institucion no disponible",
    9: "Operacion no procesada",
    10: "Devolucion por solicitud del cliente",
}
