"""
Motor de Calculo de Indicadores Sectoriales.
Calcula metricas especificas por sector de proyecto.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from dataclasses import dataclass


def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Convierte valor a Decimal de forma segura."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except:
        return default


def safe_divide(numerator: Decimal, denominator: Decimal, default: Decimal = Decimal("0")) -> Decimal:
    """Division segura que evita division por cero."""
    if denominator == 0:
        return default
    return numerator / denominator


class SectorIndicatorsEngine:
    """
    Motor de calculo de indicadores por sector.
    Cada sector tiene sus propios indicadores y formulas.
    """

    @classmethod
    def calculate_indicators(cls, sector: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula indicadores segun el sector.

        Args:
            sector: Nombre del sector (tecnologia, inmobiliario, etc.)
            input_data: Datos de entrada especificos del sector

        Returns:
            Dict con indicadores calculados y sus descripciones
        """
        sector_lower = sector.lower()

        calculators = {
            "tecnologia": cls._calculate_tecnologia,
            "inmobiliario": cls._calculate_inmobiliario,
            "energia": cls._calculate_energia,
            "fintech": cls._calculate_fintech,
            "industrial": cls._calculate_industrial,
            "comercio": cls._calculate_comercio,
            "agrotech": cls._calculate_agrotech,
            "infraestructura": cls._calculate_infraestructura,
        }

        calculator = calculators.get(sector_lower)
        if not calculator:
            return {"error": f"Sector '{sector}' no tiene calculadora de indicadores"}

        return calculator(input_data)

    @classmethod
    def _calculate_tecnologia(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Tecnologia/SaaS."""
        mrr = safe_decimal(data.get("mrr"))
        cac = safe_decimal(data.get("cac"))
        ltv = safe_decimal(data.get("ltv"))
        churn_mensual = safe_decimal(data.get("churn_mensual")) / 100  # Convertir porcentaje
        gastos_mensuales = safe_decimal(data.get("gastos_mensuales"))
        capital_disponible = safe_decimal(data.get("capital_disponible"))
        usuarios_actuales = safe_decimal(data.get("usuarios_actuales"))
        usuarios_proyectados = safe_decimal(data.get("usuarios_proyectados"))
        nps_score = data.get("nps_score")
        arpu_input = safe_decimal(data.get("arpu"))

        # Calculos
        arr = mrr * 12
        ltv_cac_ratio = safe_divide(ltv, cac)
        burn_rate = gastos_mensuales - mrr if gastos_mensuales > mrr else Decimal("0")
        runway_meses = safe_divide(capital_disponible, burn_rate) if burn_rate > 0 else Decimal("999")

        # ARPU calculado si no se proporciona
        arpu = arpu_input if arpu_input > 0 else safe_divide(mrr, usuarios_actuales)

        # Crecimiento de usuarios proyectado
        crecimiento_usuarios = Decimal("0")
        if usuarios_actuales > 0 and usuarios_proyectados > 0:
            crecimiento_usuarios = ((usuarios_proyectados - usuarios_actuales) / usuarios_actuales) * 100

        # Churn anual
        churn_anual = (1 - (1 - churn_mensual) ** 12) * 100

        return {
            "ltv_cac_ratio": {
                "value": float(ltv_cac_ratio.quantize(Decimal("0.01"))),
                "label": "Ratio LTV/CAC",
                "description": "Valor de vida del cliente / Costo de adquisicion",
                "benchmark": "Ideal > 3.0",
                "status": "good" if ltv_cac_ratio >= 3 else "warning" if ltv_cac_ratio >= 1 else "bad"
            },
            "burn_rate": {
                "value": float(burn_rate.quantize(Decimal("0.01"))),
                "label": "Burn Rate Mensual",
                "description": "Tasa de quema de capital por mes",
                "format": "currency"
            },
            "runway_meses": {
                "value": float(min(runway_meses, Decimal("999")).quantize(Decimal("0.1"))),
                "label": "Runway",
                "description": "Meses de operacion con capital actual",
                "unit": "meses",
                "status": "good" if runway_meses >= 18 else "warning" if runway_meses >= 6 else "bad"
            },
            "mrr": {
                "value": float(mrr.quantize(Decimal("0.01"))),
                "label": "MRR",
                "description": "Ingresos Recurrentes Mensuales",
                "format": "currency"
            },
            "arr": {
                "value": float(arr.quantize(Decimal("0.01"))),
                "label": "ARR",
                "description": "Ingresos Recurrentes Anuales",
                "format": "currency"
            },
            "churn_rate": {
                "value": float((churn_mensual * 100).quantize(Decimal("0.01"))),
                "label": "Churn Rate Mensual",
                "description": "Tasa de cancelacion mensual",
                "unit": "%",
                "status": "good" if churn_mensual <= Decimal("0.02") else "warning" if churn_mensual <= Decimal("0.05") else "bad"
            },
            "churn_anual": {
                "value": float(churn_anual.quantize(Decimal("0.01"))),
                "label": "Churn Rate Anual",
                "description": "Tasa de cancelacion anualizada",
                "unit": "%"
            },
            "arpu": {
                "value": float(arpu.quantize(Decimal("0.01"))),
                "label": "ARPU",
                "description": "Ingreso promedio por usuario",
                "format": "currency"
            },
            "crecimiento_usuarios": {
                "value": float(crecimiento_usuarios.quantize(Decimal("0.01"))),
                "label": "Crecimiento Usuarios Proyectado",
                "description": "Crecimiento esperado en 12 meses",
                "unit": "%"
            },
            "nps": {
                "value": nps_score if nps_score is not None else None,
                "label": "NPS",
                "description": "Net Promoter Score",
                "status": "good" if nps_score and nps_score >= 50 else "warning" if nps_score and nps_score >= 0 else "bad" if nps_score else None
            }
        }

    @classmethod
    def _calculate_inmobiliario(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Inmobiliario."""
        metros_cuadrados = safe_decimal(data.get("metros_cuadrados"))
        precio_m2_venta = safe_decimal(data.get("precio_m2_venta"))
        precio_m2_renta = safe_decimal(data.get("precio_m2_renta"))
        ocupacion_actual = safe_decimal(data.get("ocupacion_actual")) / 100
        ingresos_renta_mensual = safe_decimal(data.get("ingresos_renta_mensual"))
        gastos_operativos = safe_decimal(data.get("gastos_operativos"))
        valor_propiedad = safe_decimal(data.get("valor_propiedad"))
        deuda_hipotecaria = safe_decimal(data.get("deuda_hipotecaria"))

        # NOI (Net Operating Income)
        noi_mensual = ingresos_renta_mensual - gastos_operativos
        noi_anual = noi_mensual * 12

        # Cap Rate
        cap_rate = safe_divide(noi_anual, valor_propiedad) * 100

        # Yield Bruto (ingresos / valor propiedad)
        yield_bruto = safe_divide(ingresos_renta_mensual * 12, valor_propiedad) * 100

        # Yield Neto (NOI / valor propiedad)
        yield_neto = safe_divide(noi_anual, valor_propiedad) * 100

        # LTV
        ltv = safe_divide(deuda_hipotecaria, valor_propiedad) * 100

        # Precio por M2
        precio_m2_calculado = safe_divide(valor_propiedad, metros_cuadrados)

        # Renta por M2
        renta_m2 = safe_divide(ingresos_renta_mensual, metros_cuadrados)

        return {
            "cap_rate": {
                "value": float(cap_rate.quantize(Decimal("0.01"))),
                "label": "Cap Rate",
                "description": "Tasa de Capitalizacion (NOI / Valor)",
                "unit": "%",
                "benchmark": "Ideal 5-10%",
                "status": "good" if cap_rate >= 5 else "warning" if cap_rate >= 3 else "bad"
            },
            "noi": {
                "value": float(noi_anual.quantize(Decimal("0.01"))),
                "label": "NOI Anual",
                "description": "Ingreso Operativo Neto",
                "format": "currency"
            },
            "yield_bruto": {
                "value": float(yield_bruto.quantize(Decimal("0.01"))),
                "label": "Yield Bruto",
                "description": "Rendimiento bruto anual",
                "unit": "%"
            },
            "yield_neto": {
                "value": float(yield_neto.quantize(Decimal("0.01"))),
                "label": "Yield Neto",
                "description": "Rendimiento neto anual",
                "unit": "%"
            },
            "loan_to_value": {
                "value": float(ltv.quantize(Decimal("0.01"))),
                "label": "Loan to Value (LTV)",
                "description": "Relacion deuda / valor propiedad",
                "unit": "%",
                "status": "good" if ltv <= 70 else "warning" if ltv <= 80 else "bad"
            },
            "precio_m2": {
                "value": float(precio_m2_calculado.quantize(Decimal("0.01"))),
                "label": "Precio por M2",
                "description": "Valor por metro cuadrado",
                "format": "currency"
            },
            "renta_m2": {
                "value": float(renta_m2.quantize(Decimal("0.01"))),
                "label": "Renta por M2",
                "description": "Renta mensual por metro cuadrado",
                "format": "currency"
            },
            "ocupacion": {
                "value": float((ocupacion_actual * 100).quantize(Decimal("0.01"))),
                "label": "Ocupacion",
                "description": "Porcentaje de ocupacion actual",
                "unit": "%",
                "status": "good" if ocupacion_actual >= Decimal("0.9") else "warning" if ocupacion_actual >= Decimal("0.7") else "bad"
            }
        }

    @classmethod
    def _calculate_energia(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Energia."""
        capacidad_mw = safe_decimal(data.get("capacidad_mw"))
        factor_planta = safe_decimal(data.get("factor_planta")) / 100
        precio_kwh = safe_decimal(data.get("precio_kwh"))
        costo_instalacion_kw = safe_decimal(data.get("costo_instalacion_kw"))
        costos_operativos_anuales = safe_decimal(data.get("costos_operativos_anuales"))
        vida_util_anos = safe_decimal(data.get("vida_util_anos", 25))

        # Produccion anual (MW * 1000 * horas/ano * factor planta)
        horas_ano = Decimal("8760")  # 24 * 365
        produccion_anual_mwh = capacidad_mw * horas_ano * factor_planta
        produccion_anual_kwh = produccion_anual_mwh * 1000

        # Ingresos anuales
        ingresos_anuales = produccion_anual_kwh * precio_kwh

        # Inversion total
        inversion_total = capacidad_mw * 1000 * costo_instalacion_kw  # MW to kW

        # LCOE (Levelized Cost of Energy)
        produccion_total_vida = produccion_anual_kwh * vida_util_anos
        costos_totales_vida = inversion_total + (costos_operativos_anuales * vida_util_anos)
        lcoe = safe_divide(costos_totales_vida, produccion_total_vida)

        # ROI simplificado
        utilidad_anual = ingresos_anuales - costos_operativos_anuales
        roi_anual = safe_divide(utilidad_anual, inversion_total) * 100

        # Payback
        payback_anos = safe_divide(inversion_total, utilidad_anual)

        return {
            "lcoe": {
                "value": float(lcoe.quantize(Decimal("0.0001"))),
                "label": "LCOE",
                "description": "Costo Nivelado de Energia ($/kWh)",
                "format": "currency_small",
                "status": "good" if lcoe < precio_kwh else "bad"
            },
            "factor_capacidad": {
                "value": float((factor_planta * 100).quantize(Decimal("0.01"))),
                "label": "Factor de Capacidad",
                "description": "Porcentaje de utilizacion de capacidad",
                "unit": "%"
            },
            "produccion_anual": {
                "value": float(produccion_anual_mwh.quantize(Decimal("0.01"))),
                "label": "Produccion Anual",
                "description": "Energia producida al ano",
                "unit": "MWh"
            },
            "ingresos_anuales": {
                "value": float(ingresos_anuales.quantize(Decimal("0.01"))),
                "label": "Ingresos Anuales",
                "description": "Ingresos por venta de energia",
                "format": "currency"
            },
            "costo_instalacion_kw": {
                "value": float(costo_instalacion_kw.quantize(Decimal("0.01"))),
                "label": "Costo por kW",
                "description": "Costo de instalacion por kW",
                "format": "currency"
            },
            "roi_energia": {
                "value": float(roi_anual.quantize(Decimal("0.01"))),
                "label": "ROI Anual",
                "description": "Retorno anual sobre inversion",
                "unit": "%"
            },
            "payback_anos": {
                "value": float(payback_anos.quantize(Decimal("0.1"))),
                "label": "Payback",
                "description": "Periodo de recuperacion",
                "unit": "anos"
            },
            "vida_util_anos": {
                "value": int(vida_util_anos),
                "label": "Vida Util",
                "description": "Vida util del proyecto",
                "unit": "anos"
            }
        }

    @classmethod
    def _calculate_fintech(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Fintech."""
        volumen_transacciones = safe_decimal(data.get("volumen_transacciones_mensual"))
        comision_promedio = safe_decimal(data.get("comision_promedio")) / 100
        usuarios_activos = safe_decimal(data.get("usuarios_activos"))
        tasa_default = safe_decimal(data.get("tasa_default")) / 100
        costo_fondeo = safe_decimal(data.get("costo_fondeo", 0)) / 100
        cartera_creditos = safe_decimal(data.get("cartera_creditos", 0))
        cac = safe_decimal(data.get("cac"))
        ltv = safe_decimal(data.get("ltv"))

        # Take rate (comisiones sobre volumen)
        take_rate = comision_promedio * 100

        # Ingresos por comisiones
        ingresos_comisiones = volumen_transacciones * comision_promedio

        # LTV/CAC
        ltv_cac_ratio = safe_divide(ltv, cac)

        # Spread (si aplica a creditos)
        spread = Decimal("0")
        if cartera_creditos > 0 and costo_fondeo > 0:
            # Asumiendo tasa de credito promedio del mercado
            tasa_credito = Decimal("0.25")  # 25% promedio
            spread = (tasa_credito - costo_fondeo) * 100

        # Perdida esperada
        perdida_esperada = cartera_creditos * tasa_default if cartera_creditos > 0 else Decimal("0")

        # Cartera neta
        cartera_neta = cartera_creditos - perdida_esperada

        return {
            "take_rate": {
                "value": float(take_rate.quantize(Decimal("0.01"))),
                "label": "Take Rate",
                "description": "Comision sobre transacciones",
                "unit": "%"
            },
            "volumen_procesado": {
                "value": float(volumen_transacciones.quantize(Decimal("0.01"))),
                "label": "Volumen Mensual",
                "description": "Volumen de transacciones procesadas",
                "format": "currency"
            },
            "ingresos_comisiones": {
                "value": float(ingresos_comisiones.quantize(Decimal("0.01"))),
                "label": "Ingresos Comisiones",
                "description": "Ingresos mensuales por comisiones",
                "format": "currency"
            },
            "ltv_cac_ratio": {
                "value": float(ltv_cac_ratio.quantize(Decimal("0.01"))),
                "label": "LTV/CAC",
                "description": "Valor de vida / Costo adquisicion",
                "status": "good" if ltv_cac_ratio >= 3 else "warning" if ltv_cac_ratio >= 1 else "bad"
            },
            "default_rate": {
                "value": float((tasa_default * 100).quantize(Decimal("0.01"))),
                "label": "Tasa de Default",
                "description": "Porcentaje de incumplimiento",
                "unit": "%",
                "status": "good" if tasa_default <= Decimal("0.05") else "warning" if tasa_default <= Decimal("0.10") else "bad"
            },
            "spread": {
                "value": float(spread.quantize(Decimal("0.01"))),
                "label": "Spread",
                "description": "Margen sobre costo de fondeo",
                "unit": "%"
            },
            "cartera_neta": {
                "value": float(cartera_neta.quantize(Decimal("0.01"))),
                "label": "Cartera Neta",
                "description": "Cartera menos provision",
                "format": "currency"
            }
        }

    @classmethod
    def _calculate_industrial(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Industrial."""
        capacidad_produccion = safe_decimal(data.get("capacidad_produccion"))
        produccion_actual = safe_decimal(data.get("produccion_actual"))
        costo_unitario = safe_decimal(data.get("costo_unitario"))
        precio_venta_unitario = safe_decimal(data.get("precio_venta_unitario"))
        costos_fijos_mensuales = safe_decimal(data.get("costos_fijos_mensuales"))
        inventario_promedio = safe_decimal(data.get("inventario_promedio", 0))

        # Utilizacion de capacidad
        utilizacion = safe_divide(produccion_actual, capacidad_produccion) * 100

        # Margen de contribucion
        margen_contribucion = precio_venta_unitario - costo_unitario
        margen_contribucion_pct = safe_divide(margen_contribucion, precio_venta_unitario) * 100

        # Punto de equilibrio
        punto_equilibrio = safe_divide(costos_fijos_mensuales, margen_contribucion)

        # Ventas mensuales
        ventas_mensuales = produccion_actual * precio_venta_unitario
        costos_variables = produccion_actual * costo_unitario

        # Margen operativo
        utilidad_operativa = ventas_mensuales - costos_variables - costos_fijos_mensuales
        margen_operativo = safe_divide(utilidad_operativa, ventas_mensuales) * 100

        # Rotacion de inventario
        rotacion_inventario = safe_divide(produccion_actual, inventario_promedio) if inventario_promedio > 0 else Decimal("0")

        return {
            "utilizacion_capacidad": {
                "value": float(utilizacion.quantize(Decimal("0.01"))),
                "label": "Utilizacion de Capacidad",
                "description": "Porcentaje de capacidad utilizada",
                "unit": "%",
                "status": "good" if utilizacion >= 80 else "warning" if utilizacion >= 60 else "bad"
            },
            "margen_contribucion": {
                "value": float(margen_contribucion.quantize(Decimal("0.01"))),
                "label": "Margen de Contribucion",
                "description": "Precio - Costo variable unitario",
                "format": "currency"
            },
            "margen_contribucion_pct": {
                "value": float(margen_contribucion_pct.quantize(Decimal("0.01"))),
                "label": "Margen Contribucion %",
                "description": "Margen de contribucion porcentual",
                "unit": "%"
            },
            "punto_equilibrio_unidades": {
                "value": float(punto_equilibrio.quantize(Decimal("0.01"))),
                "label": "Punto de Equilibrio",
                "description": "Unidades para cubrir costos fijos",
                "unit": "unidades"
            },
            "margen_operativo": {
                "value": float(margen_operativo.quantize(Decimal("0.01"))),
                "label": "Margen Operativo",
                "description": "Utilidad operativa / Ventas",
                "unit": "%"
            },
            "costo_unitario": {
                "value": float(costo_unitario.quantize(Decimal("0.01"))),
                "label": "Costo Unitario",
                "description": "Costo variable por unidad",
                "format": "currency"
            },
            "rotacion_inventario": {
                "value": float(rotacion_inventario.quantize(Decimal("0.01"))),
                "label": "Rotacion Inventario",
                "description": "Veces que rota el inventario/mes",
                "unit": "veces"
            }
        }

    @classmethod
    def _calculate_comercio(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Comercio."""
        ventas_mensuales = safe_decimal(data.get("ventas_mensuales"))
        metros_cuadrados = safe_decimal(data.get("metros_cuadrados"))
        ticket_promedio = safe_decimal(data.get("ticket_promedio"))
        visitas_mensuales = safe_decimal(data.get("visitas_mensuales"))
        costo_mercancia = safe_decimal(data.get("costo_mercancia")) / 100
        gastos_operativos = safe_decimal(data.get("gastos_operativos"))
        inventario_promedio = safe_decimal(data.get("inventario_promedio", 0))

        # Ventas por M2
        ventas_m2 = safe_divide(ventas_mensuales, metros_cuadrados)

        # Margen bruto
        costo_ventas = ventas_mensuales * costo_mercancia
        margen_bruto = ventas_mensuales - costo_ventas
        margen_bruto_pct = safe_divide(margen_bruto, ventas_mensuales) * 100

        # Conversion rate
        transacciones = safe_divide(ventas_mensuales, ticket_promedio)
        conversion_rate = safe_divide(transacciones, visitas_mensuales) * 100

        # Punto de equilibrio
        punto_equilibrio = safe_divide(gastos_operativos, (1 - costo_mercancia))

        # Rotacion inventario
        rotacion_inventario = safe_divide(costo_ventas, inventario_promedio) if inventario_promedio > 0 else Decimal("0")

        # Margen neto
        utilidad_neta = margen_bruto - gastos_operativos
        margen_neto = safe_divide(utilidad_neta, ventas_mensuales) * 100

        return {
            "ventas_m2": {
                "value": float(ventas_m2.quantize(Decimal("0.01"))),
                "label": "Ventas por M2",
                "description": "Ventas mensuales por metro cuadrado",
                "format": "currency"
            },
            "margen_bruto": {
                "value": float(margen_bruto_pct.quantize(Decimal("0.01"))),
                "label": "Margen Bruto",
                "description": "Porcentaje de margen bruto",
                "unit": "%"
            },
            "ticket_promedio": {
                "value": float(ticket_promedio.quantize(Decimal("0.01"))),
                "label": "Ticket Promedio",
                "description": "Valor promedio por transaccion",
                "format": "currency"
            },
            "conversion_rate": {
                "value": float(conversion_rate.quantize(Decimal("0.01"))),
                "label": "Tasa de Conversion",
                "description": "Porcentaje de visitas que compran",
                "unit": "%"
            },
            "punto_equilibrio": {
                "value": float(punto_equilibrio.quantize(Decimal("0.01"))),
                "label": "Punto de Equilibrio",
                "description": "Ventas minimas para cubrir gastos",
                "format": "currency"
            },
            "rotacion_inventario": {
                "value": float(rotacion_inventario.quantize(Decimal("0.01"))),
                "label": "Rotacion Inventario",
                "description": "Veces que rota el inventario/mes",
                "unit": "veces"
            },
            "margen_neto": {
                "value": float(margen_neto.quantize(Decimal("0.01"))),
                "label": "Margen Neto",
                "description": "Utilidad neta / Ventas",
                "unit": "%"
            }
        }

    @classmethod
    def _calculate_agrotech(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Agrotech."""
        hectareas = safe_decimal(data.get("hectareas"))
        rendimiento_ton_ha = safe_decimal(data.get("rendimiento_ton_ha"))
        precio_ton = safe_decimal(data.get("precio_ton"))
        costo_produccion_ha = safe_decimal(data.get("costo_produccion_ha"))
        ciclos_por_ano = safe_decimal(data.get("ciclos_por_ano", 1))
        perdida_estimada = safe_decimal(data.get("perdida_estimada", 0)) / 100

        # Produccion total
        produccion_bruta = hectareas * rendimiento_ton_ha * ciclos_por_ano
        produccion_neta = produccion_bruta * (1 - perdida_estimada)

        # Ingresos
        ingresos_anuales = produccion_neta * precio_ton
        ingreso_por_hectarea = safe_divide(ingresos_anuales, hectareas)

        # Costos
        costos_totales = hectareas * costo_produccion_ha * ciclos_por_ano
        costo_produccion_ton = safe_divide(costos_totales, produccion_neta)

        # Margen
        margen_bruto = ingresos_anuales - costos_totales
        margen_bruto_pct = safe_divide(margen_bruto, ingresos_anuales) * 100

        # Punto de equilibrio
        punto_equilibrio_ha = safe_divide(costos_totales, safe_divide(ingresos_anuales, hectareas))

        return {
            "rendimiento_hectarea": {
                "value": float(rendimiento_ton_ha.quantize(Decimal("0.01"))),
                "label": "Rendimiento por Ha",
                "description": "Toneladas por hectarea",
                "unit": "ton/ha"
            },
            "produccion_anual": {
                "value": float(produccion_neta.quantize(Decimal("0.01"))),
                "label": "Produccion Anual",
                "description": "Toneladas netas producidas",
                "unit": "ton"
            },
            "ingreso_por_hectarea": {
                "value": float(ingreso_por_hectarea.quantize(Decimal("0.01"))),
                "label": "Ingreso por Ha",
                "description": "Ingresos anuales por hectarea",
                "format": "currency"
            },
            "costo_produccion_ton": {
                "value": float(costo_produccion_ton.quantize(Decimal("0.01"))),
                "label": "Costo por Tonelada",
                "description": "Costo de produccion por tonelada",
                "format": "currency",
                "status": "good" if costo_produccion_ton < precio_ton else "bad"
            },
            "margen_bruto": {
                "value": float(margen_bruto_pct.quantize(Decimal("0.01"))),
                "label": "Margen Bruto",
                "description": "Porcentaje de margen bruto",
                "unit": "%"
            },
            "punto_equilibrio": {
                "value": float(punto_equilibrio_ha.quantize(Decimal("0.01"))),
                "label": "Punto Equilibrio",
                "description": "Hectareas minimas rentables",
                "unit": "ha"
            }
        }

    @classmethod
    def _calculate_infraestructura(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Indicadores para sector Infraestructura."""
        usuarios_diarios = safe_decimal(data.get("usuarios_diarios"))
        tarifa_promedio = safe_decimal(data.get("tarifa_promedio"))
        costos_operativos_mensuales = safe_decimal(data.get("costos_operativos_mensuales"))
        inversion_total = safe_decimal(data.get("inversion_total"))
        vida_util_anos = safe_decimal(data.get("vida_util_anos", 30))
        crecimiento_trafico = safe_decimal(data.get("crecimiento_trafico_anual", 0)) / 100

        # Ingresos
        dias_mes = Decimal("30")
        dias_ano = Decimal("365")
        ingresos_mensuales = usuarios_diarios * tarifa_promedio * dias_mes
        ingresos_anuales = usuarios_diarios * tarifa_promedio * dias_ano

        # Flujo operativo
        flujo_operativo_mensual = ingresos_mensuales - costos_operativos_mensuales
        flujo_operativo_anual = flujo_operativo_mensual * 12

        # Payback simple
        payback_anos = safe_divide(inversion_total, flujo_operativo_anual)

        # ROI anual
        roi_anual = safe_divide(flujo_operativo_anual, inversion_total) * 100

        # Beneficio/Costo simplificado
        beneficios_vida = flujo_operativo_anual * vida_util_anos
        beneficio_costo = safe_divide(beneficios_vida, inversion_total)

        # Trafico proyectado a 5 anos
        trafico_5_anos = usuarios_diarios * ((1 + crecimiento_trafico) ** 5)

        return {
            "ingresos_anuales": {
                "value": float(ingresos_anuales.quantize(Decimal("0.01"))),
                "label": "Ingresos Anuales",
                "description": "Ingresos totales por ano",
                "format": "currency"
            },
            "flujo_operativo_anual": {
                "value": float(flujo_operativo_anual.quantize(Decimal("0.01"))),
                "label": "Flujo Operativo Anual",
                "description": "Ingresos - Costos operativos",
                "format": "currency"
            },
            "payback_infraestructura": {
                "value": float(payback_anos.quantize(Decimal("0.1"))),
                "label": "Payback",
                "description": "Periodo de recuperacion",
                "unit": "anos"
            },
            "roi_anual": {
                "value": float(roi_anual.quantize(Decimal("0.01"))),
                "label": "ROI Anual",
                "description": "Retorno anual sobre inversion",
                "unit": "%"
            },
            "beneficio_costo_ratio": {
                "value": float(beneficio_costo.quantize(Decimal("0.01"))),
                "label": "Ratio B/C",
                "description": "Beneficios / Costos (vida util)",
                "status": "good" if beneficio_costo >= 1.5 else "warning" if beneficio_costo >= 1 else "bad"
            },
            "tarifa_promedio": {
                "value": float(tarifa_promedio.quantize(Decimal("0.01"))),
                "label": "Tarifa Promedio",
                "description": "Tarifa por usuario/vehiculo",
                "format": "currency"
            },
            "trafico_proyectado": {
                "value": float(trafico_5_anos.quantize(Decimal("0"))),
                "label": "Trafico Proyectado (5 anos)",
                "description": "Usuarios diarios en 5 anos",
                "unit": "usuarios/dia"
            },
            "vida_util_anos": {
                "value": int(vida_util_anos),
                "label": "Vida Util",
                "description": "Vida util del proyecto",
                "unit": "anos"
            }
        }
