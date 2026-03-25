"""
Tests para FinancialEngine.

Cobertura de calculos VAN, TIR, ROI, Payback e Indice de Rentabilidad.
"""

import pytest
from decimal import Decimal
from typing import List

from app.services.financial_engine import (
    FinancialEngine,
    EvaluacionFinanciera,
    AnalisisSensibilidad,
)


class TestCalcularVAN:
    """Tests para calculo de Valor Actual Neto."""

    def test_van_positivo(self):
        """VAN positivo indica proyecto rentable."""
        inversion = Decimal("100000")
        flujos = [Decimal("30000")] * 5  # 5 anos de 30k
        tasa = Decimal("0.10")  # 10%

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        # VAN debe ser positivo
        assert van > 0
        # Valor aproximado: 30000 * (1-(1.1)^-5)/0.1 - 100000 = 13723.60
        assert Decimal("13000") < van < Decimal("14500")

    def test_van_negativo(self):
        """VAN negativo indica proyecto no rentable."""
        inversion = Decimal("100000")
        flujos = [Decimal("10000")] * 5  # Flujos bajos
        tasa = Decimal("0.10")

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        assert van < 0

    def test_van_cero_inversion(self):
        """VAN con inversion cero."""
        inversion = Decimal("0")
        flujos = [Decimal("10000")] * 3
        tasa = Decimal("0.10")

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        # Solo flujos positivos = VAN positivo
        assert van > 0

    def test_van_flujos_negativos(self):
        """VAN con flujos negativos (perdidas)."""
        inversion = Decimal("50000")
        flujos = [Decimal("-10000")] * 3  # Perdidas cada ano
        tasa = Decimal("0.10")

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        assert van < 0

    def test_van_tasa_cero(self):
        """VAN con tasa de descuento cero."""
        inversion = Decimal("100000")
        flujos = [Decimal("30000")] * 5
        tasa = Decimal("0")

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        # Sin descuento: VAN = sum(flujos) - inversion = 150000 - 100000 = 50000
        assert van == Decimal("50000.00")

    def test_van_precision_decimal(self):
        """Verifica precision de 2 decimales."""
        inversion = Decimal("12345.67")
        flujos = [Decimal("5000.123")] * 3
        tasa = Decimal("0.085")

        van = FinancialEngine.calcular_van(inversion, flujos, tasa)

        # Verificar que tiene 2 decimales
        assert van == van.quantize(Decimal("0.01"))


class TestCalcularTIR:
    """Tests para calculo de Tasa Interna de Retorno."""

    def test_tir_proyecto_rentable(self):
        """TIR de proyecto con buenos retornos."""
        inversion = Decimal("100000")
        flujos = [Decimal("40000")] * 5

        tir = FinancialEngine.calcular_tir(inversion, flujos)

        assert tir is not None
        # TIR aproximada: ~28%
        assert Decimal("0.25") < tir < Decimal("0.35")

    def test_tir_proyecto_marginal(self):
        """TIR de proyecto marginal."""
        inversion = Decimal("100000")
        flujos = [Decimal("25000")] * 5

        tir = FinancialEngine.calcular_tir(inversion, flujos)

        assert tir is not None
        # TIR aproximada: ~8%
        assert Decimal("0.05") < tir < Decimal("0.12")

    def test_tir_flujos_insuficientes(self):
        """TIR cuando flujos no recuperan inversion."""
        inversion = Decimal("100000")
        flujos = [Decimal("5000")] * 5  # Solo 25k total

        tir = FinancialEngine.calcular_tir(inversion, flujos)

        # TIR negativa o None
        assert tir is None or tir < 0

    def test_tir_un_solo_flujo(self):
        """TIR con un solo flujo."""
        inversion = Decimal("100000")
        flujos = [Decimal("150000")]  # 50% ganancia en 1 periodo

        tir = FinancialEngine.calcular_tir(inversion, flujos)

        assert tir is not None
        assert tir == Decimal("0.5")  # 50%

    def test_tir_precision(self):
        """Verifica precision de 4 decimales para tasas."""
        inversion = Decimal("100000")
        flujos = [Decimal("30000")] * 5

        tir = FinancialEngine.calcular_tir(inversion, flujos)

        assert tir is not None
        assert tir == tir.quantize(Decimal("0.0001"))


