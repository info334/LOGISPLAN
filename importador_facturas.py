"""
LogisPLAN - Importador de Facturas de Combustible y Peajes
Parsea facturas PDF de:
- StarOil (combustible) - bonificación fija 0,165€/L gasoil, 0,30€/L AdBlue
- Solred/Waylet (combustible) - descuento en columna Dto
- Valcarce (combustible o peajes) - detecta automáticamente el tipo
"""

import pdfplumber
import re
from datetime import datetime
from typing import Optional, List, Dict, Union
from io import BytesIO


# Mapeo de matrículas a IDs de vehículo
MATRICULAS_VEHICULOS = {
    '1257MTY': 'MTY',
    '1257-MTY': 'MTY',
    'MTY': 'MTY',
    '9245MJC': 'MJC',
    '9245-MJC': 'MJC',
    'MJC': 'MJC',
    '1382LVX': 'LVX',
    '1382-LVX': 'LVX',
    'LVX': 'LVX',
    '0245MLB': 'MLB',
    '0245-MLB': 'MLB',
    'MLB': 'MLB',
}

# Bonificaciones fijas StarOil (€/litro con IVA incluido)
# En factura aparecen como 0,165€/L gasoil y 0,30€/L AdBlue (con IVA)
# Para aplicar sobre base imponible, quitamos el IVA
BONIF_STAROIL_GASOIL_IVA = 0.165
BONIF_STAROIL_ADBLUE_IVA = 0.30
BONIF_STAROIL_GASOIL = BONIF_STAROIL_GASOIL_IVA / 1.21  # ~0.1364€/L sin IVA
BONIF_STAROIL_ADBLUE = BONIF_STAROIL_ADBLUE_IVA / 1.21  # ~0.2479€/L sin IVA


def normalizar_matricula(matricula: str) -> Optional[str]:
    """Convierte una matrícula al ID de vehículo correspondiente."""
    matricula = matricula.upper().replace(' ', '').replace('-', '')

    # Buscar coincidencia directa
    for key, value in MATRICULAS_VEHICULOS.items():
        if key.replace('-', '') == matricula:
            return value

    # Buscar por contenido
    for key, value in MATRICULAS_VEHICULOS.items():
        if key.replace('-', '') in matricula or matricula in key.replace('-', ''):
            return value

    return None


def parsear_numero_es(texto: str) -> Optional[float]:
    """Parsea un número en formato español (1.234,56) a float."""
    if not texto or texto == '-':
        return None
    try:
        texto = str(texto).strip()
        texto = texto.replace('.', '').replace(',', '.')
        return float(texto)
    except (ValueError, TypeError):
        return None


def detectar_proveedor(texto: str) -> str:
    """Detecta el proveedor de la factura por el contenido."""
    texto_upper = texto.upper()

    if 'STAROIL' in texto_upper:
        return 'STAROIL'
    elif 'SOLRED' in texto_upper or 'REPSOL' in texto_upper or 'WAYLET' in texto_upper:
        return 'SOLRED'
    elif 'VALCARCE' in texto_upper:
        return 'VALCARCE'

    return 'DESCONOCIDO'


def detectar_tipo_valcarce(texto: str) -> str:
    """
    Detecta si una factura de Valcarce es de COMBUSTIBLE o PEAJES.
    - PEAJES: contiene "AT-1K PEAJE" o similar
    - COMBUSTIBLE: contiene "GA GASOLEO" o "GASOLEO"
    """
    texto_upper = texto.upper()

    # Buscar indicadores de peajes
    if re.search(r'AT-\d*[A-Z]*\s+PEAJE', texto_upper):
        return 'PEAJES'

    # Buscar indicadores de combustible
    if 'GA GASOLEO' in texto_upper or 'GASOLEO' in texto_upper:
        return 'COMBUSTIBLE'

    # Por defecto, asumir combustible (el tipo original)
    return 'COMBUSTIBLE'


