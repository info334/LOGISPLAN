"""
LogisPLAN - Cliente de integración con Holded API

Lógica de importación:
- Facturas emitidas: split por línea de producto (cada línea = 1 vehículo)
- Gastos/Compras: auto-categorización con reglas BD + detección de matrícula
- Duplicados: se controlan por referencia holded:{id} en campo referencia
"""
import sys
import os
import re
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
import pandas as pd
from database import (
    insertar_movimientos,
    insertar_facturacion,
    get_reglas,
    get_connection,
    read_sql,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.holded.com/api/invoicing/v1"
CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "holded_config.json"


# =========================================================
#  Configuración
# =========================================================

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def _save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def get_api_key() -> Optional[str]:
    key = os.environ.get("HOLDED_API_KEY")
    return key or _load_config().get("api_key")

def set_api_key(api_key: str):
    config = _load_config()
    config["api_key"] = api_key
    _save_config(config)

def get_holded_status() -> dict:
    api_key = get_api_key()
    if not api_key:
        return {"connected": False, "error": "No hay API Key configurada"}
    try:
        resp = requests.get(f"{BASE_URL}/treasury", headers={"key": api_key}, timeout=10)
        if resp.status_code == 200:
            config = _load_config()
            return {"connected": True, "last_sync": config.get("last_sync"), "treasury_accounts": len(resp.json())}
        elif resp.status_code == 401:
            return {"connected": False, "error": "API Key invalida"}
        else:
            return {"connected": False, "error": f"Error HTTP {resp.status_code}"}
    except requests.RequestException as e:
        return {"connected": False, "error": str(e)}


# =========================================================
#  HTTP helpers
# =========================================================

def _get_headers() -> dict:
    api_key = get_api_key()
    if not api_key:
        raise ValueError("No hay API Key de Holded configurada")
    return {"key": api_key, "Content-Type": "application/json"}

def _fetch_all_pages(endpoint: str, params: dict = None) -> list:
    headers = _get_headers()
    params = dict(params or {})
    params.setdefault("limit", 100)
    params.setdefault("page", 1)
    all_items = []
    while True:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        all_items.extend(items)
        if len(items) < params["limit"]:
            break
        params["page"] += 1
        time.sleep(0.3)
    return all_items

def _fetch_document_detail(doc_type: str, doc_id: str) -> Optional[dict]:
    try:
        resp = requests.get(f"{BASE_URL}/documents/{doc_type}/{doc_id}", headers=_get_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"No se pudo obtener detalle de {doc_type}/{doc_id}: {e}")
    return None

def _unix_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""

def _unix_to_month(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m") if ts else ""

def _date_range_params(mes_desde, mes_hasta):
    now = datetime.now()
    if not mes_desde:
        mes_desde = (now.replace(day=1) - timedelta(days=90)).replace(day=1).strftime("%Y-%m")
    if not mes_hasta:
        mes_hasta = now.strftime("%Y-%m")
    start_dt = datetime.strptime(mes_desde + "-01", "%Y-%m-%d")
    ey, em = map(int, mes_hasta.split("-"))
    end_dt = datetime(ey + 1, 1, 1) if em == 12 else datetime(ey, em + 1, 1)
    return {
        "starttmp": str(int(start_dt.timestamp())),
        "endtmp": str(int(end_dt.timestamp())),
        "sort": "created-asc",
    }


# =========================================================
#  Detección de vehículos
# =========================================================

MATRICULAS = {
    "1257MTY": "MTY", "9245MJC": "MJC", "1382LVX": "LVX", "0245MLB": "MLB",
}

VEHICLE_KEYWORDS = {
    "MTY": ["MTY", "1257MTY", "1257 MTY", "1257-MTY", "MATERIAS PRIMAS", "SUSO"],
    "LVX": ["LVX", "1382LVX", "1382 LVX", "1382-LVX", "JOSÉ MANUEL", "JOSE MANUEL"],
    "MJC": ["MJC", "9245MJC", "9245 MJC", "9245-MJC", "CARLOS-MJC", "CARLOS MJC"],
    "MLB": ["MLB", "0245MLB", "0245 MLB", "0245-MLB"],
}

# Contactos de facturación → vehículo (para facturas emitidas completas)
INVOICE_CONTACT_VEHICLE = {
    "WARBURTON": "MLB",
    "UNIVERSIDADE DE SANTIAGO": "MLB",
}

MATRICULA_REGEX = re.compile(r'(\d{4})\s*[-]?\s*([A-Z]{3})')


def _detect_vehicle(text: str) -> Optional[str]:
    """Detecta vehículo en un texto por matrícula o keyword."""
    if not text:
        return None
    text_clean = text.upper().replace('-', '').replace(' ', '')
    # Matrícula exacta
    for mat, veh in MATRICULAS.items():
        if mat.replace('-', '') in text_clean:
            return veh
    # Regex
    for digits, letters in MATRICULA_REGEX.findall(text.upper()):
        key = digits + letters
        if key in MATRICULAS:
            return MATRICULAS[key]
    # Keywords
    text_upper = text.upper()
    for veh, kws in VEHICLE_KEYWORDS.items():
        for kw in kws:
            if kw in text_upper:
                return veh
    return None


def _detect_all_vehicles_in_products(products: list) -> dict:
    """
    Busca vehículos en todas las líneas de producto.
    Retorna {vehiculo_id: importe_total} para asignación parcial.
    """
    vehicle_totals = {}
    for p in products:
        text = f"{p.get('name', '')} {p.get('desc', '')} {p.get('sku', '')}"
        veh = _detect_vehicle(text)
        price = p.get("price", 0) or 0
        units = p.get("units", 1) or 1
        subtotal = price * units
        if veh:
            vehicle_totals[veh] = vehicle_totals.get(veh, 0) + subtotal
    return vehicle_totals


# =========================================================
#  Reglas de auto-categorización
# =========================================================

_reglas_cache = None
_reglas_ts = 0

def _get_reglas_cached():
    global _reglas_cache, _reglas_ts
    now = time.time()
    if _reglas_cache is None or (now - _reglas_ts) > 60:
        _reglas_cache = get_reglas()
        _reglas_ts = now
    return _reglas_cache

def _match_rules(texto: str):
    """Retorna (categoria_id, vehiculo_id) de la primera regla que coincida."""
    try:
        reglas = _get_reglas_cached()
        texto_upper = texto.upper()
        for _, r in reglas.iterrows():
            if str(r["patron"]).upper() in texto_upper:
                cat = r["categoria_id"]
                veh = r.get("vehiculo_id") if pd.notna(r.get("vehiculo_id")) else None
                return cat, veh
    except Exception:
        pass
    return None, None


# =========================================================
#  Control de duplicados por referencia holded:{id}
# =========================================================

def _get_existing_holded_refs() -> set:
    """
    Obtiene todas las referencias holded: existentes en movimientos.
    Devuelve tanto refs exactas como los IDs base (sin sufijo de vehículo).
    Ej: si existe 'holded:abc123:MTY', también incluye 'holded:abc123'.
    """
    try:
        conn = get_connection()
        df = read_sql("SELECT referencia FROM movimientos WHERE referencia LIKE 'holded:%'", conn)
        conn.close()
        refs = set(df["referencia"].tolist())
        # Añadir IDs base para que la comprobación por doc_id funcione
        base_refs = set()
        for r in refs:
            parts = r.split(":")
            if len(parts) >= 2:
                base_refs.add(f"{parts[0]}:{parts[1]}")
        refs.update(base_refs)
        return refs
    except Exception:
        return set()

def _get_existing_facturacion_descs() -> set:
    """Obtiene descripciones de facturación existentes para evitar duplicados."""
    try:
        conn = get_connection()
        df = read_sql("SELECT descripcion FROM facturacion WHERE descripcion LIKE 'Holded%'", conn)
        conn.close()
        return set(df["descripcion"].tolist())
    except Exception:
        return set()


# =========================================================
#  FACTURAS EMITIDAS (Ventas) - Split por línea/vehículo
# =========================================================

def sync_facturas_emitidas(mes_desde=None, mes_hasta=None) -> dict:
    """
    Importa facturas de venta. Cada línea de producto con vehículo detectado
    se suma al total del mes+vehículo correspondiente.

    La tabla facturacion tiene UNIQUE(mes, vehiculo_id), así que acumulamos
    todos los importes por (mes, vehiculo) y hacemos un upsert final.
    """
    params = _date_range_params(mes_desde, mes_hasta)
    facturas = _fetch_all_pages("documents/invoice", params)
    logger.info(f"Holded: {len(facturas)} facturas emitidas descargadas")

    resultado = {"importadas": 0, "facturas_procesadas": len(facturas), "errores": 0, "detalle": []}

    # Acumular importes por (mes, vehiculo_id)
    # La tabla facturacion tiene UNIQUE(mes, vehiculo_id) con INSERT OR REPLACE,
    # así que cada sync recalcula los totales (es idempotente).
    acumulado = {}  # {(mes, vehiculo_id): importe_total}

    for fact in facturas:
        try:
            doc_id = fact.get("id", "")
            fecha = fact.get("date", 0)
            mes = _unix_to_month(fecha)
            total = fact.get("total", 0)
            contacto = fact.get("contactName", "")
            doc_number = fact.get("docNumber", "")

            # Obtener detalle completo para tener los precios de cada línea
            detail = _fetch_document_detail("invoice", doc_id) if doc_id else None
            products = (detail or fact).get("products", (detail or fact).get("items", []))
            time.sleep(0.15)

            # Detectar vehículos por línea de producto
            vehicle_totals = _detect_all_vehicles_in_products(products)

            if vehicle_totals:
                # Repartir el total de la factura (con IVA) proporcionalmente
                asignado_base = sum(vehicle_totals.values())
                for veh_id, importe_base in vehicle_totals.items():
                    if asignado_base > 0:
                        proporcion = importe_base / asignado_base
                        importe_con_iva = round(total * proporcion, 2)
                    else:
                        importe_con_iva = importe_base
                    key = (mes, veh_id)
                    acumulado[key] = acumulado.get(key, 0) + importe_con_iva
                    resultado["detalle"].append({
                        "doc": doc_number, "contacto": contacto,
                        "total": importe_con_iva, "vehiculo": veh_id, "mes": mes,
                        "tipo": "parcial",
                    })

            else:
                # Sin desglose: asignar todo a un vehículo o COMÚN
                veh = _detect_vehicle(contacto) or _detect_vehicle(fact.get("desc", ""))
                if not veh:
                    _, veh = _match_rules(contacto)
                if not veh:
                    # Buscar por contacto de facturación
                    contacto_upper = contacto.upper()
                    for pattern, v in INVOICE_CONTACT_VEHICLE.items():
                        if pattern in contacto_upper:
                            veh = v
                            break
                if not veh:
                    veh = "COMÚN"

                key = (mes, veh)
                acumulado[key] = acumulado.get(key, 0) + total
                resultado["detalle"].append({
                    "doc": doc_number, "contacto": contacto,
                    "total": total, "vehiculo": veh, "mes": mes,
                    "tipo": "completa",
                })

        except Exception as e:
            logger.error(f"Error factura {fact.get('id')}: {e}")
            resultado["errores"] += 1

    # Insertar los totales acumulados por (mes, vehiculo)
    for (mes, veh_id), importe_total in acumulado.items():
        try:
            insertar_facturacion({
                "mes": mes,
                "vehiculo_id": veh_id,
                "importe": round(importe_total, 2),
                "descripcion": f"Holded sync {mes} [{veh_id}]",
            })
            resultado["importadas"] += 1
        except Exception as e:
            logger.error(f"Error insertando facturación {mes}/{veh_id}: {e}")
            resultado["errores"] += 1

    return resultado


# =========================================================
#  GASTOS / COMPRAS - Con reglas + detección matrícula
# =========================================================

def sync_gastos(mes_desde=None, mes_hasta=None) -> dict:
    """
    Importa facturas de compra. Aplica:
    1. Reglas BD para categoría y vehículo
    2. Detección de matrícula en líneas de producto (split parcial si hay varias)
    3. Control de duplicados por referencia holded:{id}
    """
    params = _date_range_params(mes_desde, mes_hasta)
    compras = _fetch_all_pages("documents/purchase", params)
    logger.info(f"Holded: {len(compras)} compras descargadas")

    existing_refs = _get_existing_holded_refs()
    movimientos = []
    detalle = []
    errores = 0

    for compra in compras:
        try:
            holded_id = compra.get("id", "")
            ref = f"holded:{holded_id}"

            # Duplicado por referencia
            if ref in existing_refs:
                detalle.append({"doc": compra.get("docNumber"), "estado": "duplicado"})
                continue

            fecha = _unix_to_date(compra.get("date", 0))
            total = compra.get("total", 0)
            contacto = compra.get("contactName", "")
            doc_number = compra.get("docNumber", "")
            desc = compra.get("desc", "")
            texto = f"{contacto} {desc} {doc_number}"

            # Reglas BD → categoría + vehículo
            cat_regla, veh_regla = _match_rules(texto)

            # Obtener detalle para buscar matrículas en líneas
            detail = _fetch_document_detail("purchase", holded_id) if holded_id else None
            products = (detail or compra).get("products", (detail or compra).get("items", []))
            time.sleep(0.15)

            # Buscar matrículas en las líneas de producto
            vehicle_totals = _detect_all_vehicles_in_products(products)

            if vehicle_totals and len(vehicle_totals) > 1:
                # SPLIT PARCIAL: factura con múltiples vehículos (ej: Solred, Valcarce)
                for veh_id, importe in vehicle_totals.items():
                    movimientos.append({
                        "fecha": fecha,
                        "descripcion": f"Holded #{doc_number} - {contacto} [{veh_id}]",
                        "importe": -abs(importe),
                        "categoria_id": cat_regla,
                        "vehiculo_id": veh_id,
                        "referencia": f"{ref}:{veh_id}",
                    })
                # Resto no asignado
                asignado = sum(vehicle_totals.values())
                resto = abs(total) - asignado
                if abs(resto) > 1:
                    movimientos.append({
                        "fecha": fecha,
                        "descripcion": f"Holded #{doc_number} - {contacto} [COMÚN]",
                        "importe": -abs(resto),
                        "categoria_id": cat_regla,
                        "vehiculo_id": "COMÚN",
                        "referencia": f"{ref}:COMÚN",
                    })
                detalle.append({
                    "doc": doc_number, "contacto": contacto, "total": total,
                    "vehiculos": list(vehicle_totals.keys()), "categoria": cat_regla,
                    "tipo": "split", "fecha": fecha,
                })

            elif vehicle_totals and len(vehicle_totals) == 1:
                # Un solo vehículo detectado en líneas → asignar todo
                veh_id = list(vehicle_totals.keys())[0]
                movimientos.append({
                    "fecha": fecha,
                    "descripcion": f"Holded #{doc_number} - {contacto}",
                    "importe": -abs(total),
                    "categoria_id": cat_regla,
                    "vehiculo_id": veh_id,
                    "referencia": ref,
                })
                detalle.append({
                    "doc": doc_number, "contacto": contacto, "total": total,
                    "vehiculo": veh_id, "fuente": "matricula",
                    "categoria": cat_regla, "fecha": fecha,
                })

            else:
                # Sin matrícula en líneas → usar regla o dejar sin asignar
                veh = veh_regla or _detect_vehicle(texto)
                movimientos.append({
                    "fecha": fecha,
                    "descripcion": f"Holded #{doc_number} - {contacto}" + (f" - {desc}" if desc else ""),
                    "importe": -abs(total) if total > 0 else total,
                    "categoria_id": cat_regla,
                    "vehiculo_id": veh,
                    "referencia": ref,
                })
                detalle.append({
                    "doc": doc_number, "contacto": contacto, "total": total,
                    "vehiculo": veh, "fuente": "regla" if veh_regla else ("keyword" if veh else "sin_asignar"),
                    "categoria": cat_regla, "fecha": fecha,
                })

        except Exception as e:
            logger.error(f"Error compra {compra.get('id')}: {e}")
            errores += 1

    # Insertar en batch
    if movimientos:
        res = insertar_movimientos(
            movimientos,
            archivo_nombre=f"holded_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tipo="holded_gastos",
        )
    else:
        res = {"insertados": 0, "duplicados": 0}

    dup_count = sum(1 for d in detalle if d.get("estado") == "duplicado")

    return {
        "insertados": res.get("insertados", 0),
        "duplicados_ref": dup_count,
        "duplicados_db": res.get("duplicados", 0),
        "total_descargados": len(compras),
        "errores": errores,
        "detalle": [d for d in detalle if d.get("estado") != "duplicado"],
    }


# =========================================================
#  Tesorería + Sync completo
# =========================================================

def sync_tesoreria() -> dict:
    resp = requests.get(f"{BASE_URL}/treasury", headers=_get_headers(), timeout=15)
    resp.raise_for_status()
    return {"cuentas": [
        {"id": c.get("id"), "nombre": c.get("name"), "tipo": c.get("type"),
         "balance": c.get("balance", 0), "iban": c.get("iban", ""), "banco": c.get("bankname", "")}
        for c in resp.json()
    ]}


def reaplicar_reglas_holded() -> dict:
    """
    Re-aplica reglas de categorización y detección de vehículo a todos los
    movimientos importados de Holded que aún no tienen categoría o vehículo.
    Útil después de actualizar las reglas o si la sync anterior no las aplicó bien.
    """
    conn = get_connection()
    df = read_sql("""
        SELECT id, descripcion, categoria_id, vehiculo_id
        FROM movimientos
        WHERE referencia LIKE 'holded:%'
    """, conn)

    actualizados = 0
    for _, row in df.iterrows():
        texto = row["descripcion"]
        cat_actual = row["categoria_id"]
        veh_actual = row["vehiculo_id"]

        # Solo actualizar si falta categoría o vehículo
        nueva_cat, nuevo_veh = _match_rules(texto)
        veh_detect = _detect_vehicle(texto)

        cat_final = cat_actual if (cat_actual and str(cat_actual).strip()) else nueva_cat
        veh_final = veh_actual if (veh_actual and str(veh_actual).strip()) else (nuevo_veh or veh_detect)

        # Corregir COMUN → COMÚN (sin tilde)
        if veh_final == "COMUN":
            veh_final = "COMÚN"

        if cat_final != cat_actual or veh_final != veh_actual:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE movimientos SET categoria_id = ?, vehiculo_id = ?
                WHERE id = ?
            """, (cat_final, veh_final, row["id"]))
            actualizados += 1

    conn.commit()
    if hasattr(conn, 'sync'):
        conn.sync()
    conn.close()

    return {"total_revisados": len(df), "actualizados": actualizados}


def limpiar_holded_y_resync(mes_desde=None, mes_hasta=None) -> dict:
    """
    Elimina todos los movimientos importados de Holded y vuelve a sincronizar.
    Esto permite re-importar con las reglas y detección actualizadas.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimientos WHERE referencia LIKE 'holded:%'")
    eliminados = cursor.rowcount
    conn.commit()
    if hasattr(conn, 'sync'):
        conn.sync()
    conn.close()

    logger.info(f"Eliminados {eliminados} movimientos holded previos. Re-sincronizando...")
    resultado = sync_gastos(mes_desde, mes_hasta)
    resultado["eliminados_previos"] = eliminados
    return resultado


def sync_todo(mes_desde=None, mes_hasta=None) -> dict:
    resultado = {"facturas": None, "gastos": None, "tesoreria": None,
                 "timestamp": datetime.now().isoformat(), "errores_globales": []}

    for key, fn in [("facturas", sync_facturas_emitidas), ("gastos", sync_gastos), ("tesoreria", sync_tesoreria)]:
        try:
            if key == "tesoreria":
                resultado[key] = fn()
            else:
                resultado[key] = fn(mes_desde, mes_hasta)
        except Exception as e:
            resultado["errores_globales"].append(f"{key}: {str(e)}")
            logger.error(f"Error sync {key}: {e}")

    config = _load_config()
    config["last_sync"] = resultado["timestamp"]
    _save_config(config)
    return resultado
