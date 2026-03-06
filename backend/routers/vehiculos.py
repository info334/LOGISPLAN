"""
LogisPLAN - Router de Vehículos
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter

from database import get_vehiculos, get_vehiculos_operativos
from backend.services.profitability import calcular_rentabilidad_vehiculo

router = APIRouter(prefix="/api/vehiculos", tags=["vehiculos"])


@router.get("")
def listar_vehiculos():
    df = get_vehiculos()
    return df.to_dict(orient='records')


@router.get("/operativos")
def listar_operativos():
    df = get_vehiculos_operativos()
    return df.to_dict(orient='records')


@router.get("/{vehiculo_id}/rentabilidad")
def rentabilidad_vehiculo(vehiculo_id: str):
    fact, neto, margen, periodo = calcular_rentabilidad_vehiculo(vehiculo_id)
    return {
        "vehiculo_id": vehiculo_id,
        "facturacion": round(fact, 2),
        "resultado_neto": round(neto, 2),
        "margen_pct": round(margen, 1),
        "periodo": periodo,
    }