def parsear_factura_pdf(contenido: bytes, nombre_archivo: str = None) -> Dict:
    """
    Parsea una factura PDF de combustible o peajes.

    Returns:
        Dict con:
        - proveedor: str
        - tipo: 'COMBUSTIBLE' o 'PEAJES'
        - fecha_factura: str
        - num_factura: str
        - total_factura: float
        - movimientos: List[Dict] - cada repostaje/peaje individual
        - resumen_vehiculos: Dict[vehiculo] = {litros_gasoil, litros_adblue, importe_total, etc}
    """
    resultado = {
        'proveedor': 'DESCONOCIDO',
        'tipo': 'COMBUSTIBLE',
        'fecha_factura': None,
        'num_factura': None,
        'total_factura': 0,
        'movimientos': [],
        'resumen_vehiculos': {},
        'errores': []
    }

    try:
        pdf = pdfplumber.open(BytesIO(contenido))
        texto_completo = ''

        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() or ''

        pdf.close()

        # Detectar proveedor
        proveedor = detectar_proveedor(texto_completo)
        resultado['proveedor'] = proveedor

        if proveedor == 'STAROIL':
            resultado['tipo'] = 'COMBUSTIBLE'
            resultado = parsear_staroil(contenido, resultado)
        elif proveedor == 'SOLRED':
            resultado['tipo'] = 'COMBUSTIBLE'
            resultado = parsear_solred(contenido, resultado)
        elif proveedor == 'VALCARCE':
            # Detectar si es combustible o peajes
            tipo_valcarce = detectar_tipo_valcarce(texto_completo)
            resultado['tipo'] = tipo_valcarce
            if tipo_valcarce == 'PEAJES':
                resultado = parsear_valcarce_peajes(contenido, resultado)
            else:
                resultado = parsear_valcarce_combustible(contenido, resultado)
        else:
            resultado['errores'].append(f"Proveedor no reconocido en {nombre_archivo}")

    except Exception as e:
        resultado['errores'].append(f"Error al procesar PDF: {str(e)}")

    return resultado


