"""
LogisPLAN - Importar Todo
Página centralizada de importación con auto-detección y checklist mensual.
"""

import hashlib
import streamlit as st
import pandas as pd
from datetime import datetime
import re
import pdfplumber
from io import BytesIO

from database import (
    get_connection, insertar_movimientos, insertar_costes_laborales_batch,
    insertar_importacion_tipada, verificar_hash_duplicado, verificar_nombre_duplicado,
    get_importaciones_por_mes, upsert_checklist_documento
)
from importador import (
    parsear_csv_abanca, auto_categorizar, detectar_duplicados,
    validar_importacion, preparar_para_guardado
)
from importador_facturas import (
    parsear_factura_pdf, generar_movimientos_para_db, detectar_tipo_valcarce
)
from importador_costes import parsear_pdf_costes_laborales


# ============== CONSTANTES ==============

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

TIPOS_DOCUMENTO = {
    'EXTRACTO_ABANCA': {
        'nombre': 'Extracto bancario Abanca',
        'icono': '\U0001f3e6',
        'frecuencia': 'Mensual',
        'obligatorio': True,
        'fuente': 'importaciones',
    },
    'FACTURA_STAROIL': {
        'nombre': 'Factura Staroil',
        'icono': '\u26fd',
        'frecuencia': 'Mensual',
        'obligatorio': True,
        'fuente': 'importaciones',
    },
    'FACTURA_SOLRED': {
        'nombre': 'Factura Solred/Waylet',
        'icono': '\u26fd',
        'frecuencia': 'Mensual',
        'obligatorio': True,
        'fuente': 'importaciones',
    },
    'FACTURA_VALCARCE_PEAJES': {
        'nombre': 'Factura Valcarce peajes',
        'icono': '\U0001f6e3\ufe0f',
        'frecuencia': 'Mensual',
        'obligatorio': True,
        'fuente': 'importaciones',
    },
    'COSTES_LABORALES': {
        'nombre': 'Costes laborales',
        'icono': '\U0001f477',
        'frecuencia': 'Mensual',
        'obligatorio': True,
        'fuente': 'costes_laborales',
    },
    'FACTURA_TALLER': {
        'nombre': 'Facturas taller',
        'icono': '\U0001f527',
        'frecuencia': 'Variable',
        'obligatorio': False,
        'fuente': 'movimientos_cat',
        'categoria_id': 'TALL',
    },
    'FACTURA_NEUMATICOS': {
        'nombre': 'Facturas neumaticos',
        'icono': '\U0001f534',
        'frecuencia': 'Variable',
        'obligatorio': False,
        'fuente': 'movimientos_cat',
        'categoria_id': 'NEUM',
    },
    'SEGURO': {
        'nombre': 'Seguros',
        'icono': '\U0001f6e1\ufe0f',
        'frecuencia': 'Trimestral',
        'obligatorio': False,
        'fuente': 'movimientos_cat',
        'categoria_id': 'SEG',
    },
    'LEASING': {
        'nombre': 'Leasing',
        'icono': '\U0001f4c3',
        'frecuencia': 'Mensual',
        'obligatorio': False,
        'fuente': 'movimientos_cat',
        'categoria_id': 'LEAS',
    },
}


# ============== FUNCIONES AUXILIARES ==============

def _formato_importe(valor):
    """Formatea un importe en formato espanol."""
    try:
        val = float(valor)
        return f"{val:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "-"


def calcular_hash(contenido: bytes) -> str:
    """Calcula SHA-256 del contenido del archivo."""
    return hashlib.sha256(contenido).hexdigest()


