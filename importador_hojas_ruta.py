"""
LogisPLAN - Importador de Hojas de Ruta
Parsea PDFs de hojas de ruta con datos de kilómetros, viajes y repartos por zona.

Formato esperado del PDF:
  Encabezado: "Enero 2026 - Dispositivo MJC"
  Tabla zonas: Verde, Azul, Morado, Naranja, Rojo → Viajes, Repartos, Km, % Viajes
  Totales: Total Viajes, Total Repartos, Total Kilómetros, Media Repartos/Viaje, Días Trabajados
"""

import re
import pdfplumber
from io import BytesIO


# Mapeo dispositivo → vehículo
DISPOSITIVOS = {
    'MJC': 'MJC',
    'MTY': 'MTY',
    'LVX': 'LVX',
    'MLB': 'MLB',
}

# Meses en español → número
MESES_ES_INV = {
    'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
    'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
    'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12',
}

# Zonas válidas
ZONAS_VALIDAS = ['Verde', 'Azul', 'Morado', 'Naranja', 'Rojo']


def _parsear_numero(texto):
    """Convierte texto numérico (formato español) a float."""
    try:
        limpio = texto.strip().replace('%', '').replace('.', '').replace(',', '.')
        return float(limpio)
    except (ValueError, AttributeError):
        return 0.0


