"""
LogisPLAN - Módulo de Base de Datos
Gestión de tablas SQLite para flota de transporte Severino Logística
Soporta Turso (libsql) en producción y SQLite local en desarrollo.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
import pandas as pd

# Intentar importar libsql para Turso (producción)
try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

# Ruta de la base de datos local (réplica o desarrollo)
DB_PATH = Path(__file__).parent / "data" / "logisplan.db"

# Credenciales Turso (desde secrets de Streamlit o env vars)
TURSO_URL = None
TURSO_TOKEN = None

try:
    import streamlit as st
    TURSO_URL = st.secrets.get("TURSO_DATABASE_URL")
    TURSO_TOKEN = st.secrets.get("TURSO_AUTH_TOKEN")
except Exception:
    pass

if not TURSO_URL:
    TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
    TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")


def get_connection() -> Union[sqlite3.Connection, "libsql.Connection"]:
    """
    Obtiene conexión a la base de datos.

    Modo producción (Turso): Si hay credenciales Turso + libsql disponible,
    usa conexión remota con réplica local para velocidad.

    Modo desarrollo: SQLite local estándar.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if HAS_LIBSQL and TURSO_URL and TURSO_TOKEN:
        # Modo producción: Turso con embedded replica
        conn = libsql.connect(
            str(DB_PATH),           # Réplica local para velocidad
            sync_url=TURSO_URL,     # Sync con Turso remoto
            auth_token=TURSO_TOKEN
        )
        conn.sync()  # Sincronizar con el servidor al conectar
        return conn
    else:
        # Modo desarrollo: SQLite local
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def _sync_if_turso(conn):
    """Sincroniza con Turso si estamos en modo remoto."""
    if hasattr(conn, 'sync'):
        conn.sync()