def parsear_staroil(contenido: bytes, resultado: Dict) -> Dict:
    """
    Parsea factura de StarOil - cada repostaje individual.
    Bonificación fija: 0,165€/L gasoil, 0,30€/L AdBlue
    """
    pdf = pdfplumber.open(BytesIO(contenido))

    vehiculo_actual = None
    fecha_factura = None

    for pagina in pdf.pages:
        texto = pagina.extract_text() or ''
        lineas = texto.split('\n')

        for linea in lineas:
            # Buscar fecha y número de factura (formato: 31/12/25 2503369 101217)
            if re.match(r'^\d{2}/\d{2}/\d{2}\s+\d{6,}', linea):
                match = re.match(r'^(\d{2}/\d{2}/\d{2})\s+(\d{6,})', linea)
                if match:
                    try:
                        fecha_factura = datetime.strptime(match.group(1), '%d/%m/%y').strftime('%Y-%m-%d')
                        resultado['fecha_factura'] = fecha_factura
                        resultado['num_factura'] = match.group(2)
                    except:
                        pass

            # Detectar vehículo
            if 'Matrícula' in linea or 'Matricula' in linea:
                match = re.search(r':\s*(\d*[A-Z]{2,3})', linea)
                if match:
                    vehiculo_actual = normalizar_matricula(match.group(1))

            # Parsear líneas de combustible - cada repostaje
            # Formato: 1050227643 01/12/25 107727 Gasol A 140,06 1,428 200,00
            match = re.match(r'(\d{10})\s+(\d{2}/\d{2}/\d{2})\s+\d+\s+(Gasol\s*A|AdBlue)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)', linea)
            if match and vehiculo_actual:
                concepto = 'GASOIL' if 'Gasol' in match.group(3) else 'ADBLUE'
                litros = parsear_numero_es(match.group(4))
                precio_bruto_iva = parsear_numero_es(match.group(5))  # Precio con IVA
                importe_con_iva = parsear_numero_es(match.group(6))

                # El importe en factura incluye IVA, calcular base imponible
                importe_base = importe_con_iva / 1.21

                # Bonificación fija (con IVA para mostrar)
                if concepto == 'GASOIL':
                    bonif_iva = BONIF_STAROIL_GASOIL_IVA  # 0.165€/L
                    descuento = litros * BONIF_STAROIL_GASOIL  # Sin IVA para cálculos
                else:  # ADBLUE
                    bonif_iva = BONIF_STAROIL_ADBLUE_IVA  # 0.30€/L
                    descuento = litros * BONIF_STAROIL_ADBLUE

                importe_neto = importe_base - descuento

                # Precio neto = precio bruto (IVA inc.) - bonificación fija
                precio_neto_iva = precio_bruto_iva - bonif_iva

                try:
                    fecha_op = datetime.strptime(match.group(2), '%d/%m/%y').strftime('%Y-%m-%d')
                except:
                    fecha_op = fecha_factura

                resultado['movimientos'].append({
                    'vehiculo': vehiculo_actual,
                    'fecha': fecha_op,
                    'concepto': concepto,
                    'litros': litros,
                    'precio_litro': precio_neto_iva,  # Precio IVA inc. - bonificación
                    'importe_bruto': importe_base,  # Base imponible (sin IVA)
                    'descuento': descuento,
                    'importe': importe_neto
                })

    # Buscar total factura
    # Formato: Base Imponible % Cuota IVA Total Factura
    #          4.178,56 21,00 877,50 5.056,06
    for pagina in pdf.pages:
        texto = pagina.extract_text() or ''
        # Buscar línea con Base Imponible, IVA y Total
        match_total = re.search(r'([\d.,]+)\s+21[,.]00\s+([\d.,]+)\s+([\d.,]+)\s*$', texto, re.MULTILINE)
        if match_total:
            # Usar Base Imponible (primer número) - sin IVA
            resultado['total_factura'] = parsear_numero_es(match_total.group(1))

    pdf.close()

    # Calcular resumen por vehículo
    resultado['resumen_vehiculos'] = calcular_resumen_vehiculos(resultado['movimientos'])

    return resultado


