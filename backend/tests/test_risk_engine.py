"""
Tests para RiskEngine - Motor de Credit Scoring.

Cobertura de calculo de scores, niveles de riesgo y analisis completo.
"""

import pytest
from decimal import Decimal

from app.services.risk_engine import (
    RiskEngine,
    NivelRiesgo,
    AccionRiesgo,
    ScoreComponentes,
    AnalisisRiesgoCompleto,
)


class TestNivelRiesgoEnum:
    """Tests para enum NivelRiesgo."""

    def test_niveles_riesgo_values(self):
        """Test valores de NivelRiesgo."""
        assert NivelRiesgo.AAA.value == "AAA"
        assert NivelRiesgo.AA.value == "AA"
        assert NivelRiesgo.A.value == "A"
        assert NivelRiesgo.B.value == "B"
        assert NivelRiesgo.C.value == "C"

    def test_accion_riesgo_values(self):
        """Test valores de AccionRiesgo."""
        assert "automatica" in AccionRiesgo.APROBACION_AUTOMATICA.value.lower()
        assert "rechazo" in AccionRiesgo.RECHAZO_AUTOMATICO.value.lower()


class TestRiskEngineConstants:
    """Tests para constantes del motor de riesgo."""

    def test_pesos_componentes(self):
        """Test que los pesos suman 1."""
        total = (
            RiskEngine.PESO_CAPACIDAD +
            RiskEngine.PESO_HISTORIAL +
            RiskEngine.PESO_GARANTIAS
        )
        assert total == Decimal("1.00")

    def test_umbrales_ordenados(self):
        """Test que los umbrales estan ordenados."""
        assert RiskEngine.UMBRAL_AAA > RiskEngine.UMBRAL_AA
        assert RiskEngine.UMBRAL_AA > RiskEngine.UMBRAL_A
        assert RiskEngine.UMBRAL_A > RiskEngine.UMBRAL_B

    def test_tasas_base_definidas(self):
        """Test que hay tasas para cada nivel."""
        assert NivelRiesgo.AAA in RiskEngine.TASAS_BASE
        assert NivelRiesgo.AA in RiskEngine.TASAS_BASE
        assert NivelRiesgo.A in RiskEngine.TASAS_BASE
        assert NivelRiesgo.B in RiskEngine.TASAS_BASE
        assert NivelRiesgo.C in RiskEngine.TASAS_BASE