def init_database():
    """Inicializa las tablas de la base de datos."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de vehículos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id TEXT PRIMARY KEY,
            descripcion TEXT NOT NULL,
            amortizacion_mensual REAL DEFAULT 0
        )
    """)

    # Tabla de categorías
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            tipo TEXT DEFAULT 'GASTO',  -- GASTO o INGRESO
            asignacion_tipica TEXT DEFAULT 'MANUAL'
        )
    """)

    # Tabla de movimientos bancarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            descripcion TEXT NOT NULL,
            importe REAL NOT NULL,
            categoria_id TEXT,
            vehiculo_id TEXT,
            referencia TEXT,
            importacion_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id),
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
        )
    """)

    # Tabla de reglas de auto-categorización
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reglas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patron TEXT NOT NULL UNIQUE,
            categoria_id TEXT NOT NULL,
            vehiculo_id TEXT,
            activa INTEGER DEFAULT 1,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id),
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
        )
    """)

    # Tabla de importaciones (para tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_importacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            archivo_nombre TEXT,
            num_movimientos INTEGER,
            periodo_desde DATE,
            periodo_hasta DATE
        )
    """)

    # Migración: añadir columnas nuevas a importaciones
    for col_sql in [
        "ALTER TABLE importaciones ADD COLUMN tipo TEXT",
        "ALTER TABLE importaciones ADD COLUMN hash_archivo TEXT",
        "ALTER TABLE importaciones ADD COLUMN mes_referencia TEXT",
    ]:
        try:
            cursor.execute(col_sql)
        except Exception:
            pass  # La columna ya existe

    # Tabla de checklist de documentos mensuales
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            tipo_documento TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            notas TEXT,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(mes, tipo_documento)
        )
    """)

    # Tabla de exclusiones para importación bancaria
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exclusiones_banco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patron TEXT NOT NULL UNIQUE,
            categoria_id TEXT NOT NULL,
            motivo TEXT,
            activa INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    """)

    # Log de movimientos excluidos (auditoría)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_excluidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            descripcion TEXT NOT NULL,
            importe REAL NOT NULL,
            patron_exclusion TEXT NOT NULL,
            motivo TEXT,
            importacion_id INTEGER,
            mes_referencia TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla de amortizaciones por activo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS amortizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activo TEXT NOT NULL,
            matricula TEXT,
            vehiculo_id TEXT,
            amortizacion_anual REAL NOT NULL,
            amortizacion_mensual REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
        )
    """)

    # Tabla de costes laborales
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS costes_laborales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            trabajador_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            vehiculo_id TEXT,
            bruto REAL DEFAULT 0,
            ss_trabajador REAL DEFAULT 0,
            irpf REAL DEFAULT 0,
            liquido REAL DEFAULT 0,
            ss_empresa REAL DEFAULT 0,
            coste_total REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
            UNIQUE(mes, trabajador_id)
        )
    """)

    # Tabla de facturación
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            vehiculo_id TEXT NOT NULL,
            importe REAL NOT NULL,
            descripcion TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
            UNIQUE(mes, vehiculo_id)
        )
    """)

    # Tabla de hojas de ruta (kilómetros por vehículo/zona)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hojas_ruta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            vehiculo_id TEXT NOT NULL,
            zona TEXT NOT NULL,
            viajes INTEGER DEFAULT 0,
            repartos INTEGER DEFAULT 0,
            km REAL DEFAULT 0,
            media_repartos_viaje REAL,
            dias_trabajados INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
            UNIQUE(mes, vehiculo_id, zona)
        )
    """)

    # Índice único compuesto para evitar duplicados en movimientos
    # Si hay duplicados existentes, NO borrar datos — solo omitir el índice.
    # El usuario puede limpiar duplicados manualmente desde Configuración.
    # INSERT OR IGNORE funciona igualmente gracias al índice cuando se pueda crear.
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movimientos_unique
            ON movimientos(fecha, descripcion, importe)
        """)
    except (sqlite3.IntegrityError, Exception):
        # Hay duplicados existentes, no se puede crear el índice aún.
        # No borrar datos automáticamente para evitar pérdida de información.
        pass

    # Índices para mejorar rendimiento
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_vehiculo ON movimientos(vehiculo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_categoria ON movimientos(categoria_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_costes_laborales_mes ON costes_laborales(mes)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_costes_laborales_vehiculo ON costes_laborales(vehiculo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_importaciones_mes_tipo ON importaciones(mes_referencia, tipo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hojas_ruta_mes ON hojas_ruta(mes, vehiculo_id)")

    conn.commit()
    _sync_if_turso(conn)

    # Insertar datos iniciales
    _insertar_datos_iniciales(conn)

    _sync_if_turso(conn)
    conn.close()


def _insertar_datos_iniciales(conn):
    """Inserta vehículos, categorías y reglas iniciales."""
    cursor = conn.cursor()

    # Vehículos
    vehiculos = [
        ("MTY", "Camión MTY", 2000.0),
        ("LVX", "Camión LVX", 2584.0),
        ("MJC", "Camión MJC", 1500.0),
        ("MLB", "Camión MLB", 1000.0),
        ("COMÚN", "Gastos comunes", 0.0),
    ]

    for v in vehiculos:
        cursor.execute("""
            INSERT OR IGNORE INTO vehiculos (id, descripcion, amortizacion_mensual)
            VALUES (?, ?, ?)
        """, v)

    # Categorías
    categorias = [
        ("SAL", "Salarios", "GASTO", "VEHICULO"),
        ("SS", "Seguridad Social", "GASTO", "COMÚN"),
        ("COMB", "Combustible", "GASTO", "VEHICULO"),
        ("TALL", "Talleres", "GASTO", "VEHICULO"),
        ("PEAJ", "Peajes", "GASTO", "VEHICULO"),
        ("DIET", "Dietas", "GASTO", "VEHICULO"),
        ("NEUM", "Neumáticos", "GASTO", "VEHICULO"),
        ("LEAS", "Leasing", "GASTO", "LVX"),
        ("FIN", "Financiación", "GASTO", "VEHICULO"),
        ("SEG", "Seguros", "GASTO", "COMÚN"),
        ("TEL", "Telecomunicaciones", "GASTO", "COMÚN"),
        ("ELEC", "Electricidad", "GASTO", "COMÚN"),
        ("ADM", "Administración", "GASTO", "COMÚN"),
        ("ASOC", "Asociaciones", "GASTO", "COMÚN"),
        ("IMP", "Impuestos", "GASTO", "COMÚN"),
        ("VISA", "Tarjeta VISA", "GASTO", "MLB"),
        ("SOCIO", "Gastos socio", "GASTO", "COMÚN"),
        ("OTRO", "Otros", "GASTO", "MANUAL"),
        ("INGRESO", "Ingresos", "INGRESO", "VEHICULO"),
    ]

    for c in categorias:
        cursor.execute("""
            INSERT OR IGNORE INTO categorias (id, nombre, tipo, asignacion_tipica)
            VALUES (?, ?, ?, ?)
        """, c)

    # Reglas de auto-categorización
    reglas = [
        # Combustible
        ("SOLRED", "COMB", None),
        ("STAROIL", "COMB", None),
        ("VALCARCE", "COMB", None),
        ("COMBUSTIBLE", "COMB", None),
        # Devolución gasoil
        ("GASOLEO PROFESIONAL", "INGRESO", "COMÚN"),
        # Seguridad Social
        ("TGSS", "SS", "COMÚN"),
        ("COTIZACION", "SS", "COMÚN"),
        # Leasing/Financiación
        ("LEAS:", "LEAS", "LVX"),
        ("TRANSOLVER", "FIN", None),
        # Impuestos
        ("IMP:", "IMP", "COMÚN"),
        ("IMP ", "IMP", "COMÚN"),
        ("IMPUESTO", "IMP", "COMÚN"),
        ("NRC:", "IMP", "COMÚN"),
        ("AEAT", "IMP", "COMÚN"),
        # Telecomunicaciones
        ("TELEFONICA", "TEL", "COMÚN"),
        ("VODAFONE", "TEL", "COMÚN"),
        # Electricidad
        ("IBERDROLA", "ELEC", "COMÚN"),
        ("ELECTRICIDAD", "ELEC", "COMÚN"),
        ("CURENERG", "ELEC", "COMÚN"),
        # Administración
        ("ADM FRANCHISING", "ADM", "COMÚN"),
        ("FRANCHISING", "ADM", "COMÚN"),
        # Asociaciones
        ("ASOCIACION", "ASOC", "COMÚN"),
        ("APETAMCOR", "ASOC", "COMÚN"),
        # Neumáticos
        ("NEUMATICO", "NEUM", None),
        ("RODAS", "NEUM", None),
        # Talleres
        ("IVECO", "TALL", None),
        # Seguros
        ("SVRNE", "SEG", "COMÚN"),
        # VISA
        ("TARJETA VISA", "VISA", "MLB"),
        ("AMORTIZACION DEUDA", "VISA", "MLB"),
        # Gastos socio
        ("GASTOS SEVE", "SOCIO", "COMÚN"),
        # Clientes principales
        ("NUTRIMENTOS", "INGRESO", None),
        ("WARBURTON", "INGRESO", "MLB"),
    ]

    for r in reglas:
        cursor.execute("""
            INSERT OR IGNORE INTO reglas (patron, categoria_id, vehiculo_id)
            VALUES (?, ?, ?)
        """, r)

    # Exclusiones bancarias por defecto
    exclusiones = [
        ("TGSS", "SS", "Se importa desde archivo Seguridad Social"),
        ("COTIZACION", "SS", "Se importa desde archivo Seguridad Social"),
        ("SOLRED", "COMB", "Se importa desde factura Solred"),
        ("STAROIL", "COMB", "Se importa desde factura Staroil"),
        ("VALCARCE", "PEAJ", "Se importa desde factura Valcarce"),
        ("DOCUMENTO", "SAL", "Se importa desde costes laborales (salarios)"),
    ]
    for e in exclusiones:
        cursor.execute("""
            INSERT OR IGNORE INTO exclusiones_banco (patron, categoria_id, motivo)
            VALUES (?, ?, ?)
        """, e)

    conn.commit()


# ============== FUNCIONES DE CONSULTA ==============

def get_vehiculos() -> pd.DataFrame:
    """Obtiene todos los vehículos."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM vehiculos", conn)
    conn.close()
    return df