def parsear_solred(contenido: bytes, resultado: Dict) -> Dict:
    """
    Parsea factura de Solred/Waylet - cada repostaje individual.
    Descuento en columna "Dto. tot. cent€/u iva inc."
    """
    pdf = pdfplumber.open(BytesIO(contenido))

    texto_completo = ''
    for pagina in pdf.pages:
        texto_completo += (pagina.extract_text() or '') + '\n'

    # Buscar fecha factura
    match_fecha = re.search(r'Fechadeoperación\s*(\d{2}/\d{2}/\d{4})\s*AL\s*(\d{2}/\d{2}/\d{4})', texto_completo.replace(' ', ''))
    if not match_fecha:
        match_fecha = re.search(r'Fecha de operación\s+(\d{2}/\d{2}/\d{4})\s+AL\s+(\d{2}/\d{2}/\d{4})', texto_completo)
    if match_fecha:
        try:
            resultado['fecha_factura'] = datetime.strptime(match_fecha.group(2), '%d/%m/%Y').strftime('%Y-%m-%d')
        except:
            pass

    # Buscar número factura
    match_num = re.search(r'Núm\.?\s*Factura\s+([A-Z0-9]+)', texto_completo)
    if not match_num:
        match_num = re.search(r'Num\.?Factura\s*([A-Z0-9]+)', texto_completo.replace(' ', ''))
    if match_num:
        resultado['num_factura'] = match_num.group(1)

    # Buscar total factura
    match_total = re.search(r'Total Factura en Euros\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)', texto_completo)
    if match_total:
        resultado['total_factura'] = parsear_numero_es(match_total.group(3))

    # Parsear detalle de operaciones (página 3)
    vehiculo_actual = None
    año_factura = datetime.now().year
    if resultado.get('fecha_factura'):
        año_factura = int(resultado['fecha_factura'][:4])

    lineas = texto_completo.split('\n')

    for linea in lineas:
        # Detectar cambio de vehículo
        # Formato: Nº de Tarjeta 7078 8378 9547 0026 Nº de Matrícula 9245-MJC Conductor
        match_vehiculo = re.search(r'Nº de Matrícula\s+(\d{4}-[A-Z]{3})', linea)
        if match_vehiculo:
            vehiculo_actual = normalizar_matricula(match_vehiculo.group(1))
            continue

        # Parsear líneas de operación
        # Formato: 1189536 05/0115:33 DIESEL E+ NEOTECH (L) E.S. ... 158,73 1,398 1,449 1,398 221,90 10,00 15,87 206,03
        # Los números al final son: cantidad, precio_neto, precio_iva, precio_unit, importe_bruto, [dto%, dto_cent, importe_final] o [importe_final]

        if not vehiculo_actual:
            continue

        # Detectar si es DIESEL o ADBLUE
        es_diesel = 'DIESEL' in linea
        es_adblue = 'ADBLUE' in linea

        if not (es_diesel or es_adblue):
            continue

        # Extraer fecha al inicio
        match_fecha = re.match(r'(\d{6,})\s+(\d{2}/\d{2})\s*\d{2}:\d{2}', linea)
        if not match_fecha:
            continue

        fecha_str = match_fecha.group(2)

        # Extraer todos los números de la línea (después del concepto)
        # Buscar desde después del concepto DIESEL/ADBLUE
        if es_diesel:
            pos = linea.find('DIESEL')
            resto = linea[pos:]
        else:
            pos = linea.find('ADBLUE')
            resto = linea[pos:]

        # Encontrar todos los números en el resto de la línea
        numeros = re.findall(r'([\d]+[,.][\d]+)', resto)

        if len(numeros) < 5:
            continue

        # Formato: cantidad, precio_sin_iva, precio_con_iva, precio_unit, importe_bruto, [dto%, dto_cent, importe_final]
        # Los primeros 5 números son siempre: cantidad, precio_neto, precio_iva, precio_unit, importe_bruto
        litros = parsear_numero_es(numeros[0])
        precio_con_iva = parsear_numero_es(numeros[2])  # Precio IVA incluido
        importe_bruto = parsear_numero_es(numeros[4])

        # El último número siempre es el importe final
        importe_final = parsear_numero_es(numeros[-1])

        # Si hay más de 5 números, hay descuento (dto%, dto_cent€/u, importe_final)
        # numeros[5] = dto%, numeros[6] = dto_cent€/u (centimos por litro)
        dto_cent_litro = 0
        if len(numeros) >= 7:
            dto_cent_litro = parsear_numero_es(numeros[5]) / 100  # Convertir cent€ a €

        # Precio neto = precio con IVA - descuento por litro
        precio_neto_iva = precio_con_iva - dto_cent_litro

        # Calcular descuento total
        descuento = importe_bruto - importe_final if importe_bruto and importe_final else 0
        if descuento < 0.01:
            descuento = 0

        try:
            fecha_op = datetime.strptime(fecha_str + '/' + str(año_factura), '%d/%m/%Y').strftime('%Y-%m-%d')
        except:
            fecha_op = resultado.get('fecha_factura')

        resultado['movimientos'].append({
            'vehiculo': vehiculo_actual,
            'fecha': fecha_op,
            'concepto': 'GASOIL' if es_diesel else 'ADBLUE',
            'litros': litros,
            'precio_litro': precio_neto_iva,  # Precio IVA inc. - descuento
            'importe_bruto': importe_bruto,
            'descuento': descuento,
            'importe': importe_final
        })

    pdf.close()

    # Calcular resumen por vehículo
    resultado['resumen_vehiculos'] = calcular_resumen_vehiculos(resultado['movimientos'])

    return resultado


