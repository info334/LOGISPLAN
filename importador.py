"""
LogisPLAN - Módulo de Importación CSV
Parseo de extractos bancarios Abanca y auto-categorización
"""

import pandas as pd
from io import StringIO
from datetime import datetime
from typing import Optional, Union
import unicodedata

from database import get_reglas, get_connection


def _normalizar_texto(texto: str) -> str:
    """Quita tildes y normaliza texto para comparación."""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.upper().strip()


def parsear_csv_abanca(contenido: Union[bytes, str], nombre_archivo: str = None) -> pd.DataFrame:
    """
    Parsea un CSV de extracto bancario de Abanca.
    """
    # Decodificar si es bytes
    if isinstance(contenido, bytes):
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
            try:
                texto = contenido.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("No se pudo decodificar el archivo CSV")
    else:
        texto = contenido

    # Detectar línea de encabezados (buscar "F. VALOR" o similar)
    lineas = texto.split('\n')
    skiprows = 0
    for i, linea in enumerate(lineas):
        linea_upper = linea.upper()
        if 'F. VALOR' in linea_upper or ('FECHA' in linea_upper and 'IMPORTE' in linea_upper):
            skiprows = i
            break

    # Leer CSV con separador punto y coma
    try:
        df = pd.read_csv(
            StringIO(texto),
            sep=';',
            decimal=',',
            thousands='.',
            encoding='utf-8',
            dtype=str,
            skiprows=skiprows
        )
    except Exception as e:
        raise ValueError(f"Error al parsear CSV: {e}")

    # Normalizar nombres de columnas (quitar tildes, espacios, mayúsculas)
    df.columns = [_normalizar_texto(str(col)) for col in df.columns]

    # Mapear columnas esperadas (sin tildes para comparación)
    columnas_mapeo = {
        'F. VALOR': 'fecha',
        'F.VALOR': 'fecha',
        'FECHA VALOR': 'fecha',
        'FECHA': 'fecha',
        'F. OPERACION': 'fecha',
        'F.OPERACION': 'fecha',
        'FECHA OPERACION': 'fecha',
        'DESCRIPCION': 'descripcion',
        'CONCEPTO': 'descripcion',
        'MOVIMIENTO': 'descripcion',
        'IMPORTE': 'importe',
        'CANTIDAD': 'importe',
        'MONTO': 'importe',
        'REFERENCIA': 'referencia',
        'REF': 'referencia',
    }

    # Renombrar columnas encontradas (solo la primera coincidencia para cada destino)
    columnas_renombrar = {}
    destinos_usados = set()
    for col_orig, col_nueva in columnas_mapeo.items():
        if col_orig in df.columns and col_nueva not in destinos_usados:
            columnas_renombrar[col_orig] = col_nueva
            destinos_usados.add(col_nueva)

    df = df.rename(columns=columnas_renombrar)

    # Verificar columnas mínimas requeridas
    columnas_requeridas = ['fecha', 'descripcion', 'importe']
    for col in columnas_requeridas:
        if col not in df.columns:
            raise ValueError(f"Columna requerida no encontrada: {col}. Columnas disponibles: {list(df.columns)}")

    # Seleccionar y limpiar columnas
    columnas_salida = ['fecha', 'descripcion', 'importe']
    if 'referencia' in df.columns:
        columnas_salida.append('referencia')

    df = df[columnas_salida].copy()

    # Limpiar y convertir datos
    df['descripcion'] = df['descripcion'].fillna('').astype(str).str.strip()

    # Convertir importe (formato español: 1.234,56)
    df['importe'] = df['importe'].apply(_parsear_importe_espanol)

    # Convertir fecha
    df['fecha'] = df['fecha'].apply(_parsear_fecha)

    # Eliminar filas sin datos válidos
    df = df.dropna(subset=['fecha', 'importe'])
    df = df[df['descripcion'].astype(str).str.len() > 0]

    # Ordenar por fecha
    df = df.sort_values('fecha', ascending=False).reset_index(drop=True)

    return df


def _parsear_importe_espanol(valor) -> Optional[float]:
    """Convierte importe en formato español a float."""
    if valor is None:
        return None

    try:
        valor_str = str(valor).strip()
        if valor_str == '' or valor_str == 'nan' or valor_str == 'None':
            return None
        valor_str = valor_str.replace('.', '')
        valor_str = valor_str.replace(',', '.')
        return float(valor_str)
    except (ValueError, TypeError):
        return None