def get_vehiculos_operativos() -> pd.DataFrame:
    """Obtiene vehículos operativos (sin COMÚN)."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM vehiculos WHERE id != 'COMÚN'", conn
    )
    conn.close()
    return df


def get_categorias() -> pd.DataFrame:
    """Obtiene todas las categorías."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM categorias", conn)
    conn.close()
    return df


def get_reglas() -> pd.DataFrame:
    """Obtiene todas las reglas de categorización."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT r.*, c.nombre as categoria_nombre
        FROM reglas r
        LEFT JOIN categorias c ON r.categoria_id = c.id
        WHERE r.activa = 1
        ORDER BY r.patron
    """, conn)
    conn.close()
    return df


def get_movimientos(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    vehiculo_id: Optional[str] = None,
    categoria_id: Optional[str] = None
) -> pd.DataFrame:
    """Obtiene movimientos con filtros opcionales."""
    conn = get_connection()

    query = """
        SELECT
            m.*,
            c.nombre as categoria_nombre,
            c.tipo as categoria_tipo,
            v.descripcion as vehiculo_descripcion
        FROM movimientos m
        LEFT JOIN categorias c ON m.categoria_id = c.id
        LEFT JOIN vehiculos v ON m.vehiculo_id = v.id
        WHERE 1=1
    """
    params = []

    if fecha_desde:
        query += " AND m.fecha >= ?"
        params.append(fecha_desde)

    if fecha_hasta:
        query += " AND m.fecha <= ?"
        params.append(fecha_hasta)

    if vehiculo_id:
        query += " AND m.vehiculo_id = ?"
        params.append(vehiculo_id)

    if categoria_id:
        query += " AND m.categoria_id = ?"
        params.append(categoria_id)

    query += " ORDER BY m.fecha DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_periodos_disponibles() -> list:
    """Obtiene lista de periodos (año-mes) con movimientos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT strftime('%Y-%m', fecha) as periodo
        FROM movimientos
        ORDER BY periodo DESC
    """)
    periodos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return periodos


