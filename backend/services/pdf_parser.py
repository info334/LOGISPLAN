"""
LogisPLAN - PDF Parser for labor costs, route reports and fuel invoices
"""
import re
from datetime import datetime
import pdfplumber

# Worker ID → vehicle assignment
WORKER_VEHICLE = {
    1: "COMÚN",      # Severino Admin
    2: "LVX",        # José Manuel
    3: "MJC",        # Carlos
    4: "MTY",        # Jesús
    5: "MLB",        # Mercedes
    8: "COMÚN",      # Susana
    9: "MLB",        # Severino
}

MESES_MAP = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
}


def parse_number(s: str) -> float:
    """Parse Spanish-formatted number: 1.234,56 → 1234.56"""
    s = s.strip()
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def extract_pdf_text(file_path: str) -> str:
    """Extract full text from a PDF using pdfplumber."""
    with pdfplumber.open(file_path) as pdf:
        pages = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return "\n".join(pages)


def parse_costes_laborales(file_path: str) -> dict:
    """
    Parse a labor costs PDF (COST - YYYYMM - Emp XX.pdf).
    Returns: { mes: "YYYY-MM", trabajadores: [{ trabajador_id, nombre, vehiculo_id, bruto, ss_trabajador, irpf, liquido, ss_empresa, coste_total }] }
    """
    full_text = extract_pdf_text(file_path)
    lines = full_text.split("\n")

    # Extract period: "Periodo 2026: ENERO/ENERO"
    mes = None
    for line in lines:
        m = re.search(r"Periodo\s+(\d{4}):\s*(\w+)", line)
        if m:
            year = m.group(1)
            month_name = m.group(2).upper()
            month_num = MESES_MAP.get(month_name)
            if month_num:
                mes = f"{year}-{month_num}"
            break

    if not mes:
        raise ValueError("No se pudo detectar el periodo del PDF")

    trabajadores = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("TOTAL") or line.startswith("MES ") or line.startswith("EMPRESA"):
            continue

        # Try simpler approach: find lines starting with a digit followed by a name
        m = re.match(r"^(\d+)\s+(.+)", line)
        if not m:
            continue

        worker_id = int(m.group(1))
        rest = m.group(2).strip()

        # Extract all Spanish numbers from the line
        numbers = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", rest)
        if len(numbers) < 2:
            continue

        # Extract name (everything before the first number)
        first_num_pos = rest.find(numbers[0])
        name_raw = rest[:first_num_pos].strip().rstrip(",").strip()

        # Normalize name: "APELLIDO1 APELLIDO2, NOMBRE" → "Nombre Apellido1 Apellido2"
        if "," in name_raw:
            parts = name_raw.split(",", 1)
            apellidos = parts[0].strip().title()
            nombre = parts[1].strip().title()
            name = f"{nombre} {apellidos}"
        else:
            name = name_raw.title()

        nums = [parse_number(n) for n in numbers]

        # The PDF columns are: BRUTO, SS.TRA, IRPF, LIQUIDO, SS.EMP, ..., COSTE
        # But some columns may be empty (0). The last number is always COSTE TRAB.
        # and BRUTO is always the first.
        bruto = nums[0]
        coste_total = nums[-1]

        # Try to identify the columns based on count
        ss_trabajador = 0.0
        irpf = 0.0
        liquido = 0.0
        ss_empresa = 0.0

        if len(nums) >= 6:
            ss_trabajador = nums[1]
            # Check if bruto - ss_trab ≈ nums[2] → no IRPF (LIQUIDO is nums[2])
            if abs(bruto - nums[1] - nums[2]) < 1:
                liquido = nums[2]
                ss_empresa = nums[3]
            else:
                irpf = nums[2]
                liquido = nums[3]
                ss_empresa = nums[4]
        elif len(nums) == 5:
            # Missing IRPF or SS_EMP
            ss_trabajador = nums[1]
            # Check if bruto - ss_trab ≈ nums[2] (no IRPF, so liquido = bruto - ss_trab)
            if abs(bruto - nums[1] - nums[2]) < 1:
                # No IRPF: BRUTO, SS_TRAB, LIQUIDO, SS_EMP, COSTE
                liquido = nums[2]
                ss_empresa = nums[3]
            else:
                # Has IRPF: BRUTO, SS_TRAB, IRPF, LIQUIDO, COSTE (no SS_EMP)
                irpf = nums[2]
                liquido = nums[3]
        elif len(nums) == 4:
            # BRUTO, IRPF, LIQUIDO, COSTE (admin pattern)
            if abs(bruto - nums[1] - nums[2]) < 1:
                irpf = nums[1]
                liquido = nums[2]
            else:
                ss_trabajador = nums[1]
                liquido = nums[2]
        elif len(nums) == 3:
            # BRUTO, LIQUIDO, COSTE
            liquido = nums[1]

        vehiculo_id = WORKER_VEHICLE.get(worker_id, "COMÚN")

        trabajadores.append({
            "trabajador_id": worker_id,
            "nombre": name,
            "vehiculo_id": vehiculo_id,
            "bruto": bruto,
            "ss_trabajador": ss_trabajador,
            "irpf": irpf,
            "liquido": liquido,
            "ss_empresa": ss_empresa,
            "coste_total": coste_total,
        })

    return {"mes": mes, "trabajadores": trabajadores}


