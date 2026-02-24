"""
Motor de Evaluacion Financiera.
Calcula VAN, TIR, ROI, Payback, Indice de Rentabilidad.
Precision financiera con Decimal y numpy_financial.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import numpy_financial as npf


@dataclass
class EvaluacionFinanciera:
    """Resultado de la evaluacion financiera."""
    inversion_inicial: Decimal
    tasa_descuento: Decimal
    van: Decimal
    tir: Optional[Decimal]
    roi: Decimal
    payback_period: Optional[Decimal]  # En periodos
    indice_rentabilidad: Decimal
    flujos_descontados: List[Decimal]
    es_viable: bool
    mensaje: str


@dataclass
class AnalisisSensibilidad:
    """Escenarios de sensibilidad."""
    escenario: str  # pesimista, base, optimista
    variacion_flujos: float  # -20%, 0%, +20%
    van: Decimal
    tir: Optional[Decimal]
    es_viable: bool


class FinancialEngine:
    """
    Motor de calculos financieros de grado bancario.
    Usa numpy_financial para precision y velocidad.
    """

    PRECISION = Decimal("0.01")  # 2 decimales para moneda
    PRECISION_TASA = Decimal("0.0001")  # 4 decimales para tasas

    @staticmethod
    def calcular_van(
        inversion_inicial: Decimal,
        flujos_caja: List[Decimal],
        tasa_descuento: Decimal
    ) -> Decimal:
        """
        Calcula el Valor Actual Neto (VAN/NPV).

        VAN = -I0 + SUM(FCt / (1+r)^t)

        Args:
            inversion_inicial: Monto inicial invertido (positivo)
            flujos_caja: Lista de flujos por periodo
            tasa_descuento: Tasa de descuento (ej: 0.12 para 12%)

        Returns:
            VAN calculado
        """
        # Convertir a float para numpy
        rate = float(tasa_descuento)
        cashflows = [-float(inversion_inicial)] + [float(f) for f in flujos_caja]

        # Calcular NPV
        van = npf.npv(rate, cashflows)

        return Decimal(str(van)).quantize(
            FinancialEngine.PRECISION,
            rounding=ROUND_HALF_UP
        )

    @staticmethod
    def calcular_tir(
        inversion_inicial: Decimal,
        flujos_caja: List[Decimal]
    ) -> Optional[Decimal]:
        """
        Calcula la Tasa Interna de Retorno (TIR/IRR).

        La TIR es la tasa que hace VAN = 0.

        Returns:
            TIR o None si no converge
        """
        cashflows = [-float(inversion_inicial)] + [float(f) for f in flujos_caja]

        try:
            tir = npf.irr(cashflows)

            # Verificar que sea un numero valido
            if np.isnan(tir) or np.isinf(tir):
                return None

            return Decimal(str(tir)).quantize(
                FinancialEngine.PRECISION_TASA,
                rounding=ROUND_HALF_UP
            )
        except Exception:
            return None

    @staticmethod
    def calcular_roi(
        inversion_inicial: Decimal,
        retorno_total: Decimal
    ) -> Decimal:
        """
        Calcula el Retorno sobre la Inversion (ROI).

        ROI = (Retorno - Inversion) / Inversion
        """
        if inversion_inicial == 0:
            return Decimal("0")

        roi = (retorno_total - inversion_inicial) / inversion_inicial

        return roi.quantize(
            FinancialEngine.PRECISION_TASA,
            rounding=ROUND_HALF_UP
        )

    @staticmethod
    def calcular_payback(
        inversion_inicial: Decimal,
        flujos_caja: List[Decimal]
    ) -> Optional[Decimal]:
        """
        Calcula el Periodo de Recuperacion (Payback).

        Retorna el numero de periodos para recuperar la inversion.
        """
        flujo_acumulado = Decimal("0")

        for periodo, flujo in enumerate(flujos_caja, start=1):
            flujo_acumulado += flujo

            if flujo_acumulado >= inversion_inicial:
                # Interpolacion para periodo exacto
                exceso = flujo_acumulado - inversion_inicial
                fraccion = 1 - (exceso / flujo) if flujo > 0 else Decimal("0")
                payback = Decimal(str(periodo - 1)) + fraccion

                return payback.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

        # No se recupera en el periodo analizado
        return None

    @staticmethod
    def calcular_indice_rentabilidad(
        van: Decimal,
        inversion_inicial: Decimal
    ) -> Decimal:
        """
        Calcula el Indice de Rentabilidad (PI/IR).

        PI = 1 + (VAN / Inversion)
        Si PI > 1, el proyecto es rentable.
        """
        if inversion_inicial == 0:
            return Decimal("0")

        pi = 1 + (van / inversion_inicial)

        return pi.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    @classmethod
    def evaluar_proyecto(
        cls,
        inversion_inicial: Decimal,
        flujos_caja: List[Decimal],
        tasa_descuento: Decimal,
        tasa_minima_aceptable: Decimal = Decimal("0.10")
    ) -> EvaluacionFinanciera:
        """
        Evaluacion completa de un proyecto de inversion.

        Args:
            inversion_inicial: Inversion inicial
            flujos_caja: Flujos de caja proyectados
            tasa_descuento: Tasa de descuento (WACC o requerida)
            tasa_minima_aceptable: TIR minima para considerar viable

        Returns:
            EvaluacionFinanciera con todos los indicadores
        """
        # Calcular indicadores
        van = cls.calcular_van(inversion_inicial, flujos_caja, tasa_descuento)
        tir = cls.calcular_tir(inversion_inicial, flujos_caja)

        retorno_total = sum(flujos_caja)
        roi = cls.calcular_roi(inversion_inicial, retorno_total)

        payback = cls.calcular_payback(inversion_inicial, flujos_caja)
        indice_rentabilidad = cls.calcular_indice_rentabilidad(van, inversion_inicial)

        # Calcular flujos descontados
        flujos_descontados = []
        for t, flujo in enumerate(flujos_caja, start=1):
            fd = flujo / ((1 + tasa_descuento) ** t)
            flujos_descontados.append(fd.quantize(cls.PRECISION))

        # Determinar viabilidad
        es_viable = (
            van > 0 and
            (tir is None or tir >= tasa_minima_aceptable) and
            indice_rentabilidad > 1
        )

        # Mensaje de evaluacion
        if van > 0 and (tir and tir >= tasa_minima_aceptable):
            mensaje = "Proyecto VIABLE: VAN positivo y TIR superior a la tasa minima."
        elif van > 0:
            mensaje = "Proyecto con VAN positivo pero TIR baja. Revisar supuestos."
        elif van == 0:
            mensaje = "Proyecto neutro: VAN igual a cero."
        else:
            mensaje = "Proyecto NO VIABLE: VAN negativo."

        return EvaluacionFinanciera(
            inversion_inicial=inversion_inicial,
            tasa_descuento=tasa_descuento,
            van=van,
            tir=tir,
            roi=roi,
            payback_period=payback,
            indice_rentabilidad=indice_rentabilidad,
            flujos_descontados=flujos_descontados,
            es_viable=es_viable,
            mensaje=mensaje
        )

    @classmethod
    def analisis_sensibilidad(
        cls,
        inversion_inicial: Decimal,
        flujos_caja_base: List[Decimal],
        tasa_descuento: Decimal,
        variaciones: List[float] = [-0.20, 0, 0.20]
    ) -> List[AnalisisSensibilidad]:
        """
        Analisis de sensibilidad con escenarios.

        Calcula VAN y TIR bajo diferentes supuestos de flujos.
        """
        escenarios = ["pesimista", "base", "optimista"]
        resultados = []

        for i, variacion in enumerate(variaciones):
            # Ajustar flujos
            flujos_ajustados = [
                Decimal(str(float(f) * (1 + variacion)))
                for f in flujos_caja_base
            ]

            van = cls.calcular_van(inversion_inicial, flujos_ajustados, tasa_descuento)
            tir = cls.calcular_tir(inversion_inicial, flujos_ajustados)

            resultados.append(AnalisisSensibilidad(
                escenario=escenarios[i],
                variacion_flujos=variacion,
                van=van,
                tir=tir,
                es_viable=van > 0
            ))

        return resultados

    @staticmethod
    def calcular_tasa_descuento_wacc(
        costo_deuda: Decimal,
        costo_capital: Decimal,
        proporcion_deuda: Decimal,
        tasa_impuestos: Decimal
    ) -> Decimal:
        """
        Calcula el WACC (Costo Promedio Ponderado del Capital).

        WACC = (E/V)*Re + (D/V)*Rd*(1-Tc)
        """
        proporcion_capital = 1 - proporcion_deuda

        wacc = (
            (proporcion_capital * costo_capital) +
            (proporcion_deuda * costo_deuda * (1 - tasa_impuestos))
        )

        return wacc.quantize(
            FinancialEngine.PRECISION_TASA,
            rounding=ROUND_HALF_UP
        )

    @classmethod
    def analisis_sensibilidad_variable(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        variable: str,
        variaciones: List[float] = [-0.20, -0.10, 0, 0.10, 0.20]
    ) -> List[Dict]:
        """
        Analisis de sensibilidad sobre una variable especifica.

        Args:
            variable: "ingresos", "costos", "tasa_descuento"
            variaciones: Lista de variaciones porcentuales

        Returns:
            Lista de resultados por variacion
        """
        resultados = []

        for var in variaciones:
            if variable == "ingresos":
                flujos = [
                    (ing * Decimal(str(1 + var))) - cos
                    for ing, cos in zip(flujos_ingresos, flujos_costos)
                ]
                tasa = tasa_descuento
            elif variable == "costos":
                flujos = [
                    ing - (cos * Decimal(str(1 + var)))
                    for ing, cos in zip(flujos_ingresos, flujos_costos)
                ]
                tasa = tasa_descuento
            elif variable == "tasa_descuento":
                flujos = [ing - cos for ing, cos in zip(flujos_ingresos, flujos_costos)]
                tasa = tasa_descuento * Decimal(str(1 + var))
            else:
                continue

            van = cls.calcular_van(inversion_inicial, flujos, tasa)
            tir = cls.calcular_tir(inversion_inicial, flujos)

            # Determinar escenario
            if var < 0:
                escenario = "Pesimista"
            elif var > 0:
                escenario = "Optimista"
            else:
                escenario = "Base"

            # Estado de viabilidad
            if van > 0:
                if tir and tir > tasa_descuento:
                    estado = "Viable"
                else:
                    estado = "Riesgo Moderado"
            else:
                estado = "No Viable" if van < -inversion_inicial * Decimal("0.1") else "Riesgo Alto"

            resultados.append({
                "escenario": escenario,
                "variacion": var,
                "van": float(van),
                "tir": float(tir) if tir else None,
                "estado_viabilidad": estado
            })

        return resultados

    @classmethod
    def matriz_sensibilidad_cruzada(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        variaciones: List[float] = [-0.10, 0, 0.10]
    ) -> Dict:
        """
        Genera matriz cruzada de sensibilidad (ingresos vs tasa).

        Returns:
            Matriz con VAN para cada combinacion
        """
        matriz = []
        etiquetas_filas = []
        etiquetas_cols = []

        for var_tasa in variaciones:
            tasa_mod = tasa_descuento * Decimal(str(1 + var_tasa))
            etiquetas_cols.append(f"{float(tasa_mod)*100:.1f}%")
            fila = []

            for var_ing in variaciones:
                flujos = [
                    (ing * Decimal(str(1 + var_ing))) - cos
                    for ing, cos in zip(flujos_ingresos, flujos_costos)
                ]
                van = cls.calcular_van(inversion_inicial, flujos, tasa_mod)
                fila.append({
                    "van": float(van),
                    "viable": van > 0,
                    "var_ingresos": var_ing,
                    "var_tasa": var_tasa
                })

            matriz.append(fila)

        for var in variaciones:
            if var < 0:
                etiquetas_filas.append(f"{var*100:.0f}% Ingresos")
            elif var > 0:
                etiquetas_filas.append(f"+{var*100:.0f}% Ingresos")
            else:
                etiquetas_filas.append("Base")

        return {
            "matriz": matriz,
            "etiquetas_filas": etiquetas_filas,
            "etiquetas_columnas": etiquetas_cols,
            "variables": {
                "filas": "ingresos",
                "columnas": "tasa_descuento"
            }
        }

    @classmethod
    def calcular_punto_equilibrio(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        variable: str
    ) -> Dict:
        """
        Calcula el punto de equilibrio (VAN = 0) para una variable.
        """
        from scipy import optimize

        def van_con_variacion(var):
            var = float(var)
            if variable == "ingresos":
                flujos = [
                    float((ing * Decimal(str(1 + var))) - cos)
                    for ing, cos in zip(flujos_ingresos, flujos_costos)
                ]
            elif variable == "costos":
                flujos = [
                    float(ing - (cos * Decimal(str(1 + var))))
                    for ing, cos in zip(flujos_ingresos, flujos_costos)
                ]
            else:
                return 0

            cashflows = [-float(inversion_inicial)] + flujos
            return npf.npv(float(tasa_descuento), cashflows)

        try:
            resultado = optimize.brentq(van_con_variacion, -0.99, 5.0)
            return {
                "variable": variable,
                "variacion_equilibrio": round(resultado, 4),
                "margen_seguridad": abs(round(resultado, 4)),
                "interpretacion": f"El proyecto soporta {abs(resultado)*100:.1f}% de variacion en {variable}"
            }
        except Exception:
            return {
                "variable": variable,
                "variacion_equilibrio": None,
                "margen_seguridad": None,
                "interpretacion": "No se encontro punto de equilibrio en el rango analizado"
            }

    @classmethod
    def simulacion_montecarlo(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        n_simulaciones: int = 1000,
        volatilidad_ingresos: float = 0.15,
        volatilidad_costos: float = 0.10
    ) -> Dict:
        """
        Simulacion Monte Carlo para distribucion de VAN.

        Returns:
            Estadisticas de la distribucion
        """
        np.random.seed(42)
        vanes = []

        for _ in range(n_simulaciones):
            factor_ing = np.random.normal(1, volatilidad_ingresos)
            factor_cos = np.random.normal(1, volatilidad_costos)

            flujos = [
                float(ing) * max(0.1, factor_ing) - float(cos) * max(0.1, factor_cos)
                for ing, cos in zip(flujos_ingresos, flujos_costos)
            ]

            cashflows = [-float(inversion_inicial)] + flujos
            van = npf.npv(float(tasa_descuento), cashflows)
            vanes.append(van)

        vanes_arr = np.array(vanes)

        # Histograma
        hist, bins = np.histogram(vanes_arr, bins=20)

        return {
            "n_simulaciones": n_simulaciones,
            "van_promedio": round(float(np.mean(vanes_arr)), 2),
            "van_mediana": round(float(np.median(vanes_arr)), 2),
            "van_desviacion": round(float(np.std(vanes_arr)), 2),
            "van_minimo": round(float(np.min(vanes_arr)), 2),
            "van_maximo": round(float(np.max(vanes_arr)), 2),
            "percentil_5": round(float(np.percentile(vanes_arr, 5)), 2),
            "percentil_95": round(float(np.percentile(vanes_arr, 95)), 2),
            "probabilidad_perdida": round(float(np.mean(vanes_arr < 0)), 4),
            "valor_en_riesgo_95": round(float(np.percentile(vanes_arr, 5)), 2),
            "histograma": {
                "rangos": [round(float(b), 2) for b in bins],
                "frecuencias": [int(h) for h in hist]
            }
        }

    @classmethod
    def grafico_tornado_data(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        variacion: float = 0.10
    ) -> List[Dict]:
        """
        Genera datos para grafico tornado (impacto de variables).

        Returns:
            Lista ordenada por impacto
        """
        variables = ["ingresos", "costos", "tasa_descuento"]
        impactos = []

        # VAN base
        flujos_base = [ing - cos for ing, cos in zip(flujos_ingresos, flujos_costos)]
        van_base = cls.calcular_van(inversion_inicial, flujos_base, tasa_descuento)

        for var in variables:
            # VAN con +variacion
            sens_pos = cls.analisis_sensibilidad_variable(
                inversion_inicial, flujos_ingresos, flujos_costos,
                tasa_descuento, var, [variacion]
            )[0]

            # VAN con -variacion
            sens_neg = cls.analisis_sensibilidad_variable(
                inversion_inicial, flujos_ingresos, flujos_costos,
                tasa_descuento, var, [-variacion]
            )[0]

            impacto = abs(sens_pos["van"] - sens_neg["van"])

            impactos.append({
                "variable": var,
                "van_positivo": sens_pos["van"],
                "van_negativo": sens_neg["van"],
                "van_base": float(van_base),
                "impacto_total": impacto,
                "variacion_aplicada": variacion
            })

        # Ordenar por impacto descendente
        impactos.sort(key=lambda x: x["impacto_total"], reverse=True)
        return impactos

    @classmethod
    def evaluacion_completa(
        cls,
        inversion_inicial: Decimal,
        flujos_ingresos: List[Decimal],
        flujos_costos: List[Decimal],
        tasa_descuento: Decimal,
        incluir_montecarlo: bool = True
    ) -> Dict:
        """
        Evaluacion financiera completa con todos los analisis.
        """
        # Flujos netos
        flujos_netos = [ing - cos for ing, cos in zip(flujos_ingresos, flujos_costos)]

        # Evaluacion basica
        eval_basica = cls.evaluar_proyecto(
            inversion_inicial, flujos_netos, tasa_descuento
        )

        # Sensibilidad por variable
        sens_ingresos = cls.analisis_sensibilidad_variable(
            inversion_inicial, flujos_ingresos, flujos_costos,
            tasa_descuento, "ingresos"
        )
        sens_costos = cls.analisis_sensibilidad_variable(
            inversion_inicial, flujos_ingresos, flujos_costos,
            tasa_descuento, "costos"
        )

        # Puntos de equilibrio
        eq_ingresos = cls.calcular_punto_equilibrio(
            inversion_inicial, flujos_ingresos, flujos_costos,
            tasa_descuento, "ingresos"
        )
        eq_costos = cls.calcular_punto_equilibrio(
            inversion_inicial, flujos_ingresos, flujos_costos,
            tasa_descuento, "costos"
        )

        # Matriz cruzada
        matriz = cls.matriz_sensibilidad_cruzada(
            inversion_inicial, flujos_ingresos, flujos_costos, tasa_descuento
        )

        # Tornado
        tornado = cls.grafico_tornado_data(
            inversion_inicial, flujos_ingresos, flujos_costos, tasa_descuento
        )

        resultado = {
            "evaluacion": {
                "inversion_inicial": float(inversion_inicial),
                "tasa_descuento": float(tasa_descuento),
                "van": float(eval_basica.van),
                "tir": float(eval_basica.tir) if eval_basica.tir else None,
                "roi": float(eval_basica.roi),
                "payback_period": float(eval_basica.payback_period) if eval_basica.payback_period else None,
                "indice_rentabilidad": float(eval_basica.indice_rentabilidad),
                "flujos_descontados": [float(f) for f in eval_basica.flujos_descontados],
                "es_viable": eval_basica.es_viable,
                "mensaje": eval_basica.mensaje
            },
            "sensibilidad": {
                "ingresos": sens_ingresos,
                "costos": sens_costos
            },
            "punto_equilibrio": {
                "ingresos": eq_ingresos,
                "costos": eq_costos
            },
            "matriz_cruzada": matriz,
            "tornado": tornado
        }

        # Monte Carlo opcional (costoso computacionalmente)
        if incluir_montecarlo:
            resultado["montecarlo"] = cls.simulacion_montecarlo(
                inversion_inicial, flujos_ingresos, flujos_costos,
                tasa_descuento, n_simulaciones=500
            )

        return resultado
