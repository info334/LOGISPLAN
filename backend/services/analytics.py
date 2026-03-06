"""
LogisPLAN - Servicio de Analytics
Cálculos de KPIs, tendencias y actividad reciente para el dashboard.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from database import (
    get_movimientos,
    get_facturacion,
    get_vehiculos_operativos,
    get_importaciones_por_mes,
)
from backend.services.profitability import (
    calcular_rentabilidad_vehiculo,
    VEHICULOS_OPERATIVOS,
)


def get_dashboard_kpis():
    """Calcula los 4 KPIs principales del dashboard."""
    vehiculos = get_vehiculos_operativos()
    vehiculos_activos = len(vehiculos)

    now = datetime.now()
    mes_actual = now.strftime('%Y-%m')
    mes_anterior = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')

    # Gastos del mes actual
    movimientos = get_movimientos()
    if len(movimientos) > 0:
        movimientos['mes'] = pd.to_datetime(movimientos['fecha']).dt.strftime('%Y-%m')
        mov_mes = movimientos[movimientos['mes'] == mes_actual]
        gastos_mes = abs(mov_mes[mov_mes['importe'] < 0]['importe'].sum())

        mov_ant = movimientos[movimientos['mes'] == mes_anterior]
        gastos_anterior = abs(mov_ant[mov_ant['importe'] < 0]['importe'].sum())
        gastos_cambio = ((gastos_mes - gastos_anterior) / gastos_anterior * 100) if gastos_anterior > 0 else 0
    else:
        gastos_mes = 0
        gastos_cambio = 0

    # Rentabilidad total
    _, _, rentabilidad_pct, _ = calcular_rentabilidad_vehiculo(None)

    # Facturas pendientes (meses sin facturación para vehículos operativos)
    df_fact = get_facturacion(mes=mes_actual)
    vehiculos_con_factura = set(df_fact['vehiculo_id'].tolist()) if len(df_fact) > 0 else set()
    facturas_pendientes = vehiculos_activos - len(vehiculos_con_factura.intersection(VEHICULOS_OPERATIVOS))

    return {
        "vehiculos_activos": vehiculos_activos,
        "gastos_mes": round(gastos_mes, 2),
        "gastos_cambio_pct": round(gastos_cambio, 1),
        "rentabilidad_pct": round(rentabilidad_pct, 1),
        "facturas_pendientes": facturas_pendientes,
    }


def get_trend_data(period: str = "month"):
    """Datos de tendencia para el gráfico principal."""
    movimientos = get_movimientos()
    if len(movimientos) == 0:
        return []

    movimientos['fecha_dt'] = pd.to_datetime(movimientos['fecha'])

    if period == "week":
        movimientos['periodo'] = movimientos['fecha_dt'].dt.strftime('%Y-W%W')
    else:
        movimientos['periodo'] = movimientos['fecha_dt'].dt.strftime('%Y-%m')

    resumen = movimientos.groupby('periodo').agg(
        ingresos=('importe', lambda x: round(x[x > 0].sum(), 2)),
        gastos=('importe', lambda x: round(abs(x[x < 0].sum()), 2)),
    ).reset_index()

    resumen['balance'] = resumen['ingresos'] - resumen['gastos']
    resumen = resumen.sort_values('periodo').tail(12)

    return resumen.to_dict(orient='records')


def get_activity_feed(limit: int = 10):
    """Actividad reciente: últimas importaciones y movimientos."""
    items = []

    movimientos = get_movimientos()
    if len(movimientos) > 0 and 'created_at' in movimientos.columns:
        recientes = movimientos.sort_values('created_at', ascending=False).head(limit)
        for _, row in recientes.iterrows():
            items.append({
                "tipo": "movimiento",
                "descripcion": f"{row.get('descripcion', '')[:50]}",
                "detalle": f"Vehículo {row.get('vehiculo_id', 'N/A')} - {row.get('importe', 0):.2f}€",
                "timestamp": str(row.get('created_at', '')),
            })

    items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return items[:limit]


def get_monitoring_data():
    """Datos de monitoreo: estado de cada vehículo."""
    rows = []
    for veh_id in VEHICULOS_OPERATIVOS:
        fact, neto, margen, periodo = calcular_rentabilidad_vehiculo(veh_id)

        if margen < 0:
            estado = "perdidas"
        elif margen < 10:
            estado = "bajo"
        elif margen < 20:
            estado = "aceptable"
        else:
            estado = "bueno"

        mov = get_movimientos(vehiculo_id=veh_id)
        ultimo_mov = ""
        if len(mov) > 0:
            ultimo_mov = str(mov.iloc[0].get('fecha', ''))

        rows.append({
            "vehiculo_id": veh_id,
            "facturacion": round(fact, 2),
            "resultado_neto": round(neto, 2),
            "rentabilidad_pct": round(margen, 1),
            "estado": estado,
            "ultimo_movimiento": ultimo_mov,
            "periodo": periodo,
        })

    return rows