def detectar_tipo_archivo(contenido: bytes, nombre: str) -> dict:
    """
    Auto-detecta el tipo de archivo por su contenido y nombre.
    Retorna dict con: tipo, nombre_tipo, mes_detectado, error, parsed_data
    """
    resultado = {
        'tipo': None,
        'nombre_tipo': 'Desconocido',
        'mes_detectado': None,
        'error': None,
        'parsed_data': None,
        'resumen': None,
    }

    nombre_upper = nombre.upper()

    # CSV -> Extracto bancario Abanca
    if nombre.lower().endswith('.csv'):
        try:
            df = parsear_csv_abanca(contenido, nombre)
            if len(df) > 0:
                resultado['tipo'] = 'EXTRACTO_ABANCA'
                resultado['nombre_tipo'] = 'Extracto bancario Abanca'
                df = auto_categorizar(df)
                df = detectar_duplicados(df)
                stats = validar_importacion(df)
                resultado['parsed_data'] = {'df': df, 'stats': stats}
                resultado['resumen'] = f"{stats['total_filas']} movimientos"
                # Detectar mes por la moda de fechas
                fechas = pd.to_datetime(df['fecha'], errors='coerce').dropna()
                if len(fechas) > 0:
                    mes_moda = fechas.dt.to_period('M').mode()
                    if len(mes_moda) > 0:
                        resultado['mes_detectado'] = str(mes_moda[0])
            else:
                resultado['error'] = 'CSV vacio o formato no reconocido'
        except Exception as e:
            resultado['error'] = f'Error al parsear CSV: {e}'
        return resultado

    # PDF
    if nombre.lower().endswith('.pdf'):
        # Costes laborales (detectar por nombre de archivo)
        if re.search(r'COST', nombre_upper):
            mes_match = re.search(r'COST[\s_-]+(\d{6})', nombre_upper)
            if mes_match:
                try:
                    resultados_costes, errores_costes, mes = parsear_pdf_costes_laborales(contenido, nombre)
                    resultado['tipo'] = 'COSTES_LABORALES'
                    resultado['nombre_tipo'] = 'Costes laborales'
                    resultado['mes_detectado'] = mes
                    if errores_costes:
                        resultado['error'] = '; '.join(errores_costes)
                    else:
                        resultado['parsed_data'] = {'resultados': resultados_costes, 'mes': mes}
                        total = sum(r.get('coste_total', 0) for r in resultados_costes)
                        resultado['resumen'] = f"{len(resultados_costes)} trabajadores, {_formato_importe(total)}"
                except Exception as e:
                    resultado['error'] = f'Error al parsear costes: {e}'
                return resultado

        # Facturas PDF: detectar proveedor por contenido
        try:
            pdf = pdfplumber.open(BytesIO(contenido))
            texto = ''
            for page in pdf.pages:
                texto += (page.extract_text() or '')
            pdf.close()

            texto_upper = texto.upper()

            if 'STAROIL' in texto_upper:
                resultado['tipo'] = 'FACTURA_STAROIL'
                resultado['nombre_tipo'] = 'Factura Staroil'
            elif 'SOLRED' in texto_upper or 'WAYLET' in texto_upper:
                resultado['tipo'] = 'FACTURA_SOLRED'
                resultado['nombre_tipo'] = 'Factura Solred/Waylet'
            elif 'VALCARCE' in texto_upper:
                tipo_v = detectar_tipo_valcarce(texto)
                if tipo_v == 'PEAJES':
                    resultado['tipo'] = 'FACTURA_VALCARCE_PEAJES'
                    resultado['nombre_tipo'] = 'Factura Valcarce peajes'
                else:
                    resultado['tipo'] = 'FACTURA_VALCARCE_COMB'
                    resultado['nombre_tipo'] = 'Factura Valcarce combustible'
            else:
                resultado['error'] = 'Proveedor PDF no reconocido'
                return resultado

            # Parsear factura
            res = parsear_factura_pdf(contenido, nombre)
            resultado['parsed_data'] = res
            if res.get('errores'):
                resultado['error'] = '; '.join(res['errores'])
            if res.get('fecha_factura'):
                resultado['mes_detectado'] = res['fecha_factura'][:7]
            if res.get('total_factura'):
                resultado['resumen'] = _formato_importe(res['total_factura'])
            elif res.get('movimientos'):
                resultado['resumen'] = f"{len(res['movimientos'])} operaciones"

        except Exception as e:
            resultado['error'] = f'Error al leer PDF: {e}'
    else:
        resultado['error'] = 'Formato no soportado (solo CSV y PDF)'

    return resultado


