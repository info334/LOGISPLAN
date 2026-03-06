"""
LogisPLAN - Router de Configuración
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
import tempfile

from fastapi import APIRouter, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List

from database import (
    get_categorias, get_reglas, get_connection, read_sql,
    get_costes_laborales, insertar_coste_laboral, eliminar_coste_laboral,
)
from backend.services.pdf_parser import parse_costes_laborales, parse_recorridos, parse_gasoil_solred

router = APIRouter(prefix="/api/configuracion", tags=["configuracion"])


@router.get("/categorias")
def listar_categorias():
    df = get_categorias()
    return df.to_dict(orient='records')


@router.get("/reglas")
def listar_reglas():
    df = get_reglas()
    return df.to_dict(orient='records')


# =========================================================
#  Kilómetros por vehículo y mes
# =========================================================

class KmInput(BaseModel):
    mes: str
    vehiculo_id: str
    km: float


@router.get("/km")
def listar_km(mes: Optional[str] = Query(None), vehiculo_id: Optional[str] = Query(None)):
    conn = get_connection()
    query = "SELECT * FROM hojas_ruta WHERE zona = 'TOTAL'"
    params = []
    if mes:
        query += " AND mes = ?"
        params.append(mes)
    if vehiculo_id:
        query += " AND vehiculo_id = ?"
        params.append(vehiculo_id)
    query += " ORDER BY mes DESC, vehiculo_id"
    df = read_sql(query, conn, params=params)
    conn.close()
    return df.to_dict(orient="records")


@router.post("/km")
def guardar_km(data: KmInput):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO hojas_ruta
        (mes, vehiculo_id, zona, km, viajes, repartos, media_repartos_viaje, dias_trabajados)
        VALUES (?, ?, 'TOTAL', ?, 0, 0, 0, 0)
    """, (data.mes, data.vehiculo_id, data.km))
    conn.commit()
    conn.close()
    return {"ok": True, "mes": data.mes, "vehiculo_id": data.vehiculo_id, "km": data.km}


@router.post("/km/batch")
def guardar_km_batch(datos: List[KmInput]):
    conn = get_connection()
    cursor = conn.cursor()
    for d in datos:
        cursor.execute("""
            INSERT OR REPLACE INTO hojas_ruta
            (mes, vehiculo_id, zona, km, viajes, repartos, media_repartos_viaje, dias_trabajados)
            VALUES (?, ?, 'TOTAL', ?, 0, 0, 0, 0)
        """, (d.mes, d.vehiculo_id, d.km))
    conn.commit()
    conn.close()
    return {"ok": True, "guardados": len(datos)}


@router.delete("/km/{km_id}")
def eliminar_km(km_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hojas_ruta WHERE id = ?", (km_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# =========================================================
#  Costes laborales
# =========================================================

class CosteLaboralInput(BaseModel):
    mes: str
    trabajador_id: int
    nombre: str
    vehiculo_id: Optional[str] = None
    bruto: float = 0
    ss_trabajador: float = 0
    irpf: float = 0
    liquido: float = 0
    ss_empresa: float = 0
    coste_total: float = 0


@router.get("/costes-laborales")
def listar_costes_laborales(
    mes: Optional[str] = Query(None),
    vehiculo_id: Optional[str] = Query(None),
):
    df = get_costes_laborales(mes=mes, vehiculo_id=vehiculo_id)
    return df.to_dict(orient="records")


@router.post("/costes-laborales")
def guardar_coste_laboral(data: CosteLaboralInput):
    coste_id = insertar_coste_laboral(data.model_dump())
    return {"ok": True, "id": coste_id}


@router.delete("/costes-laborales/{coste_id}")
def borrar_coste_laboral(coste_id: int):
    eliminar_coste_laboral(coste_id)
    return {"ok": True}


# =========================================================
#  Importar PDFs
# =========================================================

@router.post("/importar/costes-pdf")
async def importar_costes_pdf(file: UploadFile = File(...)):
    """Import labor costs from a PDF (COST - YYYYMM - Emp XX.pdf)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = parse_costes_laborales(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Insert into database
    insertados = 0
    for t in result["trabajadores"]:
        t["mes"] = result["mes"]
        insertar_coste_laboral(t)
        insertados += 1

    return {
        "ok": True,
        "tipo": "costes_laborales",
        "mes": result["mes"],
        "trabajadores": insertados,
        "detalle": result["trabajadores"],
    }


@router.post("/importar/recorridos-pdf")
async def importar_recorridos_pdf(file: UploadFile = File(...)):
    """Import route km from a Localiza recorridos PDF."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = parse_recorridos(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Insert into database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO hojas_ruta
        (mes, vehiculo_id, zona, km, viajes, repartos, media_repartos_viaje, dias_trabajados)
        VALUES (?, ?, 'TOTAL', ?, 0, 0, 0, ?)
    """, (result["mes"], result["vehiculo_id"], result["km_total"], result["dias_trabajados"]))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "tipo": "recorridos",
        "vehiculo_id": result["vehiculo_id"],
        "mes": result["mes"],
        "km_total": result["km_total"],
        "dias_trabajados": result["dias_trabajados"],
    }


@router.post("/importar/gasoil-pdf")
async def importar_gasoil_pdf(file: UploadFile = File(...)):
    """Import fuel costs from a SOLRED PDF, splitting by vehicle."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = parse_gasoil_solred(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Insert/update movimientos per vehicle
    conn = get_connection()
    cursor = conn.cursor()
    insertados = 0
    for veh_id, importe in result["vehiculos"].items():
        ref = f"solred:{result['factura']}:{veh_id}"
        # Check if already exists
        cursor.execute("SELECT id FROM movimientos WHERE referencia = ?", (ref,))
        existing = cursor.fetchone()
        if existing:
            # Update
            cursor.execute("""
                UPDATE movimientos SET importe = ?, vehiculo_id = ?, categoria_id = 'COMB'
                WHERE referencia = ?
            """, (-abs(importe), veh_id, ref))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO movimientos (fecha, descripcion, importe, categoria_id, vehiculo_id, referencia)
                VALUES (?, ?, ?, 'COMB', ?, ?)
            """, (
                result["fecha_hasta"],
                f"SOLRED {result['factura']} [{veh_id}] {result['fecha_desde']} al {result['fecha_hasta']}",
                -abs(importe),
                veh_id,
                ref,
            ))
        insertados += 1
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "tipo": "gasoil",
        "factura": result["factura"],
        "mes": result["mes"],
        "fecha_desde": result["fecha_desde"],
        "fecha_hasta": result["fecha_hasta"],
        "vehiculos": result["vehiculos"],
        "total": result["total"],
        "insertados": insertados,
    }