# ============== FUNCIONES DE INSERCIÓN ==============

def insertar_movimientos(movimientos: list[dict], archivo_nombre: str = None,
                         tipo: str = None, hash_archivo: str = None,
                         mes_referencia: str = None) -> dict:
    """
    Inserta múltiples movimientos en la base de datos.
    Usa INSERT OR IGNORE para evitar duplicados (basado en fecha+descripcion+importe).
    Retorna dict con: importacion_id, insertados, duplicados.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Crear registro de importación
    fechas = [m['fecha'] for m in movimientos if m.get('fecha')]
    periodo_desde = min(fechas) if fechas else None
    periodo_hasta = max(fechas) if fechas else None

    cursor.execute("""
        INSERT INTO importaciones (archivo_nombre, num_movimientos, periodo_desde, periodo_hasta,
                                   tipo, hash_archivo, mes_referencia)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (archivo_nombre, len(movimientos), periodo_desde, periodo_hasta,
          tipo, hash_archivo, mes_referencia))

    importacion_id = cursor.lastrowid

    # Verificar si el índice único existe (puede no existir si había duplicados previos)
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='idx_movimientos_unique'")
    tiene_indice = cursor.fetchone()[0] > 0

    # Insertar movimientos evitando duplicados
    insertados = 0
    duplicados = 0
    for mov in movimientos:
        fecha = mov.get('fecha')
        descripcion = mov.get('descripcion')
        importe = mov.get('importe')

        # Si no hay índice único, verificar manualmente si ya existe
        if not tiene_indice:
            cursor.execute("""
                SELECT COUNT(*) FROM movimientos
                WHERE fecha = ? AND descripcion = ? AND importe = ?
            """, (fecha, descripcion, importe))
            if cursor.fetchone()[0] > 0:
                duplicados += 1
                continue

        cursor.execute("""
            INSERT OR IGNORE INTO movimientos
            (fecha, descripcion, importe, categoria_id, vehiculo_id, referencia, importacion_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha, descripcion, importe,
            mov.get('categoria_id'),
            mov.get('vehiculo_id'),
            mov.get('referencia'),
            importacion_id
        ))
        if cursor.rowcount > 0:
            insertados += 1
        else:
            duplicados += 1

    conn.commit()
    _sync_if_turso(conn)
    conn.close()

    return {'importacion_id': importacion_id, 'insertados': insertados, 'duplicados': duplicados}


def limpiar_duplicados_existentes() -> int:
    """
    Elimina movimientos duplicados existentes, conservando el de menor ID.
    Después intenta crear el UNIQUE INDEX si no existía.
    Retorna el número de duplicados eliminados.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM movimientos
        WHERE id NOT IN (
            SELECT MIN(id) FROM movimientos
            GROUP BY fecha, descripcion, importe
        )
    """)
    eliminados = cursor.rowcount

    # Intentar crear el índice único ahora que no hay duplicados
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movimientos_unique
            ON movimientos(fecha, descripcion, importe)
        """)
    except (sqlite3.IntegrityError, Exception):
        pass  # Todavía hay conflictos, no pasa nada

    conn.commit()
    _sync_if_turso(conn)
    conn.close()
    return eliminados


def actualizar_movimiento(id: int, categoria_id: str, vehiculo_id: str):
    """Actualiza categoría y vehículo de un movimiento."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE movimientos
        SET categoria_id = ?, vehiculo_id = ?
        WHERE id = ?
    """, (categoria_id, vehiculo_id, id))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def eliminar_importacion(importacion_id: int):
    """Elimina una importación y sus movimientos asociados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimientos WHERE importacion_id = ?", (importacion_id,))
    cursor.execute("DELETE FROM importaciones WHERE id = ?", (importacion_id,))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


# ============== FUNCIONES DE CONFIGURACIÓN ==============

def actualizar_amortizacion(vehiculo_id: str, amortizacion: float):
    """Actualiza la amortización mensual de un vehículo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE vehiculos
        SET amortizacion_mensual = ?
        WHERE id = ?
    """, (amortizacion, vehiculo_id))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def agregar_regla(patron: str, categoria_id: str, vehiculo_id: Optional[str] = None):
    """Agrega una nueva regla de categorización."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO reglas (patron, categoria_id, vehiculo_id, activa)
        VALUES (?, ?, ?, 1)
    """, (patron, categoria_id, vehiculo_id))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def eliminar_regla(regla_id: int):
    """Desactiva una regla de categorización."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reglas SET activa = 0 WHERE id = ?", (regla_id,))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