def obtener_estado_checklist_mes(mes: str) -> list:
    """
    Construye el estado completo del checklist para un mes dado.
    Retorna lista de dicts con: tipo, nombre, icono, frecuencia, obligatorio,
    estado (importado/pendiente/detectado/no_aplica), fecha_importacion, importe
    """
    resultados = []
    conn = get_connection()

    for tipo_key, tipo_info in TIPOS_DOCUMENTO.items():
        item = {
            'tipo': tipo_key,
            'nombre': tipo_info['nombre'],
            'icono': tipo_info['icono'],
            'frecuencia': tipo_info['frecuencia'],
            'obligatorio': tipo_info['obligatorio'],
            'estado': 'pendiente',
            'fecha_importacion': None,
            'importe': None,
        }

        fuente = tipo_info['fuente']

        if fuente == 'importaciones':
            df = pd.read_sql_query("""
                SELECT fecha_importacion, num_movimientos
                FROM importaciones
                WHERE mes_referencia = ? AND tipo = ?
                ORDER BY fecha_importacion DESC LIMIT 1
            """, conn, params=[mes, tipo_key])
            if len(df) > 0:
                item['estado'] = 'importado'
                item['fecha_importacion'] = df.iloc[0]['fecha_importacion']

        elif fuente == 'costes_laborales':
            df = pd.read_sql_query("""
                SELECT COUNT(*) as cnt, SUM(coste_total) as total
                FROM costes_laborales WHERE mes = ?
            """, conn, params=[mes])
            if len(df) > 0 and df.iloc[0]['cnt'] > 0:
                item['estado'] = 'importado'
                item['importe'] = float(df.iloc[0]['total']) if df.iloc[0]['total'] else 0

        elif fuente == 'movimientos_cat':
            cat_id = tipo_info.get('categoria_id')
            fecha_desde = f"{mes}-01"
            year, month_num = int(mes[:4]), int(mes[5:7])
            if month_num == 12:
                fecha_hasta = f"{year + 1}-01-01"
            else:
                fecha_hasta = f"{year}-{month_num + 1:02d}-01"

            df = pd.read_sql_query("""
                SELECT COUNT(*) as cnt, SUM(ABS(importe)) as total
                FROM movimientos
                WHERE categoria_id = ? AND fecha >= ? AND fecha < ?
            """, conn, params=[cat_id, fecha_desde, fecha_hasta])
            if len(df) > 0 and df.iloc[0]['cnt'] > 0:
                item['estado'] = 'detectado'
                item['importe'] = float(df.iloc[0]['total']) if df.iloc[0]['total'] else 0

        # Override manual desde checklist_documentos
        df_manual = pd.read_sql_query("""
            SELECT estado FROM checklist_documentos
            WHERE mes = ? AND tipo_documento = ?
        """, conn, params=[mes, tipo_key])
        if len(df_manual) > 0:
            manual_estado = df_manual.iloc[0]['estado']
            if manual_estado == 'no_aplica':
                item['estado'] = 'no_aplica'

        resultados.append(item)

    conn.close()
    return resultados


# ============== PAGINA PRINCIPAL ==============

def pagina_importar_todo():
    """Pagina centralizada de importacion y control mensual."""

    st.markdown("## \U0001f4e6 Importar Todo")
    st.caption("Importacion centralizada de documentos y control mensual")

    tab_importar, tab_checklist = st.tabs([
        "\U0001f4e5 Importar Documentos",
        "\U0001f4cb Control Mensual"
    ])

    with tab_importar:
        _render_importar_tab()

    with tab_checklist:
        _render_checklist_tab()


# ============== TAB: IMPORTAR DOCUMENTOS ==============

