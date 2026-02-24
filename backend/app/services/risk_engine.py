"""
Motor de Analisis de Riesgo y Credit Scoring.
Implementa formula: S = (C * 0.40) + (H * 0.35) + (G * 0.25)
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class NivelRiesgo(str, Enum):
    """Niveles de riesgo basados en score."""
    AAA = "AAA"  # 800-1000: Aprobacion automatica
    AA = "AA"    # 700-799: Aprobacion con revision minima
    A = "A"      # 600-699: Revision manual
    B = "B"      # 500-599: Revision exhaustiva
    C = "C"      # < 500: Rechazo automatico


class AccionRiesgo(str, Enum):
    """Acciones automaticas basadas en riesgo."""
    APROBACION_AUTOMATICA = "Aprobacion automatica, tasa preferencial"
    APROBACION_REVISION_MINIMA = "Aprobacion con revision minima"
    REVISION_MANUAL = "Requiere revision por Analista"
    REVISION_COMITE = "Requiere revision por Comite de Credito"
    RECHAZO_AUTOMATICO = "Rechazo automatico por alto riesgo"


@dataclass
class ScoreComponentes:
    """Componentes del credit score."""
    score_capacidad_pago: int      # C: 40%
    score_historial: int           # H: 35%
    score_garantias: int           # G: 25%
    score_total: int
    nivel_riesgo: NivelRiesgo
    accion: AccionRiesgo


@dataclass
class AnalisisRiesgoCompleto:
    """Resultado completo del analisis de riesgo."""
    score: ScoreComponentes
    probabilidad_default: Decimal
    probabilidad_exito: Decimal
    ratio_deuda_ingreso: Decimal
    loan_to_value: Decimal
    tasa_interes_sugerida: Decimal
    monto_maximo_aprobado: Decimal
    requiere_garantias_adicionales: bool
    observaciones: list


class RiskEngine:
    """
    Motor de Credit Scoring y Analisis de Riesgo.
    Pesos: Capacidad (40%), Historial (35%), Garantias (25%)
    """

    # Pesos de los componentes
    PESO_CAPACIDAD = Decimal("0.40")
    PESO_HISTORIAL = Decimal("0.35")
    PESO_GARANTIAS = Decimal("0.25")

    # Umbrales de score
    UMBRAL_AAA = 800
    UMBRAL_AA = 700
    UMBRAL_A = 600
    UMBRAL_B = 500

    # Tasas base por nivel de riesgo
    TASAS_BASE = {
        NivelRiesgo.AAA: Decimal("0.08"),   # 8%
        NivelRiesgo.AA: Decimal("0.10"),    # 10%
        NivelRiesgo.A: Decimal("0.12"),     # 12%
        NivelRiesgo.B: Decimal("0.15"),     # 15%
        NivelRiesgo.C: Decimal("0.20"),     # 20%
    }

    @classmethod
    def calcular_score_capacidad_pago(
        cls,
        ingresos_mensuales: Decimal,
        gastos_fijos: Decimal,
        deuda_actual: Decimal,
        cuota_propuesta: Decimal
    ) -> Tuple[int, Decimal]:
        """
        Calcula score de capacidad de pago (0-1000).

        Ratio Deuda/Ingreso (DTI):
        - < 30%: Excelente (900-1000)
        - 30-40%: Bueno (700-899)
        - 40-50%: Regular (500-699)
        - > 50%: Malo (0-499)
        """
        if ingresos_mensuales <= 0:
            return 0, Decimal("1.0")

        # Calcular DTI incluyendo la nueva cuota
        deuda_total = gastos_fijos + deuda_actual + cuota_propuesta
        dti = deuda_total / ingresos_mensuales

        # Mapear DTI a score
        if dti < Decimal("0.30"):
            score = int(900 + (Decimal("0.30") - dti) * 333)
            score = min(score, 1000)
        elif dti < Decimal("0.40"):
            score = int(700 + (Decimal("0.40") - dti) * 2000)
        elif dti < Decimal("0.50"):
            score = int(500 + (Decimal("0.50") - dti) * 2000)
        else:
            score = int(max(0, 500 - (dti - Decimal("0.50")) * 1000))

        return score, dti.quantize(Decimal("0.0001"))

    @classmethod
    def calcular_score_historial(
        cls,
        meses_actividad: int,
        pagos_puntuales: int,
        pagos_atrasados: int,
        defaults_previos: int,
        score_buro: Optional[int] = None  # Score de buro de credito externo
    ) -> int:
        """
        Calcula score de historial crediticio (0-1000).
        """
        score = 500  # Base

        # Antiguedad (hasta +200)
        if meses_actividad >= 60:
            score += 200
        elif meses_actividad >= 36:
            score += 150
        elif meses_actividad >= 24:
            score += 100
        elif meses_actividad >= 12:
            score += 50

        # Pagos puntuales (hasta +200)
        total_pagos = pagos_puntuales + pagos_atrasados
        if total_pagos > 0:
            ratio_puntualidad = pagos_puntuales / total_pagos
            score += int(ratio_puntualidad * 200)

        # Penalizacion por atrasos
        score -= pagos_atrasados * 10

        # Penalizacion severa por defaults
        score -= defaults_previos * 100

        # Integrar score de buro (si disponible)
        if score_buro is not None:
            # Normalizar buro (300-850) a (0-1000)
            buro_normalizado = int((score_buro - 300) / 550 * 1000)
            score = int((score + buro_normalizado) / 2)

        return max(0, min(1000, score))

    @classmethod
    def calcular_score_garantias(
        cls,
        monto_solicitado: Decimal,
        valor_garantias: Decimal,
        tipo_garantia: str  # inmueble, vehiculo, deposito, ninguna
    ) -> Tuple[int, Decimal]:
        """
        Calcula score de garantias (0-1000).

        LTV (Loan to Value):
        - < 60%: Excelente (900-1000)
        - 60-80%: Bueno (700-899)
        - 80-100%: Regular (500-699)
        - > 100%: Malo (0-499)
        """
        if valor_garantias <= 0 or monto_solicitado <= 0:
            # Sin garantia
            if tipo_garantia == "ninguna":
                return 200, Decimal("999.99")
            return 300, Decimal("999.99")

        ltv = monto_solicitado / valor_garantias

        # Mapear LTV a score
        if ltv < Decimal("0.60"):
            score = 900 + int((Decimal("0.60") - ltv) * 166)
            score = min(score, 1000)
        elif ltv < Decimal("0.80"):
            score = 700 + int((Decimal("0.80") - ltv) * 1000)
        elif ltv <= Decimal("1.00"):
            score = 500 + int((Decimal("1.00") - ltv) * 1000)
        else:
            score = max(0, int(500 - (ltv - 1) * 500))

        # Bonus por tipo de garantia
        bonus = {
            "inmueble": 50,
            "deposito": 40,
            "vehiculo": 20,
            "equipo": 10,
            "ninguna": 0
        }
        score += bonus.get(tipo_garantia, 0)

        return min(1000, score), ltv.quantize(Decimal("0.0001"))

    @classmethod
    def calcular_score_total(
        cls,
        score_capacidad: int,
        score_historial: int,
        score_garantias: int
    ) -> ScoreComponentes:
        """
        Calcula el score total ponderado.

        S = (C * 0.40) + (H * 0.35) + (G * 0.25)
        """
        score_total = int(
            score_capacidad * float(cls.PESO_CAPACIDAD) +
            score_historial * float(cls.PESO_HISTORIAL) +
            score_garantias * float(cls.PESO_GARANTIAS)
        )

        # Determinar nivel de riesgo
        if score_total >= cls.UMBRAL_AAA:
            nivel = NivelRiesgo.AAA
            accion = AccionRiesgo.APROBACION_AUTOMATICA
        elif score_total >= cls.UMBRAL_AA:
            nivel = NivelRiesgo.AA
            accion = AccionRiesgo.APROBACION_REVISION_MINIMA
        elif score_total >= cls.UMBRAL_A:
            nivel = NivelRiesgo.A
            accion = AccionRiesgo.REVISION_MANUAL
        elif score_total >= cls.UMBRAL_B:
            nivel = NivelRiesgo.B
            accion = AccionRiesgo.REVISION_COMITE
        else:
            nivel = NivelRiesgo.C
            accion = AccionRiesgo.RECHAZO_AUTOMATICO

        return ScoreComponentes(
            score_capacidad_pago=score_capacidad,
            score_historial=score_historial,
            score_garantias=score_garantias,
            score_total=score_total,
            nivel_riesgo=nivel,
            accion=accion
        )

    @classmethod
    def calcular_probabilidad_default(cls, score: int) -> Decimal:
        """
        Estima probabilidad de default basada en score.
        Curva exponencial inversa.
        """
        # PD = e^(-score/200) simplificado
        import math
        pd = math.exp(-score / 250)
        return Decimal(str(pd)).quantize(Decimal("0.0001"))

    @classmethod
    def analizar_riesgo_completo(
        cls,
        # Datos financieros
        ingresos_mensuales: Decimal,
        gastos_fijos: Decimal,
        deuda_actual: Decimal,
        # Solicitud
        monto_solicitado: Decimal,
        plazo_meses: int,
        tasa_interes_propuesta: Decimal,
        # Historial
        meses_actividad: int,
        pagos_puntuales: int,
        pagos_atrasados: int,
        defaults_previos: int,
        score_buro: Optional[int] = None,
        # Garantias
        valor_garantias: Decimal = Decimal("0"),
        tipo_garantia: str = "ninguna"
    ) -> AnalisisRiesgoCompleto:
        """
        Realiza analisis de riesgo completo para una solicitud.
        """
        # Calcular cuota mensual estimada
        if plazo_meses > 0 and tasa_interes_propuesta > 0:
            tasa_mensual = tasa_interes_propuesta / 12
            cuota = monto_solicitado * (
                tasa_mensual * (1 + tasa_mensual) ** plazo_meses
            ) / ((1 + tasa_mensual) ** plazo_meses - 1)
        else:
            cuota = monto_solicitado / max(plazo_meses, 1)

        # Calcular scores individuales
        score_capacidad, dti = cls.calcular_score_capacidad_pago(
            ingresos_mensuales, gastos_fijos, deuda_actual, cuota
        )

        score_historial = cls.calcular_score_historial(
            meses_actividad, pagos_puntuales, pagos_atrasados,
            defaults_previos, score_buro
        )

        score_garantias, ltv = cls.calcular_score_garantias(
            monto_solicitado, valor_garantias, tipo_garantia
        )

        # Score total
        score = cls.calcular_score_total(
            score_capacidad, score_historial, score_garantias
        )

        # Probabilidades
        pd = cls.calcular_probabilidad_default(score.score_total)
        pe = (1 - pd).quantize(Decimal("0.0001"))

        # Tasa sugerida
        tasa_sugerida = cls.TASAS_BASE[score.nivel_riesgo]

        # Monto maximo basado en capacidad de pago
        capacidad_cuota = (ingresos_mensuales - gastos_fijos - deuda_actual) * Decimal("0.40")
        if capacidad_cuota > 0 and tasa_interes_propuesta > 0:
            tasa_m = tasa_interes_propuesta / 12
            monto_max = capacidad_cuota * (
                ((1 + tasa_m) ** plazo_meses - 1) / (tasa_m * (1 + tasa_m) ** plazo_meses)
            )
        else:
            monto_max = capacidad_cuota * plazo_meses

        # Observaciones
        observaciones = []

        if dti > Decimal("0.40"):
            observaciones.append(f"DTI alto ({dti:.1%}). Considerar reducir monto.")

        if ltv > Decimal("0.80"):
            observaciones.append(f"LTV alto ({ltv:.1%}). Requiere garantias adicionales.")

        if defaults_previos > 0:
            observaciones.append(f"Historial con {defaults_previos} default(s) previo(s).")

        if score.score_total < cls.UMBRAL_A:
            observaciones.append("Score bajo. Se recomienda revision exhaustiva.")

        return AnalisisRiesgoCompleto(
            score=score,
            probabilidad_default=pd,
            probabilidad_exito=pe,
            ratio_deuda_ingreso=dti,
            loan_to_value=ltv,
            tasa_interes_sugerida=tasa_sugerida,
            monto_maximo_aprobado=monto_max.quantize(Decimal("0.01")),
            requiere_garantias_adicionales=ltv > Decimal("0.80"),
            observaciones=observaciones
        )