def parsear_valcarce_combustible(contenido: bytes, resultado: Dict) -> Dict:
    """
    Parsea factura de Valcarce - COMBUSTIBLE (GASOLEO).
    Formato: GA GASOLEO "A" fecha operacion cantidad precio importe
    El importe en la línea incluye IVA, usamos Base Imponible para el neto.
    """
    pdf = pdfplumber.open(BytesIO(contenido))

    vehiculo_actual = None
    texto_completo = ''
    bases_imponibles = {}  # {vehiculo: base_imponible}

    for pagina in pdf.pages:
        texto = pagina.extract_text() or ''
        texto_completo += texto + '\n'
        lineas = texto.split('\n')

        for linea in lineas:
            # Buscar fecha y número factura (formato: 31/12/2025 462989 24034 1)
            match_fecha_num = re.match(r'^\s*(\d{2}/\d{2}/\d{4})\s+(\d{5,})\s+\d+', linea)
            if match_fecha_num:
                try:
                    resultado['fecha_factura'] = datetime.strptime(match_fecha_num.group(1), '%d/%m/%Y').strftime('%Y-%m-%d')
                    resultado['num_factura'] = match_fecha_num.group(2)
                except:
                    pass
                continue

            # Detectar vehículo (formato: ** Vehículo : 9245MJC)
            match_vehiculo = re.search(r'Vehículo\s*:\s*(\d*[A-Z]{2,3})', linea)
            if match_vehiculo:
                vehiculo_actual = normalizar_matricula(match_vehiculo.group(1))
                continue

            # Parsear líneas de combustible
            # Formato: GA GASOLEO "A" 17-12 0039627 255,01 1,1854 302,29
            match_gasoleo = re.match(r'GA\s+GASOLEO.*?(\d{2}-\d{2})\s+\d+\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)', linea)
            if match_gasoleo and vehiculo_actual:
                fecha_str = match_gasoleo.group(1)
                litros = parsear_numero_es(match_gasoleo.group(2))
                precio_bruto = parsear_numero_es(match_gasoleo.group(3))
                importe_con_iva = parsear_numero_es(match_gasoleo.group(4))

                # Obtener año de la factura
                año_factura = datetime.now().year
                if resultado.get('fecha_factura'):
                    año_factura = int(resultado['fecha_factura'][:4])

                try:
                    fecha_op = datetime.strptime(fecha_str + '-' + str(año_factura), '%d-%m-%Y').strftime('%Y-%m-%d')
                except:
                    fecha_op = resultado.get('fecha_factura')

                resultado['movimientos'].append({
                    'vehiculo': vehiculo_actual,
                    'fecha': fecha_op,
                    'concepto': 'GASOIL',
                    'litros': litros,
                    'precio_litro': precio_bruto,
                    'importe_bruto': importe_con_iva,
                    'descuento': 0,  # Se actualiza con Base Imponible
                    'importe': 0  # Se actualiza con Base Imponible
                })
                continue

            # Capturar descuento (línea siguiente al combustible)
            # Formato: 1801500.VALCARCE - TISCO Imp:372,06 Dto:69,77
            match_dto = re.search(r'Imp:\s*([\d,]+)\s+Dto:\s*([\d,]+)', linea)
            if match_dto and vehiculo_actual and resultado['movimientos']:
                # Guardar info de descuento para el último movimiento
                for mov in reversed(resultado['movimientos']):
                    if mov['vehiculo'] == vehiculo_actual:
                        mov['_dto_info'] = parsear_numero_es(match_dto.group(2))
                        break
                continue

            # Capturar Base Imponible por vehículo
            # Formato: -- Total Base Imponible 249,83 255,01
            match_base = re.match(r'--\s*Total Base Imponible\s+([\d,]+)\s+([\d,]+)', linea)
            if match_base and vehiculo_actual:
                base = parsear_numero_es(match_base.group(1))
                bases_imponibles[vehiculo_actual] = base
                continue

    # Buscar total factura (Base Imponible global)
    match_total = re.search(r'--\s*BASE IMPONIBLE.*?([\d,]+)\s+21', texto_completo)
    if match_total:
        resultado['total_factura'] = parsear_numero_es(match_total.group(1))
    else:
        # Alternativa: sumar bases imponibles
        resultado['total_factura'] = sum(bases_imponibles.values())

    pdf.close()

    # Actualizar importes netos usando bases imponibles
    for mov in resultado['movimientos']:
        veh = mov['vehiculo']
        if veh in bases_imponibles:
            # Si hay un solo repostaje por vehículo, usar la base imponible directamente
            movs_veh = [m for m in resultado['movimientos'] if m['vehiculo'] == veh]
            if len(movs_veh) == 1:
                mov['importe'] = bases_imponibles[veh]
                mov['descuento'] = mov['importe_bruto'] - mov['importe']
                if mov['litros'] and mov['litros'] > 0:
                    mov['precio_litro'] = mov['importe'] / mov['litros']
            else:
                # Si hay varios repostajes, prorratear según litros
                total_litros = sum(m.get('litros', 0) or 0 for m in movs_veh)
                if total_litros > 0:
                    proporcion = (mov.get('litros', 0) or 0) / total_litros
                    mov['importe'] = bases_imponibles[veh] * proporcion
                    mov['descuento'] = mov['importe_bruto'] - mov['importe']
                    if mov['litros'] and mov['litros'] > 0:
                        mov['precio_litro'] = mov['importe'] / mov['litros']

    # Calcular resumen por vehículo
    resultado['resumen_vehiculos'] = calcular_resumen_vehiculos(resultado['movimientos'])

    return resultado