class TestCalcularROI:
    """Tests para calculo de Retorno sobre Inversion."""

    def test_roi_positivo(self):
        """ROI positivo (ganancia)."""
        inversion = Decimal("100000")
        retorno = Decimal("150000")

        roi = FinancialEngine.calcular_roi(inversion, retorno)

        assert roi == Decimal("0.5")  # 50%

    def test_roi_negativo(self):
        """ROI negativo (perdida)."""
        inversion = Decimal("100000")
        retorno = Decimal("80000")

        roi = FinancialEngine.calcular_roi(inversion, retorno)

        assert roi == Decimal("-0.2")  # -20%

    def test_roi_cero(self):
        """ROI cero (recuperacion exacta)."""
        inversion = Decimal("100000")
        retorno = Decimal("100000")

        roi = FinancialEngine.calcular_roi(inversion, retorno)

        assert roi == Decimal("0")

    def test_roi_inversion_cero(self):
        """ROI con inversion cero."""
        inversion = Decimal("0")
        retorno = Decimal("50000")

        roi = FinancialEngine.calcular_roi(inversion, retorno)

        assert roi == Decimal("0")

    def test_roi_100_percent(self):
        """ROI del 100% (duplicar inversion)."""
        inversion = Decimal("50000")
        retorno = Decimal("100000")

        roi = FinancialEngine.calcular_roi(inversion, retorno)

        assert roi == Decimal("1.0")


class TestCalcularPayback:
    """Tests para calculo de Periodo de Recuperacion."""

    def test_payback_exacto(self):
        """Payback cuando flujo coincide con inversion."""
        inversion = Decimal("100000")
        flujos = [Decimal("25000")] * 4  # 4 anos exactos

        payback = FinancialEngine.calcular_payback(inversion, flujos)

        assert payback == Decimal("4.00")

    def test_payback_fraccionario(self):
        """Payback con periodo fraccionario."""
        inversion = Decimal("100000")
        flujos = [Decimal("40000")] * 5

        payback = FinancialEngine.calcular_payback(inversion, flujos)

        # 2 anos completos = 80k, falta 20k del tercer ano (40k)
        # 2 + 20/40 = 2.5 anos
        assert payback == Decimal("2.50")

    def test_payback_primer_periodo(self):
        """Payback en primer periodo."""
        inversion = Decimal("50000")
        flujos = [Decimal("100000")]

        payback = FinancialEngine.calcular_payback(inversion, flujos)

        # Recupera en la mitad del primer periodo
        assert payback == Decimal("0.50")

    def test_payback_no_recupera(self):
        """Payback None cuando no se recupera."""
        inversion = Decimal("100000")
        flujos = [Decimal("10000")] * 5  # Solo 50k total

        payback = FinancialEngine.calcular_payback(inversion, flujos)

        assert payback is None

    def test_payback_flujos_variables(self):
        """Payback con flujos variables."""
        inversion = Decimal("100000")
        flujos = [
            Decimal("20000"),
            Decimal("30000"),
            Decimal("40000"),
            Decimal("50000")
        ]

        payback = FinancialEngine.calcular_payback(inversion, flujos)

        # Ano 1: 20k, Ano 2: 50k, Ano 3: 90k, Ano 4: 140k (recupera en ano 4)
        # 3 + 10/50 = 3.2 anos
        assert payback is not None
        assert Decimal("3") < payback < Decimal("4")


class TestCalcularIndiceRentabilidad:
    """Tests para calculo de Indice de Rentabilidad."""

    def test_ir_proyecto_rentable(self):
        """IR > 1 indica proyecto rentable."""
        van = Decimal("25000")
        inversion = Decimal("100000")

        ir = FinancialEngine.calcular_indice_rentabilidad(van, inversion)

        assert ir == Decimal("1.25")
        assert ir > 1

    def test_ir_proyecto_no_rentable(self):
        """IR < 1 indica proyecto no rentable."""
        van = Decimal("-20000")
        inversion = Decimal("100000")

        ir = FinancialEngine.calcular_indice_rentabilidad(van, inversion)

        assert ir == Decimal("0.80")
        assert ir < 1

    def test_ir_marginal(self):
        """IR = 1 indica VAN = 0."""
        van = Decimal("0")
        inversion = Decimal("100000")

        ir = FinancialEngine.calcular_indice_rentabilidad(van, inversion)

        assert ir == Decimal("1.00")

    def test_ir_inversion_cero(self):
        """IR con inversion cero."""
        van = Decimal("50000")
        inversion = Decimal("0")

        ir = FinancialEngine.calcular_indice_rentabilidad(van, inversion)

        assert ir == Decimal("0")


