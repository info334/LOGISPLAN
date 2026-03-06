"""
LogisPLAN - Router de Dashboard
Endpoints para KPIs, tendencia, actividad y monitoreo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query

from backend.services.analytics import (
    get_dashboard_kpis,
    get_trend_data,
    get_activity_feed,
    get_monitoring_data,
)
from database import get_connection, read_sql

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

VEHICULOS_OPERATIVOS = ["MTY", "LVX", "MJC", "MLB"]


@router.get("/kpis")
def dashboard_kpis():
    return get_dashboard_kpis()


@router.get("/trend")
def dashboard_trend(period: str = Query("month", enum=["week", "month"])):
    return get_trend_data(period)


@router.get("/activity")
def dashboard_activity(limit: int = Query(10, ge=1, le=50)):
    return get_activity_feed(limit)


@router.get("/monitoring")
def dashboard_monitoring():
    return get_monitoring_data()


@router.get("/rentabilidad-matriz")
def rentabilidad_matriz():
    """
    Devuelve la matriz de rentabilidad: por vehículo y mes.
    Ingresos = facturación, Gastos = movimientos negativos (directos + COMÚN prorrateado).
    """
    conn = get_connection()

    # Facturación por vehículo y mes
    df_fact = read_sql("""
        SELECT mes, vehiculo_id, SUM(importe) as ingresos
        FROM facturacion
        WHERE vehiculo_id != 'COMÚN'
        GROUP BY mes, vehiculo_id
    """, conn)

    # Gastos directos por vehículo y mes
    df_gastos_dir = read_sql("""
        SELECT strftime('%Y-%m', fecha) as mes, vehiculo_id, SUM(importe) as gastos
        FROM movimientos
        WHERE vehiculo_id IN ({})
          AND importe < 0
        GROUP BY mes, vehiculo_id
    """.format(",".join(f"'{v}'" for v in VEHICULOS_OPERATIVOS)), conn)

    # Gastos COMÚN por mes (se prorratean)
    df_gastos_comun = read_sql("""
        SELECT strftime('%Y-%m', fecha) as mes, SUM(importe) as gastos
        FROM movimientos
        WHERE vehiculo_id = 'COMÚN'
          AND importe < 0
        GROUP BY mes
    """, conn)

    conn.close()

    # Construir la matriz
    # Recoger todos los meses de facturación
    meses = sorted(df_fact["mes"].unique().tolist()) if len(df_fact) > 0 else []
    num_vehiculos = len(VEHICULOS_OPERATIVOS)

    resultado = []
    for veh in VEHICULOS_OPERATIVOS:
        fila = {"vehiculo_id": veh, "meses": {}}
        for mes in meses:
            # Ingresos
            ingresos = 0.0
            mask_f = (df_fact["mes"] == mes) & (df_fact["vehiculo_id"] == veh)
            if mask_f.any():
                ingresos = float(df_fact.loc[mask_f, "ingresos"].sum())

            # Gastos directos
            gastos_dir = 0.0
            if len(df_gastos_dir) > 0:
                mask_g = (df_gastos_dir["mes"] == mes) & (df_gastos_dir["vehiculo_id"] == veh)
                if mask_g.any():
                    gastos_dir = abs(float(df_gastos_dir.loc[mask_g, "gastos"].sum()))

            # Gastos comunes prorrateados
            gastos_comun = 0.0
            if len(df_gastos_comun) > 0:
                mask_c = df_gastos_comun["mes"] == mes
                if mask_c.any():
                    gastos_comun = abs(float(df_gastos_comun.loc[mask_c, "gastos"].sum())) / num_vehiculos

            gastos_total = round(gastos_dir + gastos_comun, 2)
            neto = round(ingresos - gastos_total, 2)
            margen = round((neto / ingresos) * 100, 1) if ingresos > 0 else 0.0

            fila["meses"][mes] = {
                "ingresos": round(ingresos, 2),
                "gastos": gastos_total,
                "neto": neto,
                "margen_pct": margen,
            }
        resultado.append(fila)

    return {"vehiculos": resultado, "meses": meses}


@router.get("/costes-matriz")
def costes_matriz():
    """
    Matriz de costes por vehículo y mes.
    Devuelve: ingresos, gastos (gasoil, salario, otros), km, coste/km, margen bruto.
    Gastos = movimientos directos + COMÚN prorrateado + costes laborales directos + COMÚN prorrateado.
    """
    conn = get_connection()

    # Facturación por vehículo y mes
    df_fact = read_sql("""
        SELECT mes, vehiculo_id, SUM(importe) as ingresos
        FROM facturacion
        WHERE vehiculo_id IN ({})
        GROUP BY mes, vehiculo_id
    """.format(",".join(f"'{v}'" for v in VEHICULOS_OPERATIVOS)), conn)

    # Gastos directos por vehículo, mes y categoría
    df_gastos_dir = read_sql("""
        SELECT strftime('%Y-%m', fecha) as mes, vehiculo_id, categoria_id,
               SUM(ABS(importe)) as gastos
        FROM movimientos
        WHERE vehiculo_id IN ({})
          AND importe < 0
        GROUP BY mes, vehiculo_id, categoria_id
    """.format(",".join(f"'{v}'" for v in VEHICULOS_OPERATIVOS)), conn)

    # Gastos COMÚN por mes y categoría (se prorratean)
    df_gastos_comun = read_sql("""
        SELECT strftime('%Y-%m', fecha) as mes, categoria_id,
               SUM(ABS(importe)) as gastos
        FROM movimientos
        WHERE vehiculo_id = 'COMÚN'
          AND importe < 0
        GROUP BY mes, categoria_id
    """, conn)

    # Gastos sin asignar por mes y categoría (se prorratean también)
    df_gastos_sin = read_sql("""
        SELECT strftime('%Y-%m', fecha) as mes, categoria_id,
               SUM(ABS(importe)) as gastos
        FROM movimientos
        WHERE (vehiculo_id IS NULL OR vehiculo_id = '')
          AND importe < 0
        GROUP BY mes, categoria_id
    """, conn)

    # Costes laborales directos por vehículo y mes
    df_labor_dir = read_sql("""
        SELECT mes, vehiculo_id, SUM(coste_total) as coste
        FROM costes_laborales
        WHERE vehiculo_id IN ({})
        GROUP BY mes, vehiculo_id
    """.format(",".join(f"'{v}'" for v in VEHICULOS_OPERATIVOS)), conn)

    # Costes laborales COMÚN por mes (se prorratean)
    df_labor_comun = read_sql("""
        SELECT mes, SUM(coste_total) as coste
        FROM costes_laborales
        WHERE vehiculo_id = 'COMÚN'
        GROUP BY mes
    """, conn)

    # Kilómetros por vehículo y mes
    df_km = read_sql("""
        SELECT mes, vehiculo_id, km
        FROM hojas_ruta
        WHERE zona = 'TOTAL'
    """, conn)

    conn.close()

    # Categorías de gasoil
    CATS_GASOIL = {"COMB"}
    num_veh = len(VEHICULOS_OPERATIVOS)

    # Recoger todos los meses con datos
    all_meses = set()
    if len(df_fact) > 0:
        all_meses.update(df_fact["mes"].unique())
    if len(df_gastos_dir) > 0:
        all_meses.update(df_gastos_dir["mes"].unique())
    if len(df_gastos_comun) > 0:
        all_meses.update(df_gastos_comun["mes"].unique())
    if len(df_gastos_sin) > 0:
        all_meses.update(df_gastos_sin["mes"].unique())
    if len(df_labor_dir) > 0:
        all_meses.update(df_labor_dir["mes"].unique())
    if len(df_labor_comun) > 0:
        all_meses.update(df_labor_comun["mes"].unique())
    meses = sorted(all_meses)

    def sum_df(df, filters):
        if len(df) == 0:
            return 0.0
        mask = None
        for col, val in filters.items():
            m = df[col] == val
            mask = m if mask is None else (mask & m)
        if mask is not None and mask.any():
            return float(df.loc[mask].iloc[:, -1].sum())
        return 0.0

    def sum_df_cats(df, mes, vehiculo_id, cats):
        """Sum gastos for specific category set."""
        if len(df) == 0:
            return 0.0
        mask = (df["mes"] == mes) & (df["vehiculo_id"] == vehiculo_id)
        if "categoria_id" in df.columns:
            mask = mask & (df["categoria_id"].isin(cats))
        if mask.any():
            return float(df.loc[mask, "gastos"].sum())
        return 0.0

    def sum_comun_cats(df, mes, cats):
        """Sum COMÚN/unassigned gastos for specific category set."""
        if len(df) == 0:
            return 0.0
        mask = df["mes"] == mes
        if "categoria_id" in df.columns:
            mask = mask & (df["categoria_id"].isin(cats))
        if mask.any():
            return float(df.loc[mask, "gastos"].sum())
        return 0.0

    def sum_no_cat(df, mes, vehiculo_id=None):
        """Sum gastos with no category (NaN)."""
        if len(df) == 0 or "categoria_id" not in df.columns:
            return 0.0
        mask = (df["mes"] == mes) & (df["categoria_id"].isna())
        if vehiculo_id is not None:
            mask = mask & (df["vehiculo_id"] == vehiculo_id)
        return float(df.loc[mask, "gastos"].sum()) if mask.any() else 0.0

    # Compute non-gasoil categories once (used for "otros" calculation)
    all_cats_except_gasoil = set()
    if len(df_gastos_dir) > 0:
        all_cats_except_gasoil.update(df_gastos_dir["categoria_id"].dropna().unique())
    if len(df_gastos_comun) > 0:
        all_cats_except_gasoil.update(df_gastos_comun["categoria_id"].dropna().unique())
    if len(df_gastos_sin) > 0:
        all_cats_except_gasoil.update(df_gastos_sin["categoria_id"].dropna().unique())
    all_cats_except_gasoil -= CATS_GASOIL

    resultado = []
    for veh in VEHICULOS_OPERATIVOS:
        fila = {"vehiculo_id": veh, "meses": {}}
        for mes in meses:
            # Ingresos
            ingresos = sum_df(df_fact, {"mes": mes, "vehiculo_id": veh})

            # Gastos gasoil (directos)
            gasoil_dir = sum_df_cats(df_gastos_dir, mes, veh, CATS_GASOIL)
            # Gasoil COMÚN prorrateado
            gasoil_comun = sum_comun_cats(df_gastos_comun, mes, CATS_GASOIL) / num_veh
            # Gasoil sin asignar prorrateado
            gasoil_sin = sum_comun_cats(df_gastos_sin, mes, CATS_GASOIL) / num_veh
            gasoil = round(gasoil_dir + gasoil_comun + gasoil_sin, 2)

            # Salario (costes laborales)
            salario_dir = sum_df(df_labor_dir, {"mes": mes, "vehiculo_id": veh})
            salario_comun = sum_df(df_labor_comun, {"mes": mes}) / num_veh
            salario = round(salario_dir + salario_comun, 2)

            # Otros gastos (todo excepto gasoil)
            otros_dir = sum_df_cats(df_gastos_dir, mes, veh, all_cats_except_gasoil)
            otros_comun = sum_comun_cats(df_gastos_comun, mes, all_cats_except_gasoil) / num_veh
            otros_sin = sum_comun_cats(df_gastos_sin, mes, all_cats_except_gasoil) / num_veh

            # Also include expenses without category
            otros_dir += sum_no_cat(df_gastos_dir, mes, veh)
            otros_comun += sum_no_cat(df_gastos_comun, mes) / num_veh
            otros_sin += sum_no_cat(df_gastos_sin, mes) / num_veh

            otros = round(otros_dir + otros_comun + otros_sin, 2)

            gastos_total = round(gasoil + salario + otros, 2)
            neto = round(ingresos - gastos_total, 2)
            margen = round((neto / ingresos) * 100, 1) if ingresos > 0 else 0.0

            # Km
            km = 0.0
            if len(df_km) > 0:
                mask_km = (df_km["mes"] == mes) & (df_km["vehiculo_id"] == veh)
                if mask_km.any():
                    km = float(df_km.loc[mask_km, "km"].sum())

            coste_km = round(gastos_total / km, 2) if km > 0 else None

            fila["meses"][mes] = {
                "ingresos": round(ingresos, 2),
                "gastos": gastos_total,
                "gasoil": gasoil,
                "salario": salario,
                "otros": otros,
                "neto": neto,
                "margen_pct": margen,
                "km": km,
                "coste_km": coste_km,
            }
        resultado.append(fila)

    return {"vehiculos": resultado, "meses": meses}