# ============== FUNCIONES DE AMORTIZACIONES ==============

def get_amortizaciones() -> pd.DataFrame:
    """Obtiene todas las amortizaciones."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT a.*, v.descripcion as vehiculo_descripcion
        FROM amortizaciones a
        LEFT JOIN vehiculos v ON a.vehiculo_id = v.id
        ORDER BY a.activo
    """, conn)
    conn.close()
    return df


def guardar_amortizaciones(amortizaciones: list[dict]):
    """Guarda o actualiza las amortizaciones."""
    conn = get_connection()
    cursor = conn.cursor()

    # Limpiar tabla existente
    cursor.execute("DELETE FROM amortizaciones")

    # Insertar nuevas amortizaciones
    for a in amortizaciones:
        cursor.execute("""
            INSERT INTO amortizaciones (activo, matricula, vehiculo_id, amortizacion_anual, amortizacion_mensual)
            VALUES (?, ?, ?, ?, ?)
        """, (
            a.get('activo'),
            a.get('matricula'),
            a.get('vehiculo_id'),
            a.get('amortizacion_anual'),
            a.get('amortizacion_mensual')
        ))

    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def inicializar_amortizaciones_default():
    """Inicializa amortizaciones con valores por defecto si la tabla está vacía."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM amortizaciones")
    count = cursor.fetchone()[0]

    if count == 0:
        amortizaciones_default = [
            ("CAMIÓN IVECO", "1257MTY", "MTY", 17600, 1466.67),
            ("CAMIÓN RENAULT", "1382LVX", "LVX", 19600, 1633.33),
            ("CISTERNA LVX", "1382LVX", "LVX", 6320, 526.67),
            ("CAMIÓN RENAULT T460", "9245MJC", "MJC", 9360, 780.00),
            ("SEMIRREMOLQUE", "R8985BDN", "COMÚN", 4865, 405.42),
            ("COCHE MERCEDES", "5014LRH", "COMÚN", 4627, 385.58),
            ("CARRETILLA", "-", "COMÚN", 180, 15.00),
        ]

        for a in amortizaciones_default:
            cursor.execute("""
                INSERT INTO amortizaciones (activo, matricula, vehiculo_id, amortizacion_anual, amortizacion_mensual)
                VALUES (?, ?, ?, ?, ?)
            """, a)

        conn.commit()
        _sync_if_turso(conn)

    conn.close()


# ============== FUNCIONES DE COSTES LABORALES ==============

def get_costes_laborales(mes: Optional[str] = None, vehiculo_id: Optional[str] = None) -> pd.DataFrame:
    """Obtiene costes laborales con filtros opcionales."""
    conn = get_connection()

    query = """
        SELECT cl.*, v.descripcion as vehiculo_descripcion
        FROM costes_laborales cl
        LEFT JOIN vehiculos v ON cl.vehiculo_id = v.id
        WHERE 1=1
    """
    params = []

    if mes:
        query += " AND cl.mes = ?"
        params.append(mes)

    if vehiculo_id:
        query += " AND cl.vehiculo_id = ?"
        params.append(vehiculo_id)

    query += " ORDER BY cl.mes DESC, cl.trabajador_id"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def insertar_coste_laboral(coste: dict) -> int:
    """Inserta o actualiza un coste laboral."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO costes_laborales
        (mes, trabajador_id, nombre, vehiculo_id, bruto, ss_trabajador, irpf, liquido, ss_empresa, coste_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        coste.get('mes'),
        coste.get('trabajador_id'),
        coste.get('nombre'),
        coste.get('vehiculo_id'),
        coste.get('bruto', 0),
        coste.get('ss_trabajador', 0),
        coste.get('irpf', 0),
        coste.get('liquido', 0),
        coste.get('ss_empresa', 0),
        coste.get('coste_total', 0)
    ))

    coste_id = cursor.lastrowid
    conn.commit()
    _sync_if_turso(conn)
    conn.close()

    return coste_id