def _render_importar_tab():
    """Tab de importacion con drag & drop multiple y preview."""

    # Inicializar session state
    if 'importar_todo_archivos' not in st.session_state:
        st.session_state.importar_todo_archivos = []
    if 'importar_todo_nombres' not in st.session_state:
        st.session_state.importar_todo_nombres = set()

    archivos = st.file_uploader(
        "Arrastra o selecciona archivos para importar",
        type=['csv', 'pdf'],
        accept_multiple_files=True,
        help="Acepta PDFs de facturas (Staroil, Solred, Valcarce), costes laborales y CSVs de Abanca",
        key="importar_todo_uploader"
    )

    # Procesar archivos nuevos
    if archivos:
        nuevos = [a for a in archivos if a.name not in st.session_state.importar_todo_nombres]

        if nuevos:
            with st.spinner(f"Analizando {len(nuevos)} archivo(s)..."):
                for archivo in nuevos:
                    contenido = archivo.read()
                    file_hash = calcular_hash(contenido)

                    # Detectar tipo
                    tipo_info = detectar_tipo_archivo(contenido, archivo.name)

                    # Verificar duplicados
                    dup_hash = verificar_hash_duplicado(file_hash)
                    dup_nombre = verificar_nombre_duplicado(archivo.name)
                    es_duplicado = bool(dup_hash or dup_nombre)
                    dup_info = None
                    if dup_hash:
                        dup_info = f"Hash identico a importacion #{dup_hash['id']} ({dup_hash['archivo_nombre']})"
                    elif dup_nombre:
                        dup_info = f"Nombre identico a importacion #{dup_nombre['id']}"

                    # Determinar estado
                    if tipo_info.get('error') and not tipo_info.get('tipo'):
                        estado = 'error'
                    elif es_duplicado:
                        estado = 'duplicado'
                    else:
                        estado = 'nuevo'

                    st.session_state.importar_todo_archivos.append({
                        'nombre': archivo.name,
                        'contenido': contenido,
                        'hash': file_hash,
                        'tipo': tipo_info.get('tipo'),
                        'nombre_tipo': tipo_info.get('nombre_tipo', 'Desconocido'),
                        'mes_detectado': tipo_info.get('mes_detectado'),
                        'resumen': tipo_info.get('resumen', '-'),
                        'error': tipo_info.get('error'),
                        'parsed_data': tipo_info.get('parsed_data'),
                        'estado': estado,
                        'dup_info': dup_info,
                        'seleccionado': estado == 'nuevo',
                    })
                    st.session_state.importar_todo_nombres.add(archivo.name)

    # Mostrar preview
    items = st.session_state.importar_todo_archivos
    if not items:
        st.info("Sube archivos PDF o CSV para comenzar la importacion.")
        return

    # Metricas resumen
    n_total = len(items)
    n_nuevos = sum(1 for i in items if i['estado'] == 'nuevo')
    n_dups = sum(1 for i in items if i['estado'] == 'duplicado')
    n_errors = sum(1 for i in items if i['estado'] == 'error')

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Total archivos", n_total)
    col_m2.metric("Nuevos", n_nuevos)
    col_m3.metric("Duplicados", n_dups)
    col_m4.metric("Con errores", n_errors)

    st.markdown("---")
    st.markdown("### Vista previa")

    # Generar opciones de mes para selector
    ahora = datetime.now()
    opciones_mes = []
    for delta in range(-3, 2):
        m = ahora.month + delta
        y = ahora.year
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        opciones_mes.append(f"{y}-{m:02d}")

    # Tabla de archivos
    for idx, item in enumerate(items):
        estado_emoji = {'nuevo': '\u2705', 'duplicado': '\U0001f504', 'error': '\u274c'}.get(item['estado'], '\u2753')
        estado_label = {'nuevo': 'Nuevo', 'duplicado': 'Duplicado', 'error': 'Error'}.get(item['estado'], '?')

        col_check, col_archivo, col_tipo, col_mes, col_resumen, col_estado = st.columns([0.5, 3, 2.5, 1.5, 2, 1.5])

        with col_check:
            items[idx]['seleccionado'] = st.checkbox(
                "Sel", value=item['seleccionado'],
                key=f"sel_{idx}", label_visibility="collapsed"
            )

        with col_archivo:
            st.text(item['nombre'])

        with col_tipo:
            tipo_doc = TIPOS_DOCUMENTO.get(item['tipo'])
            if tipo_doc:
                st.text(f"{tipo_doc['icono']} {item['nombre_tipo']}")
            else:
                st.text(item['nombre_tipo'])

        with col_mes:
            if item['estado'] != 'error':
                default_idx = 0
                if item['mes_detectado'] and item['mes_detectado'] in opciones_mes:
                    default_idx = opciones_mes.index(item['mes_detectado'])
                items[idx]['mes_detectado'] = st.selectbox(
                    "Mes", opciones_mes, index=default_idx,
                    key=f"mes_{idx}", label_visibility="collapsed"
                )
            else:
                st.text("-")

        with col_resumen:
            st.text(item.get('resumen') or '-')

        with col_estado:
            if item['estado'] == 'duplicado':
                st.warning(f"{estado_emoji} {estado_label}", icon="\U0001f504")
            elif item['estado'] == 'error':
                st.error(f"{estado_emoji} {estado_label}", icon="\u274c")
            else:
                st.success(f"{estado_emoji} {estado_label}", icon="\u2705")

        # Mostrar detalles de error o duplicado
        if item.get('error'):
            st.caption(f"\u26a0\ufe0f {item['error']}")
        if item.get('dup_info'):
            st.caption(f"\U0001f504 {item['dup_info']}")

    st.markdown("---")

    # Botones de accion
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        seleccionados = [i for i in items if i['seleccionado'] and i['tipo'] and i['estado'] != 'error']

        if st.button(
            f"\U0001f4e5 Importar seleccionados ({len(seleccionados)})",
            type="primary",
            disabled=len(seleccionados) == 0
        ):
            _ejecutar_importacion(seleccionados)

    with col_btn2:
        if st.button("\U0001f5d1\ufe0f Limpiar todo"):
            st.session_state.importar_todo_archivos = []
            st.session_state.importar_todo_nombres = set()
            st.rerun()