def parsear_valcarce_peajes(contenido: bytes, resultado: Dict) -> Dict:
    """
    Parsea factura de Valcarce - PEAJES.
    Usa la Base Imponible por vehículo (sin IVA).
    """
    pdf = pdfplumber.open(BytesIO(contenido))

    vehiculo_actual = None
    texto_completo = ''
    bases_imponibles = {}  # {vehiculo: base_imponible}

    # Obtener año de la factura (se actualiza al parsear)
    año_factura = datetime.now().year

    for pagina in pdf.pages:
        texto = pagina.extract_text() or ''
        texto_completo += texto + '\n'
        lineas = texto.split('\n')

        for linea in lineas:
            # Buscar fecha y número factura (formato: 16/01/2026 T84194 24034)
            match_fecha_num = re.match(r'^\s*(\d{2}/\d{2}/\d{4})\s+([A-Z]?\d{5,})\s+\d+', linea)
            if match_fecha_num:
                try:
                    resultado['fecha_factura'] = datetime.strptime(match_fecha_num.group(1), '%d/%m/%Y').strftime('%Y-%m-%d')
                    resultado['num_factura'] = match_fecha_num.group(2)
                    año_factura = int(resultado['fecha_factura'][:4])
                except:
                    pass
                continue

            # Detectar vehículo (formato: ** Vehículo : 0245MLB)
            match_vehiculo = re.search(r'Vehículo\s*:\s*(\d*[A-Z]{2,3})', linea)
            if match_vehiculo:
                vehiculo_actual = normalizar_matricula(match_vehiculo.group(1))
                continue

            # Parsear líneas de peaje
            # Formato: AT-1K PEAJE 27-11 08:31 1,00 4,690 4,69
            # Bonificaciones tienen importe negativo
            match_peaje = re.match(r'AT-\d*[A-Z]*\s+PEAJE\s+(\d{2}-\d{2})\s+\d{2}:\d{2}\s+[\d,]+\s+(-?[\d,]+)\s+(-?[\d,]+)', linea)
            if match_peaje and vehiculo_actual:
                fecha_str = match_peaje.group(1)
                importe = parsear_numero_es(match_peaje.group(3))

                es_bonificacion = importe < 0 if importe else False

                try:
                    fecha_op = datetime.strptime(fecha_str + '-' + str(año_factura), '%d-%m-%Y').strftime('%Y-%m-%d')
                except:
                    fecha_op = resultado.get('fecha_factura')

                resultado['movimientos'].append({
                    'vehiculo': vehiculo_actual,
                    'fecha': fecha_op,
                    'concepto': 'BONIF_PEAJE' if es_bonificacion else 'PEAJE',
                    'importe': importe
                })
                continue

            # Parsear comisiones, seguros, cuotas
            match_comision = re.match(r'AT-[A-Z]+\s+(COMISION|SEGURO|CUOTA).*?[\d,]+\s+([\d,]+)\s*$', linea)
            if match_comision and vehiculo_actual:
                tipo = match_comision.group(1)
                importe = parsear_numero_es(match_comision.group(2))

                resultado['movimientos'].append({
                    'vehiculo': vehiculo_actual,
                    'fecha': resultado.get('fecha_factura'),
                    'concepto': tipo,
                    'importe': importe
                })
                continue

            # Capturar Total Base Imponible por vehículo
            # Formato: -- Total Base Imponible 78,06 33,00
            match_base = re.match(r'--\s*Total Base Imponible\s+([\d,]+)\s+[\d,]+', linea)
            if match_base and vehiculo_actual:
                base = parsear_numero_es(match_base.group(1))
                bases_imponibles[vehiculo_actual] = base

    # Buscar total factura (Base Imponible global)
    # Formato: -- BASE IMPONIBLE -- - %IVA - ... \n 134,83 21 28,31 163,14
    match_total = re.search(r'BASE IMPONIBLE.*?%IVA.*?TOTAL FACTURA.*?\n\s*([\d.,]+)\s+21\s+([\d.,]+)\s+([\d.,]+)', texto_completo, re.DOTALL)
    if match_total:
        resultado['total_factura'] = parsear_numero_es(match_total.group(1))
    else:
        # Alternativa: sumar bases imponibles por vehículo
        if bases_imponibles:
            resultado['total_factura'] = sum(bases_imponibles.values())

    pdf.close()

    # Calcular resumen por vehículo usando bases imponibles capturadas
    resultado['resumen_vehiculos'] = calcular_resumen_peajes(resultado['movimientos'], bases_imponibles)

    return resultado