def insertar_costes_laborales_batch(costes: list[dict]) -> int:
    """Inserta múltiples costes laborales."""
    conn = get_connection()
    cursor = conn.cursor()

    for coste in costes:
        cursor.execute("""
            INSERT OR REPLACE INTO costes_laborales
            (mes, trabajador_id, nombre, vehiculo_id, bruto, ss_trabajador, irpf, liquido, ss_empresa, coste_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            coste.get('mes'),
            coste.get('trabajador_id'),
            coste.get('nombre'),
            coste.get('vehiculo_id'),
            coste.get('bruto', 0),
            coste.get('ss_trabajador', 0),
            coste.get('irpf', 0),
            coste.get('liquido', 0),
            coste.get('ss_empresa', 0),
            coste.get('coste_total', 0)
        ))

    conn.commit()
    _sync_if_turso(conn)
    conn.close()

    return len(costes)


def get_resumen_costes_por_vehiculo() -> pd.DataFrame:
    """Obtiene resumen de costes laborales agrupados por mes y vehículo."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            mes,
            vehiculo_id,
            SUM(coste_total) as total_coste
        FROM costes_laborales
        GROUP BY mes, vehiculo_id
        ORDER BY mes DESC, vehiculo_id
    """, conn)
    conn.close()
    return df


def eliminar_coste_laboral(coste_id: int):
    """Elimina un coste laboral."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM costes_laborales WHERE id = ?", (coste_id,))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


# ============== FUNCIONES DE BORRADO DE MOVIMIENTOS ==============

def eliminar_movimientos(ids: list[int]) -> int:
    """Elimina múltiples movimientos por sus IDs."""
    if not ids:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(ids))
    cursor.execute(f"DELETE FROM movimientos WHERE id IN ({placeholders})", ids)

    deleted = cursor.rowcount
    conn.commit()
    _sync_if_turso(conn)
    conn.close()

    return deleted


def get_movimientos_con_filtros(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    vehiculos: Optional[list[str]] = None,
    categorias: Optional[list[str]] = None,
    tipo: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[pd.DataFrame, int]:
    """
    Obtiene movimientos con filtros avanzados y paginación.
    Retorna (DataFrame, total_count).
    """
    conn = get_connection()

    # Query base
    where_clauses = ["1=1"]
    params = []

    if fecha_desde:
        where_clauses.append("m.fecha >= ?")
        params.append(fecha_desde)

    if fecha_hasta:
        where_clauses.append("m.fecha <= ?")
        params.append(fecha_hasta)

    if vehiculos and len(vehiculos) > 0:
        placeholders = ','.join('?' * len(vehiculos))
        where_clauses.append(f"m.vehiculo_id IN ({placeholders})")
        params.extend(vehiculos)

    if categorias and len(categorias) > 0:
        placeholders = ','.join('?' * len(categorias))
        where_clauses.append(f"m.categoria_id IN ({placeholders})")
        params.extend(categorias)

    if tipo == 'Ingresos':
        where_clauses.append("m.importe > 0")
    elif tipo == 'Gastos':
        where_clauses.append("m.importe < 0")

    where_sql = " AND ".join(where_clauses)

    # Contar total
    count_query = f"""
        SELECT COUNT(*) FROM movimientos m
        LEFT JOIN categorias c ON m.categoria_id = c.id
        WHERE {where_sql}
    """
    cursor = conn.cursor()
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # Obtener datos paginados
    data_query = f"""
        SELECT
            m.id,
            m.fecha,
            m.descripcion,
            m.importe,
            m.categoria_id,
            c.nombre as categoria_nombre,
            m.vehiculo_id,
            v.descripcion as vehiculo_descripcion
        FROM movimientos m
        LEFT JOIN categorias c ON m.categoria_id = c.id
        LEFT JOIN vehiculos v ON m.vehiculo_id = v.id
        WHERE {where_sql}
        ORDER BY m.fecha DESC, m.id DESC
        LIMIT ? OFFSET ?
    """

    df = pd.read_sql_query(data_query, conn, params=params + [limit, offset])
    conn.close()

    return df, total_count


# ============== FUNCIONES DE FACTURACIÓN ==============

def get_facturacion(mes: Optional[str] = None, vehiculo_id: Optional[str] = None) -> pd.DataFrame:
    """Obtiene facturación con filtros opcionales."""
    conn = get_connection()

    query = """
        SELECT f.*, v.descripcion as vehiculo_descripcion
        FROM facturacion f
        LEFT JOIN vehiculos v ON f.vehiculo_id = v.id
        WHERE 1=1
    """
    params = []

    if mes:
        query += " AND f.mes = ?"
        params.append(mes)

    if vehiculo_id:
        query += " AND f.vehiculo_id = ?"
        params.append(vehiculo_id)

    query += " ORDER BY f.mes DESC, f.vehiculo_id"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def insertar_facturacion(factura: dict) -> int:
    """Inserta o actualiza una facturación."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO facturacion
        (mes, vehiculo_id, importe, descripcion)
        VALUES (?, ?, ?, ?)
    """, (
        factura.get('mes'),
        factura.get('vehiculo_id'),
        factura.get('importe', 0),
        factura.get('descripcion')
    ))

    factura_id = cursor.lastrowid
    conn.commit()
    _sync_if_turso(conn)
    conn.close()

    return factura_id