class TestEvaluarProyecto:
    """Tests para evaluacion completa de proyectos."""

    def test_proyecto_viable(self):
        """Evaluacion de proyecto viable."""
        inversion = Decimal("500000")
        flujos = [Decimal("150000")] * 5
        tasa = Decimal("0.10")

        eval = FinancialEngine.evaluar_proyecto(inversion, flujos, tasa)

        assert isinstance(eval, EvaluacionFinanciera)
        assert eval.van > 0
        assert eval.tir is not None
        assert eval.tir > tasa
        assert eval.es_viable is True
        assert eval.indice_rentabilidad > 1

    def test_proyecto_no_viable(self):
        """Evaluacion de proyecto no viable."""
        inversion = Decimal("500000")
        flujos = [Decimal("50000")] * 5
        tasa = Decimal("0.15")

        eval = FinancialEngine.evaluar_proyecto(inversion, flujos, tasa)

        assert eval.van < 0
        assert eval.es_viable is False
        assert eval.indice_rentabilidad < 1

    def test_proyecto_todos_indicadores(self):
        """Verifica que todos los indicadores se calculen."""
        inversion = Decimal("100000")
        flujos = [Decimal("30000")] * 5
        tasa = Decimal("0.10")

        eval = FinancialEngine.evaluar_proyecto(inversion, flujos, tasa)

        # Verificar todos los campos
        assert eval.inversion_inicial == inversion
        assert eval.tasa_descuento == tasa
        assert eval.van is not None
        assert eval.tir is not None
        assert eval.roi is not None
        assert eval.payback_period is not None
        assert eval.indice_rentabilidad is not None
        assert isinstance(eval.flujos_descontados, list)
        assert isinstance(eval.es_viable, bool)
        assert isinstance(eval.mensaje, str)

    def test_proyecto_con_tasa_minima(self):
        """Evaluacion con tasa minima aceptable."""
        inversion = Decimal("100000")
        flujos = [Decimal("25000")] * 5
        tasa = Decimal("0.05")
        tasa_minima = Decimal("0.12")

        eval = FinancialEngine.evaluar_proyecto(
            inversion, flujos, tasa,
            tasa_minima_aceptable=tasa_minima
        )

        # VAN positivo pero TIR < tasa minima
        assert eval.van > 0
        if eval.tir:
            assert eval.tir < tasa_minima


class TestDataclasses:
    """Tests para dataclasses del modulo."""

    def test_evaluacion_financiera_dataclass(self):
        """Test creacion de EvaluacionFinanciera."""
        eval = EvaluacionFinanciera(
            inversion_inicial=Decimal("100000"),
            tasa_descuento=Decimal("0.10"),
            van=Decimal("25000"),
            tir=Decimal("0.15"),
            roi=Decimal("0.50"),
            payback_period=Decimal("3.5"),
            indice_rentabilidad=Decimal("1.25"),
            flujos_descontados=[Decimal("27273"), Decimal("24793")],
            es_viable=True,
            mensaje="Proyecto viable"
        )

        assert eval.inversion_inicial == Decimal("100000")
        assert eval.es_viable is True

    def test_analisis_sensibilidad_dataclass(self):
        """Test creacion de AnalisisSensibilidad."""
        analisis = AnalisisSensibilidad(
            escenario="optimista",
            variacion_flujos=0.20,
            van=Decimal("50000"),
            tir=Decimal("0.22"),
            es_viable=True
        )

        assert analisis.escenario == "optimista"
        assert analisis.variacion_flujos == 0.20
        assert analisis.es_viable is True


class TestPrecisionConstants:
    """Tests para constantes de precision."""

    def test_precision_moneda(self):
        """Precision de 2 decimales para moneda."""
        assert FinancialEngine.PRECISION == Decimal("0.01")

    def test_precision_tasa(self):
        """Precision de 4 decimales para tasas."""
        assert FinancialEngine.PRECISION_TASA == Decimal("0.0001")