def parsear_pdf_hoja_ruta(pdf_bytes, filename):
    """
    Parsea un PDF de hoja de ruta.
    Retorna: (resultado_dict, errores_list)

    resultado_dict = {
        'mes': '2026-01',
        'vehiculo_id': 'MJC',
        'dispositivo': 'MJC',
        'zonas': [
            {'zona': 'Verde', 'viajes': 37, 'repartos': 62, 'km': 1928.8},
            ...
        ],
        'total_viajes': 55,
        'total_repartos': 108,
        'total_km': 7067.1,
        'media_repartos_viaje': 2.0,
        'dias_trabajados': 25,
    }
    """
    errores = []
    resultado = {
        'mes': None,
        'vehiculo_id': None,
        'dispositivo': None,
        'zonas': [],
        'total_viajes': 0,
        'total_repartos': 0,
        'total_km': 0.0,
        'media_repartos_viaje': 0.0,
        'dias_trabajados': 0,
    }

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto_completo += (page.extract_text() or "") + "\n"

    except Exception as e:
        errores.append(f"Error al leer PDF: {str(e)}")
        return resultado, errores

    if not texto_completo.strip():
        errores.append("PDF vacío o sin texto extraíble")
        return resultado, errores

    # --- 1. Detectar encabezado: "Enero 2026 - Dispositivo MJC" ---
    meses_pattern = '|'.join(MESES_ES_INV.keys())
    header_match = re.search(
        rf'({meses_pattern})\s+(\d{{4}})\s*[-–—]\s*Dispositivo\s+(\w+)',
        texto_completo, re.IGNORECASE
    )

    if header_match:
        mes_nombre = header_match.group(1).upper()
        anio = header_match.group(2)
        dispositivo = header_match.group(3).upper()

        mes_num = MESES_ES_INV.get(mes_nombre)
        if mes_num:
            resultado['mes'] = f"{anio}-{mes_num}"
        else:
            errores.append(f"Mes no reconocido: {mes_nombre}")

        # Mapear dispositivo a vehículo
        if dispositivo in DISPOSITIVOS:
            resultado['vehiculo_id'] = DISPOSITIVOS[dispositivo]
            resultado['dispositivo'] = dispositivo
        else:
            errores.append(f"Dispositivo no reconocido: {dispositivo}")
    else:
        # Intentar detección alternativa desde filename
        for mes_es, mes_num in MESES_ES_INV.items():
            if mes_es in filename.upper():
                # Buscar año
                anio_match = re.search(r'(\d{4})', filename)
                if anio_match:
                    resultado['mes'] = f"{anio_match.group(1)}-{mes_num}"
                break

        for disp in DISPOSITIVOS:
            if disp in filename.upper():
                resultado['vehiculo_id'] = DISPOSITIVOS[disp]
                resultado['dispositivo'] = disp
                break

        if not resultado['mes'] or not resultado['vehiculo_id']:
            errores.append("No se pudo detectar mes y/o dispositivo del encabezado ni del nombre de archivo")

    # --- 2. Extraer zonas ---
    lineas = texto_completo.split('\n')

    for linea in lineas:
        linea_strip = linea.strip()
        if not linea_strip:
            continue

        # Buscar filas de zona: "Verde 37 62 1928.8 67.3%"
        # o con separación variada: "Verde   37   62   1.928,8   67,3%"
        for zona_nombre in ZONAS_VALIDAS:
            if zona_nombre.lower() in linea_strip.lower():
                # Extraer números de la línea después del nombre de zona
                parte = re.split(zona_nombre, linea_strip, flags=re.IGNORECASE)
                if len(parte) > 1:
                    numeros_raw = re.findall(r'[\d.,]+', parte[1])
                    numeros = []
                    for n in numeros_raw:
                        val = _parsear_numero(n)
                        numeros.append(val)

                    if len(numeros) >= 3:
                        zona_data = {
                            'zona': zona_nombre,
                            'viajes': int(numeros[0]),
                            'repartos': int(numeros[1]),
                            'km': numeros[2],
                        }
                        # Evitar duplicados
                        if not any(z['zona'] == zona_nombre for z in resultado['zonas']):
                            resultado['zonas'].append(zona_data)
                break  # Solo un match por línea

    # --- 3. Extraer totales ---
    for linea in lineas:
        linea_strip = linea.strip()
        linea_lower = linea_strip.lower()

        if 'total viajes' in linea_lower:
            nums = re.findall(r'[\d.,]+', linea_strip)
            if nums:
                resultado['total_viajes'] = int(_parsear_numero(nums[-1]))

        elif 'total repartos' in linea_lower:
            nums = re.findall(r'[\d.,]+', linea_strip)
            if nums:
                resultado['total_repartos'] = int(_parsear_numero(nums[-1]))

        elif 'total kil' in linea_lower or 'total km' in linea_lower:
            nums = re.findall(r'[\d.,]+', linea_strip)
            if nums:
                resultado['total_km'] = _parsear_numero(nums[-1])

        elif 'media repartos' in linea_lower:
            nums = re.findall(r'[\d.,]+', linea_strip)
            if nums:
                resultado['media_repartos_viaje'] = _parsear_numero(nums[-1])

        elif 'as trabajad' in linea_lower or 'dias trabajad' in linea_lower:
            nums = re.findall(r'[\d.,]+', linea_strip)
            if nums:
                resultado['dias_trabajados'] = int(_parsear_numero(nums[-1]))

    # --- 4. Calcular totales desde zonas si no se encontraron en texto ---
    if resultado['zonas']:
        total_viajes_calc = sum(z['viajes'] for z in resultado['zonas'])
        total_repartos_calc = sum(z['repartos'] for z in resultado['zonas'])
        total_km_calc = sum(z['km'] for z in resultado['zonas'])

        if resultado['total_viajes'] == 0:
            resultado['total_viajes'] = total_viajes_calc
        if resultado['total_repartos'] == 0:
            resultado['total_repartos'] = total_repartos_calc
        if resultado['total_km'] == 0:
            resultado['total_km'] = total_km_calc
        if resultado['media_repartos_viaje'] == 0 and total_viajes_calc > 0:
            resultado['media_repartos_viaje'] = round(total_repartos_calc / total_viajes_calc, 1)
    else:
        if not errores:
            errores.append("No se encontraron datos de zonas en el PDF")

    # Validar que tenemos datos mínimos
    if not resultado['zonas'] and not errores:
        errores.append("No se pudieron extraer zonas del PDF")

    return resultado, errores