def eliminar_facturacion(factura_id: int):
    """Elimina una facturación."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM facturacion WHERE id = ?", (factura_id,))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def get_resumen_facturacion_por_vehiculo() -> pd.DataFrame:
    """Obtiene resumen de facturación agrupado por mes y vehículo."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            mes,
            vehiculo_id,
            SUM(importe) as total_facturacion
        FROM facturacion
        GROUP BY mes, vehiculo_id
        ORDER BY mes DESC, vehiculo_id
    """, conn)
    conn.close()
    return df


# ============== FUNCIONES PARA IMPORTAR TODO ==============

def insertar_importacion_tipada(archivo_nombre, num_movimientos, periodo_desde,
                                 periodo_hasta, tipo, hash_archivo, mes_referencia):
    """Inserta un registro de importación con tipo y hash (sin movimientos asociados)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO importaciones
        (archivo_nombre, num_movimientos, periodo_desde, periodo_hasta, tipo, hash_archivo, mes_referencia)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (archivo_nombre, num_movimientos, periodo_desde, periodo_hasta,
          tipo, hash_archivo, mes_referencia))
    importacion_id = cursor.lastrowid
    conn.commit()
    _sync_if_turso(conn)
    conn.close()
    return importacion_id


def verificar_hash_duplicado(hash_archivo):
    """Comprueba si un archivo con este hash ya fue importado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, archivo_nombre, fecha_importacion FROM importaciones WHERE hash_archivo = ?",
        (hash_archivo,)
    )
    resultado = cursor.fetchone()
    conn.close()
    if resultado is None:
        return None
    # Compatibilidad libsql (tupla) y sqlite3 (Row)
    if hasattr(resultado, 'keys'):
        return dict(resultado)
    return {'id': resultado[0], 'archivo_nombre': resultado[1], 'fecha_importacion': resultado[2]}


def verificar_nombre_duplicado(archivo_nombre):
    """Comprueba si un archivo con este nombre ya fue importado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, archivo_nombre, fecha_importacion FROM importaciones WHERE archivo_nombre = ?",
        (archivo_nombre,)
    )
    resultado = cursor.fetchone()
    conn.close()
    if resultado is None:
        return None
    # Compatibilidad libsql (tupla) y sqlite3 (Row)
    if hasattr(resultado, 'keys'):
        return dict(resultado)
    return {'id': resultado[0], 'archivo_nombre': resultado[1], 'fecha_importacion': resultado[2]}


def get_importaciones_por_mes(mes_referencia):
    """Obtiene todas las importaciones de un mes específico."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM importaciones
        WHERE mes_referencia = ?
        ORDER BY fecha_importacion DESC
    """, conn, params=[mes_referencia])
    conn.close()
    return df


def get_checklist_estado(mes):
    """Obtiene el estado del checklist manual para un mes."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM checklist_documentos
        WHERE mes = ?
    """, conn, params=[mes])
    conn.close()
    return df


def upsert_checklist_documento(mes, tipo_documento, estado, notas=None):
    """Inserta o actualiza el estado de un documento en el checklist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO checklist_documentos (mes, tipo_documento, estado, notas)
        VALUES (?, ?, ?, ?)
    """, (mes, tipo_documento, estado, notas))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


# ============== FUNCIONES PARA EXCLUSIONES BANCARIAS ==============

def get_exclusiones_banco() -> pd.DataFrame:
    """Obtiene todas las exclusiones bancarias (activas e inactivas)."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT e.*, c.nombre as categoria_nombre
        FROM exclusiones_banco e
        LEFT JOIN categorias c ON e.categoria_id = c.id
        ORDER BY e.patron
    """, conn)
    conn.close()
    return df