def _ejecutar_importacion(seleccionados):
    """Procesa la importacion de todos los archivos seleccionados."""
    exitos = 0
    errores = []

    progress = st.progress(0, text="Importando...")

    for i, item in enumerate(seleccionados):
        progress.progress((i + 1) / len(seleccionados), text=f"Importando {item['nombre']}...")
        tipo = item['tipo']
        mes = item.get('mes_detectado')

        try:
            if tipo == 'EXTRACTO_ABANCA':
                parsed = item['parsed_data']
                if parsed and 'df' in parsed:
                    movimientos = preparar_para_guardado(parsed['df'])
                    insertar_movimientos(
                        movimientos, item['nombre'],
                        tipo=tipo, hash_archivo=item['hash'], mes_referencia=mes
                    )
                    exitos += 1
                else:
                    errores.append(f"{item['nombre']}: Sin datos parseados")

            elif tipo in ('FACTURA_STAROIL', 'FACTURA_SOLRED',
                          'FACTURA_VALCARCE_COMB', 'FACTURA_VALCARCE_PEAJES'):
                parsed = item['parsed_data']
                if parsed and parsed.get('resumen_vehiculos'):
                    movs = generar_movimientos_para_db(parsed)
                    if movs:
                        insertar_movimientos(
                            movs, item['nombre'],
                            tipo=tipo, hash_archivo=item['hash'], mes_referencia=mes
                        )
                        exitos += 1
                    else:
                        errores.append(f"{item['nombre']}: No se generaron movimientos")
                else:
                    errores.append(f"{item['nombre']}: Sin datos de factura validos")

            elif tipo == 'COSTES_LABORALES':
                parsed = item['parsed_data']
                if parsed and 'resultados' in parsed:
                    num = insertar_costes_laborales_batch(parsed['resultados'])
                    # Crear registro en importaciones (costes no lo crea automaticamente)
                    insertar_importacion_tipada(
                        item['nombre'], num, mes + '-01' if mes else None,
                        mes + '-28' if mes else None,
                        tipo, item['hash'], mes
                    )
                    exitos += 1
                else:
                    errores.append(f"{item['nombre']}: Sin datos de costes validos")

            else:
                errores.append(f"{item['nombre']}: Tipo '{tipo}' no soportado para importacion")

        except Exception as e:
            errores.append(f"{item['nombre']}: {e}")

    progress.empty()

    if exitos > 0:
        st.success(f"\u2705 Importados correctamente: {exitos} archivo(s)")
    if errores:
        for err in errores:
            st.error(f"\u274c {err}")

    # Limpiar estado
    st.session_state.importar_todo_archivos = []
    st.session_state.importar_todo_nombres = set()


# ============== TAB: CONTROL MENSUAL ==============

