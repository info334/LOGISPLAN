"""
LogisPLAN - Router de Facturación
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from database import (
    get_facturacion, get_resumen_facturacion_por_vehiculo,
    get_vehiculos, get_connection, read_sql,
)

router = APIRouter(prefix="/api/facturacion", tags=["facturacion"])


class AsignarVehiculoRequest(BaseModel):
    vehiculo_id: str


@router.get("")
def listar_facturacion(
    mes: Optional[str] = Query(None),
    vehiculo_id: Optional[str] = Query(None),
):
    df = get_facturacion(mes=mes, vehiculo_id=vehiculo_id)
    return df.to_dict(orient='records')


@router.get("/resumen")
def resumen_por_vehiculo():
    df = get_resumen_facturacion_por_vehiculo()
    return df.to_dict(orient='records')


@router.get("/periodos")
def periodos_disponibles():
    conn = get_connection()
    df = read_sql("SELECT DISTINCT mes FROM facturacion ORDER BY mes DESC", conn)
    conn.close()
    return df["mes"].tolist()


@router.put("/{factura_id}/asignar")
def asignar_vehiculo(factura_id: int, req: AsignarVehiculoRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE facturacion SET vehiculo_id = ? WHERE id = ?",
        (req.vehiculo_id, factura_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "id": factura_id}