class TestScoreCapacidadPago:
    """Tests para calculo de score de capacidad de pago."""

    def test_score_excelente_dti_bajo(self):
        """Score excelente con DTI < 30%."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("100000"),
            gastos_fijos=Decimal("15000"),
            deuda_actual=Decimal("5000"),
            cuota_propuesta=Decimal("5000")
        )
        # DTI = 25000/100000 = 25% < 30%
        assert dti < Decimal("0.30")
        assert score >= 900

    def test_score_bueno_dti_medio(self):
        """Score bueno con DTI 30-40%."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("100000"),
            gastos_fijos=Decimal("25000"),
            deuda_actual=Decimal("5000"),
            cuota_propuesta=Decimal("5000")
        )
        # DTI = 35000/100000 = 35%
        assert Decimal("0.30") <= dti < Decimal("0.40")
        assert 700 <= score < 900

    def test_score_regular_dti_alto(self):
        """Score regular con DTI 40-50%."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("100000"),
            gastos_fijos=Decimal("35000"),
            deuda_actual=Decimal("5000"),
            cuota_propuesta=Decimal("5000")
        )
        # DTI = 45000/100000 = 45%
        assert Decimal("0.40") <= dti < Decimal("0.50")
        assert 500 <= score < 700

    def test_score_malo_dti_muy_alto(self):
        """Score malo con DTI > 50%."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("100000"),
            gastos_fijos=Decimal("45000"),
            deuda_actual=Decimal("10000"),
            cuota_propuesta=Decimal("5000")
        )
        # DTI = 60000/100000 = 60%
        assert dti >= Decimal("0.50")
        assert score < 500

    def test_score_cero_ingresos_cero(self):
        """Score 0 si ingresos son 0."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("0"),
            gastos_fijos=Decimal("10000"),
            deuda_actual=Decimal("5000"),
            cuota_propuesta=Decimal("5000")
        )
        assert score == 0
        assert dti == Decimal("1.0")

    def test_score_ingresos_negativos(self):
        """Score 0 si ingresos son negativos."""
        score, dti = RiskEngine.calcular_score_capacidad_pago(
            ingresos_mensuales=Decimal("-10000"),
            gastos_fijos=Decimal("5000"),
            deuda_actual=Decimal("0"),
            cuota_propuesta=Decimal("1000")
        )
        assert score == 0


class TestScoreHistorial:
    """Tests para calculo de score de historial crediticio."""

    def test_score_historial_excelente(self):
        """Score alto con historial impecable."""
        score = RiskEngine.calcular_score_historial(
            meses_actividad=72,  # 6 anos
            pagos_puntuales=60,
            pagos_atrasados=0,
            defaults_previos=0
        )
        assert score >= 800

    def test_score_historial_con_atrasos(self):
        """Score reducido por pagos atrasados."""
        score = RiskEngine.calcular_score_historial(
            meses_actividad=36,
            pagos_puntuales=30,
            pagos_atrasados=6,
            defaults_previos=0
        )
        # Penalizacion por atrasos
        assert score < 800

    def test_score_historial_con_defaults(self):
        """Score muy bajo con defaults previos."""
        score = RiskEngine.calcular_score_historial(
            meses_actividad=24,
            pagos_puntuales=20,
            pagos_atrasados=4,
            defaults_previos=2
        )
        # Penalizacion severa por defaults
        assert score < 600

    def test_score_historial_nuevo(self):
        """Score base para usuario nuevo."""
        score = RiskEngine.calcular_score_historial(
            meses_actividad=6,
            pagos_puntuales=5,
            pagos_atrasados=1,
            defaults_previos=0
        )
        # Score base + bonus por pagos
        assert 400 <= score <= 700

    def test_score_historial_con_buro(self):
        """Score integrado con buro de credito."""
        score = RiskEngine.calcular_score_historial(
            meses_actividad=36,
            pagos_puntuales=30,
            pagos_atrasados=0,
            defaults_previos=0,
            score_buro=750  # Buen score de buro
        )
        assert score >= 600

    def test_score_historial_min_max(self):
        """Score siempre entre 0 y 1000."""
        # Score muy malo
        score_bajo = RiskEngine.calcular_score_historial(
            meses_actividad=0,
            pagos_puntuales=0,
            pagos_atrasados=100,
            defaults_previos=10
        )
        assert score_bajo >= 0

        # Score muy bueno
        score_alto = RiskEngine.calcular_score_historial(
            meses_actividad=120,
            pagos_puntuales=100,
            pagos_atrasados=0,
            defaults_previos=0,
            score_buro=850
        )
        assert score_alto <= 1000


class TestScoreGarantias:
    """Tests para calculo de score de garantias."""

    def test_score_ltv_excelente(self):
        """Score alto con LTV < 60%."""
        score, ltv = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("500000"),
            valor_garantias=Decimal("1000000"),
            tipo_garantia="inmueble"
        )
        # LTV = 50%
        assert ltv < Decimal("0.60")
        assert score >= 900

    def test_score_ltv_bueno(self):
        """Score bueno con LTV 60-80%."""
        score, ltv = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("700000"),
            valor_garantias=Decimal("1000000"),
            tipo_garantia="inmueble"
        )
        # LTV = 70%
        assert Decimal("0.60") <= ltv < Decimal("0.80")
        assert 700 <= score < 950

    def test_score_ltv_regular(self):
        """Score regular con LTV 80-100%."""
        score, ltv = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("900000"),
            valor_garantias=Decimal("1000000"),
            tipo_garantia="vehiculo"
        )
        # LTV = 90%
        assert Decimal("0.80") <= ltv <= Decimal("1.00")
        assert 500 <= score < 750

    def test_score_sin_garantia(self):
        """Score bajo sin garantia."""
        score, ltv = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("100000"),
            valor_garantias=Decimal("0"),
            tipo_garantia="ninguna"
        )
        assert score < 300
        assert ltv == Decimal("999.99")

    def test_bonus_tipo_garantia_inmueble(self):
        """Bonus por garantia inmueble."""
        score_inmueble, _ = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("500000"),
            valor_garantias=Decimal("1000000"),
            tipo_garantia="inmueble"
        )
        score_vehiculo, _ = RiskEngine.calcular_score_garantias(
            monto_solicitado=Decimal("500000"),
            valor_garantias=Decimal("1000000"),
            tipo_garantia="vehiculo"
        )
        # Inmueble tiene mayor bonus
        assert score_inmueble > score_vehiculo


class TestScoreTotal:
    """Tests para calculo de score total ponderado."""

    def test_score_total_formula(self):
        """Test formula S = C*0.40 + H*0.35 + G*0.25."""
        result = RiskEngine.calcular_score_total(
            score_capacidad=1000,
            score_historial=1000,
            score_garantias=1000
        )
        # 1000*0.40 + 1000*0.35 + 1000*0.25 = 1000
        assert result.score_total == 1000

    def test_score_total_nivel_aaa(self):
        """Nivel AAA para score >= 800."""
        result = RiskEngine.calcular_score_total(
            score_capacidad=900,
            score_historial=850,
            score_garantias=800
        )
        assert result.nivel_riesgo == NivelRiesgo.AAA
        assert result.accion == AccionRiesgo.APROBACION_AUTOMATICA

    def test_score_total_nivel_aa(self):
        """Nivel AA para score 700-799."""
        result = RiskEngine.calcular_score_total(
            score_capacidad=750,
            score_historial=750,
            score_garantias=750
        )
        assert result.nivel_riesgo == NivelRiesgo.AA

    def test_score_total_nivel_c(self):
        """Nivel C para score < 500."""
        result = RiskEngine.calcular_score_total(
            score_capacidad=300,
            score_historial=400,
            score_garantias=200
        )
        assert result.nivel_riesgo == NivelRiesgo.C
        assert result.accion == AccionRiesgo.RECHAZO_AUTOMATICO

    def test_score_componentes_dataclass(self):
        """Test campos de ScoreComponentes."""
        result = RiskEngine.calcular_score_total(
            score_capacidad=800,
            score_historial=700,
            score_garantias=600
        )
        assert result.score_capacidad_pago == 800
        assert result.score_historial == 700
        assert result.score_garantias == 600
        assert isinstance(result.nivel_riesgo, NivelRiesgo)
        assert isinstance(result.accion, AccionRiesgo)


class TestProbabilidadDefault:
    """Tests para calculo de probabilidad de default."""

    def test_pd_score_alto(self):
        """PD baja para score alto."""
        pd = RiskEngine.calcular_probabilidad_default(900)
        assert pd < Decimal("0.05")

    def test_pd_score_bajo(self):
        """PD alta para score bajo."""
        pd = RiskEngine.calcular_probabilidad_default(300)
        assert pd > Decimal("0.20")

    def test_pd_score_medio(self):
        """PD media para score medio."""
        pd = RiskEngine.calcular_probabilidad_default(600)
        assert Decimal("0.05") < pd < Decimal("0.20")

    def test_pd_precision(self):
        """PD tiene precision de 4 decimales."""
        pd = RiskEngine.calcular_probabilidad_default(750)
        # Verificar que tiene formato correcto
        assert pd == pd.quantize(Decimal("0.0001"))


class TestDataclasses:
    """Tests para dataclasses del modulo."""

    def test_score_componentes_creation(self):
        """Test creacion de ScoreComponentes."""
        sc = ScoreComponentes(
            score_capacidad_pago=800,
            score_historial=750,
            score_garantias=700,
            score_total=758,
            nivel_riesgo=NivelRiesgo.AA,
            accion=AccionRiesgo.APROBACION_REVISION_MINIMA
        )
        assert sc.score_total == 758
        assert sc.nivel_riesgo == NivelRiesgo.AA

    def test_analisis_riesgo_completo_creation(self):
        """Test creacion de AnalisisRiesgoCompleto."""
        analisis = AnalisisRiesgoCompleto(
            score=ScoreComponentes(
                score_capacidad_pago=800,
                score_historial=750,
                score_garantias=700,
                score_total=758,
                nivel_riesgo=NivelRiesgo.AA,
                accion=AccionRiesgo.APROBACION_REVISION_MINIMA
            ),
            probabilidad_default=Decimal("0.05"),
            probabilidad_exito=Decimal("0.95"),
            ratio_deuda_ingreso=Decimal("0.35"),
            loan_to_value=Decimal("0.70"),
            tasa_interes_sugerida=Decimal("0.10"),
            monto_maximo_aprobado=Decimal("500000"),
            requiere_garantias_adicionales=False,
            observaciones=["Buen perfil crediticio"]
        )
        assert analisis.probabilidad_default == Decimal("0.05")
        assert analisis.requiere_garantias_adicionales is False
