"""
LogisPLAN - Router de Movimientos
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import (
    get_movimientos,
    get_periodos_disponibles,
    actualizar_movimiento,
    get_vehiculos,
    get_categorias,
)

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])


class AsignarRequest(BaseModel):
    vehiculo_id: Optional[str] = None
    categoria_id: Optional[str] = None


class AsignarBatchRequest(BaseModel):
    ids: list[int]
    vehiculo_id: Optional[str] = None
    categoria_id: Optional[str] = None


@router.get("")
def listar_movimientos(
    vehiculo_id: Optional[str] = Query(None),
    categoria_id: Optional[str] = Query(None),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    sin_asignar: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
):
    df = get_movimientos(
        vehiculo_id=vehiculo_id,
        categoria_id=categoria_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    # Filtrar movimientos sin vehículo asignado
    if sin_asignar:
        df = df[(df['vehiculo_id'].isna()) | (df['vehiculo_id'] == '') | (df['vehiculo_id'].isnull())]

    total = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    records = df.iloc[start:end].to_dict(orient='records')

    return {
        "data": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/periodos")
def periodos_disponibles():
    return get_periodos_disponibles()


@router.get("/opciones")
def opciones_asignacion():
    """Devuelve las opciones de vehículos y categorías para los selectores."""
    vehiculos_df = get_vehiculos()
    categorias_df = get_categorias()
    return {
        "vehiculos": vehiculos_df.to_dict(orient='records'),
        "categorias": categorias_df.to_dict(orient='records'),
    }


@router.put("/{movimiento_id}/asignar")
def asignar_movimiento(movimiento_id: int, body: AsignarRequest):
    """Asigna vehículo y/o categoría a un movimiento individual."""
    try:
        actualizar_movimiento(
            id=movimiento_id,
            categoria_id=body.categoria_id or '',
            vehiculo_id=body.vehiculo_id or '',
        )
        return {"ok": True, "id": movimiento_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/asignar-batch")
def asignar_batch(body: AsignarBatchRequest):
    """Asigna vehículo y/o categoría a múltiples movimientos a la vez."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No se proporcionaron IDs")

    errores = []
    actualizados = 0
    for mid in body.ids:
        try:
            actualizar_movimiento(
                id=mid,
                categoria_id=body.categoria_id or '',
                vehiculo_id=body.vehiculo_id or '',
            )
            actualizados += 1
        except Exception as e:
            errores.append({"id": mid, "error": str(e)})

    return {
        "actualizados": actualizados,
        "errores": len(errores),
        "detalle_errores": errores,
    }