def _render_checklist_tab():
    """Tab del checklist mensual de importaciones."""

    ahora = datetime.now()

    col_year, col_month = st.columns(2)
    with col_year:
        year = st.selectbox(
            "Ano", range(2024, ahora.year + 2),
            index=ahora.year - 2024, key="checklist_year"
        )
    with col_month:
        month = st.selectbox(
            "Mes", range(1, 13), index=ahora.month - 1,
            format_func=lambda m: MESES_ES[m], key="checklist_month"
        )

    mes = f"{year}-{month:02d}"
    mes_nombre = f"{MESES_ES[month]} {year}"

    st.markdown(f"### {mes_nombre}")

    # Obtener estado
    estado_items = obtener_estado_checklist_mes(mes)

    # Progreso de obligatorios
    obligatorios = [i for i in estado_items if i['obligatorio']]
    completados = sum(1 for i in obligatorios if i['estado'] in ('importado', 'detectado'))
    total_oblig = len(obligatorios)
    pct = completados / total_oblig if total_oblig > 0 else 0

    st.progress(pct)
    st.markdown(f"**{mes_nombre}: {completados}/{total_oblig} documentos obligatorios importados ({pct * 100:.0f}%)**")

    # Alerta si faltan documentos del mes anterior
    if ahora.day > 5:
        # Calcular mes anterior
        prev_m = ahora.month - 1
        prev_y = ahora.year
        if prev_m < 1:
            prev_m = 12
            prev_y -= 1
        mes_prev = f"{prev_y}-{prev_m:02d}"

        if mes == mes_prev:
            pendientes_oblig = [i for i in obligatorios if i['estado'] == 'pendiente']
            if pendientes_oblig:
                nombres = ", ".join(i['nombre'] for i in pendientes_oblig)
                st.warning(
                    f"\u26a0\ufe0f Estamos a dia {ahora.day} y faltan {len(pendientes_oblig)} "
                    f"documento(s) obligatorio(s) del mes anterior: {nombres}"
                )

    st.markdown("---")

    # Cabecera de tabla
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([0.5, 3, 1.5, 2, 2, 1.5])
    col_h1.markdown("**Estado**")
    col_h2.markdown("**Documento**")
    col_h3.markdown("**Frecuencia**")
    col_h4.markdown("**Fecha importacion**")
    col_h5.markdown("**Importe**")
    col_h6.markdown("**Acciones**")

    # Filas
    for item in estado_items:
        estado = item['estado']
        estado_emoji = {
            'importado': '\u2705',
            'pendiente': '\u274c',
            'detectado': '\u26a0\ufe0f',
            'no_aplica': '\u2796',
        }.get(estado, '\u2753')

        col1, col2, col3, col4, col5, col6 = st.columns([0.5, 3, 1.5, 2, 2, 1.5])

        with col1:
            st.markdown(estado_emoji)

        with col2:
            st.markdown(f"{item['icono']} {item['nombre']}")

        with col3:
            st.caption(item['frecuencia'])

        with col4:
            if item['fecha_importacion']:
                try:
                    fecha_dt = datetime.fromisoformat(item['fecha_importacion'])
                    st.caption(fecha_dt.strftime('%d/%m/%Y'))
                except (ValueError, TypeError):
                    st.caption(str(item['fecha_importacion'])[:10])
            else:
                st.caption("\u2014")

        with col5:
            if item['importe']:
                st.caption(_formato_importe(item['importe']))
            else:
                st.caption("\u2014")

        with col6:
            if estado == 'pendiente' and not item['obligatorio']:
                if st.button("N/A", key=f"na_{item['tipo']}_{mes}",
                             help="Marcar como no aplica este mes"):
                    upsert_checklist_documento(mes, item['tipo'], 'no_aplica')
                    st.rerun()
            elif estado == 'no_aplica':
                if st.button("Reactivar", key=f"react_{item['tipo']}_{mes}",
                             help="Volver a marcar como pendiente"):
                    upsert_checklist_documento(mes, item['tipo'], 'pendiente')
                    st.rerun()
            elif estado == 'pendiente':
                st.caption("Importar")
            elif estado in ('importado', 'detectado'):
                st.caption("OK")

    # Historico
    st.markdown("---")
    with st.expander("\U0001f4ca Historico de meses anteriores"):
        _render_historico(ahora)


def _render_historico(ahora):
    """Muestra resumen de los ultimos 6 meses."""
    meses_hist = []
    for delta in range(1, 7):
        m = ahora.month - delta
        y = ahora.year
        while m < 1:
            m += 12
            y -= 1
        meses_hist.append(f"{y}-{m:02d}")

    for mes_h in meses_hist:
        year_h, month_h = int(mes_h[:4]), int(mes_h[5:7])
        nombre_mes = f"{MESES_ES[month_h]} {year_h}"

        estado_items = obtener_estado_checklist_mes(mes_h)
        obligatorios = [i for i in estado_items if i['obligatorio']]
        completados = sum(1 for i in obligatorios if i['estado'] in ('importado', 'detectado'))
        total_oblig = len(obligatorios)
        pct = completados / total_oblig if total_oblig > 0 else 0

        col_hist1, col_hist2 = st.columns([2, 3])
        with col_hist1:
            st.markdown(f"**{nombre_mes}**: {completados}/{total_oblig}")
        with col_hist2:
            st.progress(pct)