def calcular_resumen_vehiculos(movimientos: List[Dict]) -> Dict:
    """Calcula resumen de combustible por vehículo."""
    resumen = {}

    for mov in movimientos:
        veh = mov['vehiculo']
        if veh not in resumen:
            resumen[veh] = {
                'litros_gasoil': 0,
                'litros_adblue': 0,
                'importe_gasoil': 0,
                'importe_adblue': 0,
                'importe_bruto_gasoil': 0,
                'importe_bruto_adblue': 0,
                'descuento_total': 0,
                'importe_neto': 0,
                'precio_medio_litro': 0,
                'num_repostajes': 0,
                '_suma_precio_litros': 0  # Para calcular precio medio ponderado
            }

        litros = mov.get('litros', 0) or 0
        importe = mov.get('importe', 0) or 0
        importe_bruto = mov.get('importe_bruto', 0) or 0
        descuento = mov.get('descuento', 0) or 0
        precio_litro = mov.get('precio_litro', 0) or 0

        if mov['concepto'] == 'GASOIL':
            resumen[veh]['litros_gasoil'] += litros
            resumen[veh]['importe_gasoil'] += importe
            resumen[veh]['importe_bruto_gasoil'] += importe_bruto
        else:
            resumen[veh]['litros_adblue'] += litros
            resumen[veh]['importe_adblue'] += importe
            resumen[veh]['importe_bruto_adblue'] += importe_bruto

        resumen[veh]['descuento_total'] += descuento
        resumen[veh]['num_repostajes'] += 1
        # Sumar precio * litros para calcular media ponderada
        resumen[veh]['_suma_precio_litros'] += precio_litro * litros

    # Calcular totales y precio medio
    for veh in resumen:
        r = resumen[veh]
        r['importe_neto'] = r['importe_gasoil'] + r['importe_adblue']
        total_litros = r['litros_gasoil'] + r['litros_adblue']

        if total_litros > 0:
            # Precio medio ponderado = suma(precio * litros) / total_litros
            r['precio_medio_litro'] = r['_suma_precio_litros'] / total_litros

        # Limpiar campo auxiliar
        del r['_suma_precio_litros']

    return resumen


