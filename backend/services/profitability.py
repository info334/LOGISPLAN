"""
LogisPLAN - Servicio de Rentabilidad
Extraído de app.py calcular_rentabilidad_vehiculo() y calcular_pnl_vehiculo()
"""
import sys
from pathlib import Path

# Añadir raíz del proyecto al path para importar database.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from database import (
    get_movimientos,
    get_facturacion,
    get_amortizaciones,
)


VEHICULOS_OPERATIVOS = ["MTY", "LVX", "MJC", "MLB"]


def calcular_rentabilidad_vehiculo(vehiculo_id: str = None):
    """
    Calcula la rentabilidad de un vehículo o total.
    Fórmula: margen = (facturacion - gastos_totales) / facturacion * 100
    Donde gastos_totales = gastos_directos + (gastos_comunes / num_vehiculos) + amortizacion

    Retorna: (facturacion, resultado_neto, margen_pct, periodo)
    """
    num_vehiculos = len(VEHICULOS_OPERATIVOS)

    df_fact = get_facturacion(vehiculo_id=vehiculo_id) if vehiculo_id else get_facturacion()
    facturacion_total = df_fact['importe'].sum() if len(df_fact) > 0 else 0

    if vehiculo_id:
        movimientos_veh = get_movimientos(vehiculo_id=vehiculo_id)
        gastos_directos = abs(movimientos_veh[movimientos_veh['importe'] < 0]['importe'].sum()) if len(movimientos_veh) > 0 else 0

        movimientos_comun = get_movimientos(vehiculo_id='COMUN')
        gastos_comunes = abs(movimientos_comun[movimientos_comun['importe'] < 0]['importe'].sum()) if len(movimientos_comun) > 0 else 0
        gastos_comunes_prorrateados = gastos_comunes / num_vehiculos

        df_amort = get_amortizaciones()
        if len(df_amort) > 0:
            amort_veh = df_amort[df_amort['vehiculo_id'] == vehiculo_id]['amortizacion_mensual'].sum()
            amort_comun = df_amort[df_amort['vehiculo_id'] == 'COMUN']['amortizacion_mensual'].sum()
            if len(movimientos_veh) > 0:
                meses_datos = pd.to_datetime(movimientos_veh['fecha']).dt.to_period('M').nunique()
            else:
                meses_datos = 1
            amortizacion = (amort_veh + amort_comun / num_vehiculos) * meses_datos
        else:
            amortizacion = 0

        gastos_totales = gastos_directos + gastos_comunes_prorrateados + amortizacion
    else:
        movimientos_todos = get_movimientos()
        gastos_totales_mov = abs(movimientos_todos[movimientos_todos['importe'] < 0]['importe'].sum()) if len(movimientos_todos) > 0 else 0

        df_amort = get_amortizaciones()
        if len(df_amort) > 0 and len(movimientos_todos) > 0:
            amort_mensual_total = df_amort['amortizacion_mensual'].sum()
            meses_datos = pd.to_datetime(movimientos_todos['fecha']).dt.to_period('M').nunique()
            amortizacion = amort_mensual_total * meses_datos
        else:
            amortizacion = 0

        gastos_totales = gastos_totales_mov + amortizacion

    resultado_neto = facturacion_total - gastos_totales
    margen_pct = (resultado_neto / facturacion_total) * 100 if facturacion_total > 0 else 0

    periodo = "Sin datos"
    df_pnl = calcular_pnl_vehiculo(vehiculo_id)
    if len(df_pnl) > 0:
        meses = df_pnl['mes'].sort_values()
        mes_inicio = meses.iloc[0] if len(meses) > 0 else ""
        mes_fin = meses.iloc[-1] if len(meses) > 0 else ""
        if mes_inicio and mes_fin:
            meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            try:
                ini_parts = mes_inicio.split('-')
                fin_parts = mes_fin.split('-')
                ini_str = f"{meses_nombres[int(ini_parts[1])-1]} {ini_parts[0]}"
                fin_str = f"{meses_nombres[int(fin_parts[1])-1]} {fin_parts[0]}"
                periodo = f"{ini_str} - {fin_str}" if mes_inicio != mes_fin else ini_str
            except (IndexError, ValueError):
                periodo = f"{mes_inicio} - {mes_fin}"

    return facturacion_total, resultado_neto, margen_pct, periodo


def calcular_pnl_vehiculo(vehiculo_id: str = None) -> pd.DataFrame:
    """
    Calcula P&L mensual para un vehículo o todos.
    Retorna DataFrame con columnas: mes, ingresos, gastos, neto
    """
    movimientos = get_movimientos(vehiculo_id=vehiculo_id) if vehiculo_id else get_movimientos()

    if len(movimientos) == 0:
        return pd.DataFrame(columns=['mes', 'ingresos', 'gastos', 'neto'])

    movimientos['mes'] = pd.to_datetime(movimientos['fecha']).dt.strftime('%Y-%m')

    resumen = movimientos.groupby('mes').agg(
        ingresos=('importe', lambda x: x[x > 0].sum()),
        gastos=('importe', lambda x: x[x < 0].sum())
    ).reset_index()

    resumen['neto'] = resumen['ingresos'] + resumen['gastos']
    resumen = resumen.sort_values('mes', ascending=False)

    return resumen