def parse_recorridos(file_path: str) -> dict:
    """
    Parse a Localiza route report PDF.
    Returns: { vehiculo_id: "MJC", mes: "YYYY-MM", km_total: 6085.5, dias_trabajados: 20 }
    """
    full_text = extract_pdf_text(file_path)
    # Clean null bytes and weird chars
    full_text = full_text.replace("\x00", "")
    lines = full_text.split("\n")

    # Extract vehicle: "Dispositivo MJC" or "Disposi vo MJC" (null byte removed)
    vehiculo_id = None
    for line in lines:
        m = re.search(r"Disposi\w*vo\s+(\w+)", line, re.IGNORECASE)
        if m:
            vehiculo_id = m.group(1).upper()
            break

    # Extract date range: "Inicio 01/02/2026"
    mes = None
    for line in lines:
        m = re.search(r"Inicio\s+(\d{2})/(\d{2})/(\d{4})", line)
        if m:
            mes = f"{m.group(3)}-{m.group(2)}"
            break

    # Extract total km: "Total vehículo ... 6085,5 ..."
    km_total = 0.0
    for line in lines:
        m = re.search(r"Total\s+veh[ií]culo.*?([\d.]+,\d+)", line, re.IGNORECASE)
        if m:
            km_total = parse_number(m.group(1))
            break

    # Count working days: "Total día" lines
    dias = 0
    for line in lines:
        if re.search(r"Total\s+d[ií]a", line, re.IGNORECASE):
            dias += 1

    if not vehiculo_id:
        raise ValueError("No se pudo detectar el vehiculo del PDF")
    if not mes:
        raise ValueError("No se pudo detectar el mes del PDF")

    return {
        "vehiculo_id": vehiculo_id,
        "mes": mes,
        "km_total": km_total,
        "dias_trabajados": dias,
    }


# =========================================================
#  SOLRED / fuel invoices
# =========================================================

MATRICULAS_VEHICLE = {
    "1257MTY": "MTY", "9245MJC": "MJC", "1382LVX": "LVX", "0245MLB": "MLB",
}


def parse_gasoil_solred(file_path: str) -> dict:
    """
    Parse a SOLRED fuel invoice PDF.
    Extracts per-vehicle totals from the detailed card operations pages.
    Returns: {
        factura: "A260094454",
        mes: "2026-01",
        fecha_desde: "2026-01-16",
        fecha_hasta: "2026-01-31",
        vehiculos: { "MJC": 1297.22, "LVX": 1716.20, ... },
        total: 3569.97,
    }
    """
    full_text = extract_pdf_text(file_path)
    lines = full_text.split("\n")

    # Extract invoice number
    factura = None
    m = re.search(r"Factura\s+([A-Z]{1,3}\d{6,})", full_text)
    if m:
        factura = m.group(1)

    # Extract date range: "Fecha de operación DD/MM/YYYY AL DD/MM/YYYY"
    # Text may have no spaces: "Fechadeoperación 16/01/2026AL31/01/2026"
    fecha_desde = None
    fecha_hasta = None
    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*AL\s*(\d{2}/\d{2}/\d{4})", full_text)
    if m:
        fecha_desde = datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
        fecha_hasta = datetime.strptime(m.group(2), "%d/%m/%Y").strftime("%Y-%m-%d")

    mes = fecha_hasta[:7] if fecha_hasta else None

    # Parse per-vehicle totals from detailed operation pages
    # Pattern: "Nº de Matrícula XXXX-YYY" followed by "Total en Euros NNN"
    current_vehicle = None
    vehiculos = {}

    for line in lines:
        # Match matricula line
        m = re.search(r"Matr[ií]cula\s+(\d{4}[-]?\s*[A-Z]{3})", line)
        if m:
            mat = m.group(1).replace("-", "").replace(" ", "")
            current_vehicle = MATRICULAS_VEHICLE.get(mat)

        # Match total per card
        if current_vehicle and "Total en Euros" in line:
            m = re.search(r"Total\s+en\s+Euros\s+([\d.,]+)", line)
            if m:
                total = parse_number(m.group(1))
                vehiculos[current_vehicle] = vehiculos.get(current_vehicle, 0) + total
                current_vehicle = None

    if not vehiculos:
        raise ValueError("No se encontraron datos por vehiculo en el PDF de SOLRED")

    total = round(sum(vehiculos.values()), 2)

    return {
        "factura": factura,
        "mes": mes,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "vehiculos": {k: round(v, 2) for k, v in vehiculos.items()},
        "total": total,
    }