def calcular_resumen_peajes(movimientos: List[Dict], bases_imponibles: Dict = None) -> Dict:
    """Calcula resumen de peajes por vehículo."""
    resumen = {}

    for mov in movimientos:
        veh = mov['vehiculo']
        if veh not in resumen:
            resumen[veh] = {
                'num_peajes': 0,
                'importe_peajes': 0,
                'importe_bonificaciones': 0,
                'importe_comisiones': 0,
                'importe_neto': 0
            }

        concepto = mov.get('concepto', '')
        importe = mov.get('importe', 0) or 0

        if concepto == 'PEAJE':
            resumen[veh]['num_peajes'] += 1
            resumen[veh]['importe_peajes'] += importe
        elif concepto == 'BONIF_PEAJE':
            resumen[veh]['importe_bonificaciones'] += importe  # Ya es negativo
        elif concepto in ('COMISION', 'SEGURO', 'CUOTA'):
            resumen[veh]['importe_comisiones'] += importe

    # Usar bases imponibles si están disponibles
    if bases_imponibles:
        for veh in resumen:
            if veh in bases_imponibles:
                resumen[veh]['importe_neto'] = bases_imponibles[veh]
    else:
        # Calcular sumando todo
        for veh in resumen:
            r = resumen[veh]
            r['importe_neto'] = r['importe_peajes'] + r['importe_bonificaciones'] + r['importe_comisiones']

    return resumen


def generar_movimientos_para_db(resultado: Dict) -> List[Dict]:
    """
    Genera los movimientos listos para insertar en la base de datos.
    - Combustible: Un movimiento por vehículo con total
    - Peajes: Un movimiento por vehículo con total
    """
    movimientos_db = []
    fecha = resultado.get('fecha_factura') or datetime.now().strftime('%Y-%m-%d')
    proveedor = resultado.get('proveedor', 'FACTURA')
    num_factura = resultado.get('num_factura', '')
    tipo = resultado.get('tipo', 'COMBUSTIBLE')

    if tipo == 'COMBUSTIBLE':
        for vehiculo, datos in resultado.get('resumen_vehiculos', {}).items():
            if datos['importe_neto'] > 0:
                descripcion = f"{proveedor} Fra.{num_factura} - {datos['litros_gasoil']:.0f}L gasoil"
                if datos['litros_adblue'] > 0:
                    descripcion += f" + {datos['litros_adblue']:.0f}L AdBlue"
                descripcion += f" ({datos['num_repostajes']} rep.)"

                movimientos_db.append({
                    'fecha': fecha,
                    'descripcion': descripcion,
                    'importe': -datos['importe_neto'],  # Negativo porque es gasto
                    'categoria_id': 'COMB',
                    'vehiculo_id': vehiculo,
                    'referencia': num_factura
                })

    elif tipo == 'PEAJES':
        for vehiculo, datos in resultado.get('resumen_vehiculos', {}).items():
            if datos['importe_neto'] > 0:
                descripcion = f"{proveedor} Fra.{num_factura} - Peajes ({datos['num_peajes']} usos)"

                movimientos_db.append({
                    'fecha': fecha,
                    'descripcion': descripcion,
                    'importe': -datos['importe_neto'],  # Negativo porque es gasto
                    'categoria_id': 'PEAJ',
                    'vehiculo_id': vehiculo,
                    'referencia': num_factura
                })

    return movimientos_db
