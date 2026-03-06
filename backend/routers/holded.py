"""
LogisPLAN - Router de integración Holded
Endpoints para configurar y sincronizar datos desde Holded.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.services.holded_client import (
    get_api_key,
    set_api_key,
    get_holded_status,
    sync_facturas_emitidas,
    sync_gastos,
    sync_tesoreria,
    sync_todo,
    reaplicar_reglas_holded,
    limpiar_holded_y_resync,
)

router = APIRouter(prefix="/api/holded", tags=["holded"])


class ApiKeyRequest(BaseModel):
    api_key: str


# ---- Configuración ----

@router.get("/status")
def holded_status():
    """Verifica si la conexión con Holded está activa."""
    return get_holded_status()


@router.post("/configure")
def configure_holded(body: ApiKeyRequest):
    """Guarda la API Key de Holded."""
    if not body.api_key or len(body.api_key) < 10:
        raise HTTPException(status_code=400, detail="API Key inválida")

    set_api_key(body.api_key)
    status = get_holded_status()

    if not status.get("connected"):
        raise HTTPException(
            status_code=401,
            detail=status.get("error", "No se pudo conectar con Holded"),
        )

    return {"message": "API Key configurada correctamente", "status": status}


# ---- Sincronización ----

@router.post("/sync/facturas")
def sync_facturas_endpoint(
    mes_desde: Optional[str] = Query(None, description="YYYY-MM"),
    mes_hasta: Optional[str] = Query(None, description="YYYY-MM"),
):
    """Importa facturas emitidas desde Holded."""
    _check_configured()
    try:
        return sync_facturas_emitidas(mes_desde, mes_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/gastos")
def sync_gastos_endpoint(
    mes_desde: Optional[str] = Query(None, description="YYYY-MM"),
    mes_hasta: Optional[str] = Query(None, description="YYYY-MM"),
):
    """Importa gastos/compras desde Holded."""
    _check_configured()
    try:
        return sync_gastos(mes_desde, mes_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tesoreria")
def tesoreria_endpoint():
    """Obtiene cuentas bancarias desde Holded."""
    _check_configured()
    try:
        return sync_tesoreria()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/todo")
def sync_todo_endpoint(
    mes_desde: Optional[str] = Query(None, description="YYYY-MM"),
    mes_hasta: Optional[str] = Query(None, description="YYYY-MM"),
):
    """Sincronización completa: facturas + gastos + tesorería."""
    _check_configured()
    try:
        return sync_todo(mes_desde, mes_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reaplicar-reglas")
def reaplicar_reglas_endpoint():
    """Re-aplica reglas de categorización a movimientos Holded existentes."""
    _check_configured()
    try:
        return reaplicar_reglas_holded()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resync")
def resync_endpoint(
    mes_desde: Optional[str] = Query(None, description="YYYY-MM"),
    mes_hasta: Optional[str] = Query(None, description="YYYY-MM"),
):
    """Elimina datos Holded previos y re-sincroniza con reglas actualizadas."""
    _check_configured()
    try:
        return limpiar_holded_y_resync(mes_desde, mes_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _check_configured():
    if not get_api_key():
        raise HTTPException(
            status_code=400,
            detail="Holded no está configurado. Configura la API Key primero en /api/holded/configure",
        )
