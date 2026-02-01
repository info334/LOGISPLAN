"""
LogisPLAN - Módulo de Base de Datos
Gestión de tablas SQLite para flota de transporte Severino Logística
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd

# Ruta de la base de datos
DB_PATH = Path(__file__).parent / "data" / "logisplan.db"


def get_connection() -> sqlite3.Connection:
    """Obtiene conexión a la base de datos SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


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

    # Índices para mejorar rendimiento
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_vehiculo ON movimientos(vehiculo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_categoria ON movimientos(categoria_id)")

    conn.commit()

    # Insertar datos iniciales
    _insertar_datos_iniciales(conn)

    conn.close()


def _insertar_datos_iniciales(conn: sqlite3.Connection):
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
        ("NRC:", "IMP", "COMÚN"),
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

def insertar_movimientos(movimientos: list[dict], archivo_nombre: str = None) -> int:
    """
    Inserta múltiples movimientos en la base de datos.
    Retorna el ID de la importación.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Crear registro de importación
    fechas = [m['fecha'] for m in movimientos if m.get('fecha')]
    periodo_desde = min(fechas) if fechas else None
    periodo_hasta = max(fechas) if fechas else None

    cursor.execute("""
        INSERT INTO importaciones (archivo_nombre, num_movimientos, periodo_desde, periodo_hasta)
        VALUES (?, ?, ?, ?)
    """, (archivo_nombre, len(movimientos), periodo_desde, periodo_hasta))

    importacion_id = cursor.lastrowid

    # Insertar movimientos
    for mov in movimientos:
        cursor.execute("""
            INSERT INTO movimientos (fecha, descripcion, importe, categoria_id, vehiculo_id, referencia, importacion_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            mov.get('fecha'),
            mov.get('descripcion'),
            mov.get('importe'),
            mov.get('categoria_id'),
            mov.get('vehiculo_id'),
            mov.get('referencia'),
            importacion_id
        ))

    conn.commit()
    conn.close()

    return importacion_id


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
    conn.close()


def eliminar_importacion(importacion_id: int):
    """Elimina una importación y sus movimientos asociados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimientos WHERE importacion_id = ?", (importacion_id,))
    cursor.execute("DELETE FROM importaciones WHERE id = ?", (importacion_id,))
    conn.commit()
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
    conn.close()


def eliminar_regla(regla_id: int):
    """Desactiva una regla de categorización."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reglas SET activa = 0 WHERE id = ?", (regla_id,))
    conn.commit()
    conn.close()


# Inicializar base de datos al importar el módulo
if __name__ == "__main__":
    init_database()
    print(f"Base de datos inicializada en: {DB_PATH}")