def _parsear_fecha(valor) -> Optional[str]:
    """Convierte fecha en varios formatos a YYYY-MM-DD."""
    # Manejar valores nulos
    if valor is None:
        return None

    try:
        # Convertir a string y verificar si está vacío
        valor_str = str(valor).strip()
        if valor_str == '' or valor_str == 'nan' or valor_str == 'None':
            return None
    except:
        return None

    formatos = [
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d/%m/%y',
        '%d-%m-%y',
    ]

    for fmt in formatos:
        try:
            fecha = datetime.strptime(valor_str, fmt)
            return fecha.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def auto_categorizar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica reglas de auto-categorización a los movimientos.
    """
    # Obtener reglas activas
    reglas_df = get_reglas()

    # Crear lista de tuplas (patron, categoria, vehiculo)
    reglas = []
    for _, r in reglas_df.iterrows():
        reglas.append((
            str(r['patron']).upper(),
            r['categoria_id'],
            r['vehiculo_id']
        ))

    # Inicializar columnas
    df = df.copy()
    df['categoria_id'] = None
    df['vehiculo_id'] = None
    df['necesita_revision'] = False

    for idx in df.index:
        descripcion = str(df.at[idx, 'descripcion']).upper()
        try:
            importe = float(df.at[idx, 'importe'])
        except (ValueError, TypeError):
            importe = 0.0

        # Buscar coincidencia con reglas
        categoria_encontrada = None
        vehiculo_encontrado = None

        for patron, categoria, vehiculo in reglas:
            if patron in descripcion:
                categoria_encontrada = categoria
                vehiculo_encontrado = vehiculo
                break

        if categoria_encontrada:
            df.at[idx, 'categoria_id'] = categoria_encontrada
            df.at[idx, 'vehiculo_id'] = vehiculo_encontrado

            # Si es gasto sin vehículo asignado, necesita revisión
            if importe < 0 and vehiculo_encontrado is None and categoria_encontrada != 'INGRESO':
                df.at[idx, 'necesita_revision'] = True
        else:
            # Sin categoría = ingreso si positivo, otro si negativo
            if importe > 0:
                df.at[idx, 'categoria_id'] = 'INGRESO'
            else:
                df.at[idx, 'categoria_id'] = 'OTRO'
            df.at[idx, 'necesita_revision'] = True

    return df


def preparar_para_guardado(df: pd.DataFrame) -> list:
    """
    Convierte DataFrame a lista de diccionarios para insertar en BD.
    """
    movimientos = []

    for idx in df.index:
        mov = {
            'fecha': df.at[idx, 'fecha'],
            'descripcion': df.at[idx, 'descripcion'],
            'importe': df.at[idx, 'importe'],
            'categoria_id': df.at[idx, 'categoria_id'] if 'categoria_id' in df.columns else None,
            'vehiculo_id': df.at[idx, 'vehiculo_id'] if 'vehiculo_id' in df.columns else None,
            'referencia': df.at[idx, 'referencia'] if 'referencia' in df.columns else None,
        }
        movimientos.append(mov)

    return movimientos


def validar_importacion(df: pd.DataFrame) -> dict:
    """
    Valida los datos antes de importar.
    """
    # Asegurar que importe es numérico
    importe_numerico = pd.to_numeric(df['importe'], errors='coerce').fillna(0)

    # Calcular necesitan_revision
    necesitan_rev = 0
    if 'necesita_revision' in df.columns:
        necesitan_rev = int(df['necesita_revision'].astype(bool).sum())

    stats = {
        'total_filas': len(df),
        'ingresos': int((importe_numerico > 0).sum()),
        'gastos': int((importe_numerico < 0).sum()),
        'suma_ingresos': float(importe_numerico[importe_numerico > 0].sum()),
        'suma_gastos': float(importe_numerico[importe_numerico < 0].sum()),
        'necesitan_revision': necesitan_rev,
        'periodo_desde': str(df['fecha'].min()) if len(df) > 0 else None,
        'periodo_hasta': str(df['fecha'].max()) if len(df) > 0 else None,
        'advertencias': []
    }

    # Verificar si hay movimientos sin categorizar
    if stats['necesitan_revision'] > 0:
        stats['advertencias'].append(
            f"{stats['necesitan_revision']} movimientos necesitan revisión manual"
        )

    # Verificar fechas
    if stats['periodo_desde'] and stats['periodo_hasta']:
        if stats['periodo_desde'] == stats['periodo_hasta']:
            stats['advertencias'].append(
                "Todos los movimientos tienen la misma fecha"
            )

    return stats


def detectar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta posibles duplicados comparando con movimientos existentes.
    """
    df = df.copy()
    df['posible_duplicado'] = False

    if len(df) == 0:
        return df

    # Obtener movimientos existentes del mismo periodo
    fecha_min = str(df['fecha'].min())
    fecha_max = str(df['fecha'].max())

    conn = get_connection()
    existentes = pd.read_sql_query("""
        SELECT fecha, descripcion, importe
        FROM movimientos
        WHERE fecha BETWEEN ? AND ?
    """, conn, params=[fecha_min, fecha_max])
    conn.close()

    if len(existentes) == 0:
        return df

    # Crear clave única para comparar
    claves_existentes = set()
    for idx in existentes.index:
        fecha = str(existentes.at[idx, 'fecha'])
        desc = str(existentes.at[idx, 'descripcion'])[:50]
        try:
            imp = round(float(existentes.at[idx, 'importe']), 2)
        except (ValueError, TypeError):
            imp = 0
        claves_existentes.add(f"{fecha}|{desc}|{imp}")

    for idx in df.index:
        fecha = str(df.at[idx, 'fecha'])
        desc = str(df.at[idx, 'descripcion'])[:50]
        try:
            imp = round(float(df.at[idx, 'importe']), 2)
        except (ValueError, TypeError):
            imp = 0
        clave = f"{fecha}|{desc}|{imp}"
        if clave in claves_existentes:
            df.at[idx, 'posible_duplicado'] = True

    return df
