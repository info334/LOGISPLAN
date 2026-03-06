"""
LogisPLAN - Importador de Costes Laborales
Parsea PDFs de costes laborales con formato COST_YYYYMM_Emp_65.pdf
"""

import re
import pdfplumber
from io import BytesIO


# Mapeo de trabajadores a vehículos
TRABAJADORES = {
    1: {"nombre": "SEVERINO", "vehiculo": "MLB"},
    2: {"nombre": "JOSE MANUEL", "vehiculo": "LVX"},
    3: {"nombre": "CARLOS", "vehiculo": "MJC"},
    4: {"nombre": "JESUS", "vehiculo": "MTY"},
    5: {"nombre": "MERCEDES BEGOÑA", "vehiculo": "COMÚN"},
    8: {"nombre": "SUSANA", "vehiculo": "COMÚN"},
}


def parsear_pdf_costes_laborales(pdf_bytes, filename):
    """
    Parsea un PDF de costes laborales con formato COST_YYYYMM_Emp_65.pdf
    Extrae: nombre, bruto, ss_trabajador, irpf, liquido, ss_empresa, coste_total
    """
    resultados = []
    errores = []

    # Extraer mes del nombre del archivo (formato COST_YYYYMM_... o COST - YYYYMM - ...)
    mes_match = re.search(r'COST[\s_-]+(\d{6})', filename)
    if mes_match:
        year_month = mes_match.group(1)
        mes = f"{year_month[:4]}-{year_month[4:6]}"  # Formato YYYY-MM
    else:
        errores.append(f"No se pudo extraer el mes del nombre del archivo: {filename}")
        return resultados, errores, None

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto_completo += page.extract_text() or ""

            # Buscar líneas que empiecen con números del 1-8 (ID de trabajador)
            lineas = texto_completo.split('\n')

            for linea in lineas:
                linea = linea.strip()
                if not linea:
                    continue

                # Buscar patrón: número al inicio seguido de nombre
                match = re.match(r'^(\d)\s+(.+)', linea)
                if match:
                    trabajador_id = int(match.group(1))

                    if trabajador_id not in TRABAJADORES:
                        continue

                    # Extraer números de la línea (valores monetarios)
                    # Buscar todos los números con decimales
                    numeros = re.findall(r'[\d.,]+', linea)

                    # Filtrar y convertir números
                    valores = []
                    for num in numeros:
                        try:
                            # Convertir formato español a float
                            num_clean = num.replace('.', '').replace(',', '.')
                            val = float(num_clean)
                            if val > 0:  # Solo valores positivos significativos
                                valores.append(val)
                        except ValueError:
                            continue

                    # Estructura esperada: bruto, ss_trab, irpf, liquido, ss_emp, coste_total
                    # El orden puede variar según el PDF
                    if len(valores) >= 6:
                        trabajador_info = TRABAJADORES[trabajador_id]

                        # Asumimos el orden más común en nóminas
                        resultado = {
                            'mes': mes,
                            'trabajador_id': trabajador_id,
                            'nombre': trabajador_info['nombre'],
                            'vehiculo_id': trabajador_info['vehiculo'],
                            'bruto': valores[0] if len(valores) > 0 else 0,
                            'ss_trabajador': valores[1] if len(valores) > 1 else 0,
                            'irpf': valores[2] if len(valores) > 2 else 0,
                            'liquido': valores[3] if len(valores) > 3 else 0,
                            'ss_empresa': valores[4] if len(valores) > 4 else 0,
                            'coste_total': valores[5] if len(valores) > 5 else 0,
                        }
                        resultados.append(resultado)

    except Exception as e:
        errores.append(f"Error procesando PDF: {str(e)}")

    return resultados, errores, mes