def guardar_exclusion_banco(patron, categoria_id, motivo, activa=1):
    """Inserta o actualiza una regla de exclusion bancaria."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO exclusiones_banco (patron, categoria_id, motivo, activa)
        VALUES (?, ?, ?, ?)
    """, (patron.strip().upper(), categoria_id, motivo, activa))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def eliminar_exclusion_banco(exclusion_id):
    """Elimina una regla de exclusion bancaria."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exclusiones_banco WHERE id = ?", (exclusion_id,))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def toggle_exclusion_banco(exclusion_id, activa):
    """Activa o desactiva una regla de exclusion bancaria."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exclusiones_banco SET activa = ? WHERE id = ?", (1 if activa else 0, exclusion_id))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def insertar_movimientos_excluidos(excluidos: list, importacion_id=None, mes_referencia=None):
    """Registra movimientos excluidos en el log de auditoria."""
    if not excluidos:
        return
    conn = get_connection()
    cursor = conn.cursor()
    for exc in excluidos:
        cursor.execute("""
            INSERT INTO movimientos_excluidos
            (fecha, descripcion, importe, patron_exclusion, motivo, importacion_id, mes_referencia)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            exc.get('fecha'),
            exc.get('descripcion'),
            exc.get('importe'),
            exc.get('patron_exclusion'),
            exc.get('motivo'),
            importacion_id,
            mes_referencia or exc.get('mes_referencia'),
        ))
    conn.commit()
    _sync_if_turso(conn)
    conn.close()


def get_movimientos_excluidos(mes_referencia=None) -> pd.DataFrame:
    """Obtiene movimientos excluidos con filtro opcional por mes."""
    conn = get_connection()
    if mes_referencia:
        df = pd.read_sql_query("""
            SELECT * FROM movimientos_excluidos
            WHERE mes_referencia = ?
            ORDER BY fecha DESC
        """, conn, params=[mes_referencia])
    else:
        df = pd.read_sql_query("""
            SELECT * FROM movimientos_excluidos
            ORDER BY created_at DESC
        """, conn)
    conn.close()
    return df


# ============== FUNCIONES PARA HOJAS DE RUTA ==============

def insertar_hoja_ruta(datos: dict) -> int:
    """
    Inserta datos de una hoja de ruta (zonas + totales).
    datos = {'mes', 'vehiculo_id', 'zonas': [...], 'total_viajes', 'total_km', ...}
    """
    conn = get_connection()
    cursor = conn.cursor()

    mes = datos['mes']
    vehiculo_id = datos['vehiculo_id']
    media = datos.get('media_repartos_viaje', 0)
    dias = datos.get('dias_trabajados', 0)

    # Insertar cada zona
    for zona in datos.get('zonas', []):
        cursor.execute("""
            INSERT OR REPLACE INTO hojas_ruta
            (mes, vehiculo_id, zona, viajes, repartos, km, media_repartos_viaje, dias_trabajados)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mes, vehiculo_id, zona['zona'],
            zona.get('viajes', 0),
            zona.get('repartos', 0),
            zona.get('km', 0),
            media, dias
        ))

    # Insertar fila TOTAL con los totales generales
    cursor.execute("""
        INSERT OR REPLACE INTO hojas_ruta
        (mes, vehiculo_id, zona, viajes, repartos, km, media_repartos_viaje, dias_trabajados)
        VALUES (?, ?, 'TOTAL', ?, ?, ?, ?, ?)
    """, (
        mes, vehiculo_id,
        datos.get('total_viajes', 0),
        datos.get('total_repartos', 0),
        datos.get('total_km', 0),
        media, dias
    ))

    conn.commit()
    _sync_if_turso(conn)
    num = cursor.lastrowid
    conn.close()
    return num


def get_hojas_ruta(mes=None, vehiculo_id=None) -> pd.DataFrame:
    """Obtiene hojas de ruta con filtros opcionales."""
    conn = get_connection()
    query = "SELECT * FROM hojas_ruta WHERE 1=1"
    params = []

    if mes:
        query += " AND mes = ?"
        params.append(mes)
    if vehiculo_id:
        query += " AND vehiculo_id = ?"
        params.append(vehiculo_id)

    query += " ORDER BY mes DESC, vehiculo_id, zona"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_km_por_vehiculo_mes(vehiculo_id: str, mes: str) -> float:
    """Obtiene el total de km de un vehículo en un mes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT km FROM hojas_ruta
        WHERE vehiculo_id = ? AND mes = ? AND zona = 'TOTAL'
    """, (vehiculo_id, mes))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return 0.0
    # Compatibilidad libsql (tupla) y sqlite3 (Row)
    km_value = row['km'] if hasattr(row, 'keys') else row[0]
    return float(km_value)


def get_km_totales_vehiculo(vehiculo_id: str) -> pd.DataFrame:
    """Obtiene km mensuales de un vehículo (solo filas TOTAL)."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT mes, km, viajes, repartos, dias_trabajados, media_repartos_viaje
        FROM hojas_ruta
        WHERE vehiculo_id = ? AND zona = 'TOTAL'
        ORDER BY mes
    """, conn, params=[vehiculo_id])
    conn.close()
    return df


# Inicializar base de datos al importar el módulo
if __name__ == "__main__":
    init_database()
    print(f"Base de datos inicializada en: {DB_PATH}")
