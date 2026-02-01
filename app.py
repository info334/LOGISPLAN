"""
LogisPLAN - Dashboard Gestión Flota Severino Logística
Aplicación principal Streamlit
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# Importar módulos propios
from database import (
    init_database, get_vehiculos, get_categorias, get_movimientos,
    insertar_movimientos, get_vehiculos_operativos
)
from importador import (
    parsear_csv_abanca, auto_categorizar, preparar_para_guardado,
    validar_importacion, detectar_duplicados
)
from importador_facturas import parsear_factura_pdf, generar_movimientos_para_db

# ============== CONFIGURACIÓN DE PÁGINA ==============

st.set_page_config(
    page_title="LogisPLAN - Severino Logística",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar base de datos
init_database()

# ============== ESTILOS CSS ==============

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f4e79;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    .split-box {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ============== NAVEGACIÓN SIDEBAR ==============

def render_sidebar():
    """Renderiza la barra lateral de navegación."""
    # Logo de Severino Logística
    import os
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    logo_placeholder = os.path.join(os.path.dirname(__file__), "assets", "logo_placeholder.png")

    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, use_container_width=True)
    elif os.path.exists(logo_placeholder):
        st.sidebar.image(logo_placeholder, use_container_width=True)
        st.sidebar.caption("📷 Guarda tu logo en assets/logo.png")
    else:
        st.sidebar.markdown("## 🚚 LogisPLAN")

    st.sidebar.markdown("---")

    paginas = {
        "🏠 Resumen": "resumen",
        "🚛 Por Vehículo": "vehiculo",
        "📥 Importar CSV": "importar",
        "⛽ Combustible/Peajes": "facturas",
        "⚙️ Configuración": "config"
    }

    seleccion = st.sidebar.radio(
        "Navegación",
        options=list(paginas.keys()),
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(f"v1.0 | {datetime.now().strftime('%Y')}")

    return paginas[seleccion]


# ============== FUNCIONES AUXILIARES ==============

def formato_importe_es(valor):
    """Formatea un importe en formato español."""
    try:
        val = float(valor)
        return f"{val:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(valor)


# ============== PÁGINA: IMPORTAR CSV ==============

def pagina_importar():
    """Vista de importación de extractos bancarios CSV."""

    st.markdown('<p class="main-header">📥 Importar Extracto Bancario</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Carga extractos CSV de Abanca para categorizar movimientos</p>', unsafe_allow_html=True)

    # Estado de sesión
    if 'df_importacion' not in st.session_state:
        st.session_state.df_importacion = None
    if 'stats_importacion' not in st.session_state:
        st.session_state.stats_importacion = None
    if 'movimientos_split' not in st.session_state:
        st.session_state.movimientos_split = {}  # {idx: [{vehiculo, importe}, ...]}

    # File uploader
    archivo = st.file_uploader(
        "Selecciona archivo CSV",
        type=['csv'],
        help="Formato Abanca: F. VALOR;F. CONTABLE;...;IMPORTE;SALDO;DIVISA"
    )

    if archivo is not None and st.session_state.df_importacion is None:
        try:
            with st.spinner("Procesando archivo..."):
                df = parsear_csv_abanca(archivo.read(), archivo.name)
                df = auto_categorizar(df)
                df = detectar_duplicados(df)
                stats = validar_importacion(df)

                st.session_state.df_importacion = df
                st.session_state.stats_importacion = stats
                st.session_state.movimientos_split = {}
                st.rerun()

        except Exception as e:
            import traceback
            st.error(f"Error al procesar archivo: {e}")
            st.code(traceback.format_exc())
            return

    # Mostrar resultados si hay datos
    if st.session_state.df_importacion is not None:
        df = st.session_state.df_importacion.copy()
        stats = st.session_state.stats_importacion

        # Estadísticas
        st.markdown("### 📊 Resumen de Importación")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Movimientos", stats['total_filas'])
        with col2:
            st.metric("Ingresos", formato_importe_es(stats['suma_ingresos']), delta=f"{stats['ingresos']} mov.")
        with col3:
            st.metric("Gastos", formato_importe_es(stats['suma_gastos']), delta=f"{stats['gastos']} mov.")
        with col4:
            st.metric("Necesitan Revisión", int(stats['necesitan_revision']),
                     delta="⚠️" if stats['necesitan_revision'] > 0 else "✅")

        if stats['advertencias']:
            for adv in stats['advertencias']:
                st.warning(adv)

        if stats['periodo_desde'] and stats['periodo_hasta']:
            st.info(f"📅 Periodo: {stats['periodo_desde']} a {stats['periodo_hasta']}")

        duplicados = int(df['posible_duplicado'].astype(bool).sum())
        if duplicados > 0:
            st.warning(f"⚠️ Se detectaron {duplicados} posibles duplicados")

        st.markdown("---")

        # Obtener opciones
        vehiculos_df = get_vehiculos()
        categorias_df = get_categorias()
        vehiculo_options = ['', 'COMÚN'] + [v for v in vehiculos_df['id'].tolist() if v != 'COMÚN']
        categoria_options = categorias_df['id'].tolist()

        # Tabs para vista normal y dividir movimientos
        tab1, tab2 = st.tabs(["📝 Asignar Categorías", "✂️ Dividir Movimientos"])

        with tab1:
            st.markdown("### Movimientos a Importar")
            st.caption("Selecciona categoría y vehículo para cada movimiento. ⚠️ indica que necesita revisión.")

            # Mostrar cada movimiento con selectores
            for idx in df.index:
                row = df.loc[idx]
                importe = float(row['importe'])
                es_gasto = importe < 0
                necesita_rev = bool(row['necesita_revision'])
                es_dup = bool(row['posible_duplicado'])

                # Verificar si está dividido
                esta_dividido = idx in st.session_state.movimientos_split

                # Icono de estado
                if esta_dividido:
                    estado = "✂️"
                elif necesita_rev:
                    estado = "⚠️"
                elif es_dup:
                    estado = "🔄"
                else:
                    estado = "✅"

                with st.container():
                    col_estado, col_fecha, col_desc, col_importe, col_cat, col_veh = st.columns([0.5, 1, 4, 1.5, 1.5, 1.5])

                    with col_estado:
                        st.write(estado)

                    with col_fecha:
                        st.write(row['fecha'])

                    with col_desc:
                        desc_text = str(row['descripcion'])[:60]
                        if len(str(row['descripcion'])) > 60:
                            desc_text += "..."
                        st.write(desc_text)

                    with col_importe:
                        color = "red" if es_gasto else "green"
                        st.markdown(f"<span style='color:{color}'>{formato_importe_es(importe)}</span>", unsafe_allow_html=True)

                    with col_cat:
                        if not esta_dividido:
                            cat_actual = row['categoria_id'] if row['categoria_id'] else ''
                            cat_idx = categoria_options.index(cat_actual) if cat_actual in categoria_options else 0
                            nueva_cat = st.selectbox(
                                "Cat",
                                options=categoria_options,
                                index=cat_idx,
                                key=f"cat_{idx}",
                                label_visibility="collapsed"
                            )
                            df.at[idx, 'categoria_id'] = nueva_cat
                        else:
                            st.write("(dividido)")

                    with col_veh:
                        if not esta_dividido:
                            veh_actual = row['vehiculo_id'] if row['vehiculo_id'] else ''
                            veh_idx = vehiculo_options.index(veh_actual) if veh_actual in vehiculo_options else 0
                            nuevo_veh = st.selectbox(
                                "Veh",
                                options=vehiculo_options,
                                index=veh_idx,
                                key=f"veh_{idx}",
                                label_visibility="collapsed"
                            )
                            df.at[idx, 'vehiculo_id'] = nuevo_veh if nuevo_veh else None
                        else:
                            st.write("(dividido)")

                    st.markdown("<hr style='margin:2px 0; border:none; border-top:1px solid #eee;'>", unsafe_allow_html=True)

            # Actualizar session state
            st.session_state.df_importacion = df

        with tab2:
            st.markdown("### ✂️ Dividir Movimientos entre Vehículos")
            st.caption("Selecciona un movimiento para dividir su importe entre varios vehículos (ej: un ingreso de cliente para varios camiones)")

            # Selector de movimiento a dividir
            movimientos_para_dividir = []
            for idx in df.index:
                row = df.loc[idx]
                desc = str(row['descripcion'])[:40]
                importe = float(row['importe'])
                movimientos_para_dividir.append(f"{idx}: {row['fecha']} | {desc} | {formato_importe_es(importe)}")

            mov_seleccionado = st.selectbox(
                "Selecciona movimiento a dividir",
                options=movimientos_para_dividir,
                key="mov_dividir"
            )

            if mov_seleccionado:
                idx_sel = int(mov_seleccionado.split(":")[0])
                row_sel = df.loc[idx_sel]
                importe_total = float(row_sel['importe'])
                categoria_mov = row_sel['categoria_id']

                st.markdown(f"**Movimiento:** {row_sel['descripcion']}")
                st.markdown(f"**Importe total:** {formato_importe_es(importe_total)}")
                st.markdown(f"**Categoría:** {categoria_mov}")

                st.markdown("---")
                st.markdown("**Dividir entre vehículos:**")

                # Vehículos operativos (sin COMÚN)
                vehiculos_ops = [v for v in vehiculos_df['id'].tolist() if v != 'COMÚN']

                # Inicializar splits si no existen
                if idx_sel not in st.session_state.movimientos_split:
                    st.session_state.movimientos_split[idx_sel] = []

                # Inputs para cada vehículo
                splits_actuales = {}
                total_asignado = 0.0

                for veh in vehiculos_ops:
                    # Buscar valor existente
                    valor_existente = 0.0
                    for split in st.session_state.movimientos_split.get(idx_sel, []):
                        if split['vehiculo'] == veh:
                            valor_existente = split['importe']
                            break

                    col_veh_name, col_veh_input = st.columns([1, 2])
                    with col_veh_name:
                        st.write(f"**{veh}:**")
                    with col_veh_input:
                        valor = st.number_input(
                            f"Importe {veh}",
                            value=valor_existente,
                            step=100.0,
                            key=f"split_{idx_sel}_{veh}",
                            label_visibility="collapsed"
                        )
                        if valor != 0:
                            splits_actuales[veh] = valor
                            total_asignado += valor

                # Mostrar resumen
                diferencia = importe_total - total_asignado
                st.markdown("---")
                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.metric("Total original", formato_importe_es(importe_total))
                with col_res2:
                    st.metric("Total asignado", formato_importe_es(total_asignado))
                with col_res3:
                    color = "green" if abs(diferencia) < 0.01 else "red"
                    st.metric("Diferencia", formato_importe_es(diferencia))

                # Botón para guardar división
                col_btn_split1, col_btn_split2 = st.columns(2)
                with col_btn_split1:
                    if st.button("✅ Aplicar división", key=f"aplicar_split_{idx_sel}"):
                        if abs(diferencia) > 0.01:
                            st.error("La suma de los importes debe ser igual al total")
                        else:
                            # Guardar splits
                            nuevos_splits = []
                            for veh, imp in splits_actuales.items():
                                if imp != 0:
                                    nuevos_splits.append({
                                        'vehiculo': veh,
                                        'importe': imp,
                                        'categoria': categoria_mov
                                    })
                            st.session_state.movimientos_split[idx_sel] = nuevos_splits
                            st.success(f"División aplicada: {len(nuevos_splits)} partes")
                            st.rerun()

                with col_btn_split2:
                    if idx_sel in st.session_state.movimientos_split and st.session_state.movimientos_split[idx_sel]:
                        if st.button("🗑️ Quitar división", key=f"quitar_split_{idx_sel}"):
                            del st.session_state.movimientos_split[idx_sel]
                            st.success("División eliminada")
                            st.rerun()

                # Mostrar divisiones actuales
                if st.session_state.movimientos_split.get(idx_sel):
                    st.markdown("**División actual:**")
                    for split in st.session_state.movimientos_split[idx_sel]:
                        st.write(f"- {split['vehiculo']}: {formato_importe_es(split['importe'])}")

        st.markdown("---")

        # Botones de acción principales
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])

        with col_btn1:
            if st.button("💾 Guardar Importación", type="primary", use_container_width=True):
                # Preparar movimientos finales
                movimientos_finales = []

                for idx in df.index:
                    row = df.loc[idx]

                    # Verificar si está dividido
                    if idx in st.session_state.movimientos_split and st.session_state.movimientos_split[idx]:
                        # Crear un movimiento por cada split
                        for split in st.session_state.movimientos_split[idx]:
                            movimientos_finales.append({
                                'fecha': row['fecha'],
                                'descripcion': row['descripcion'],
                                'importe': split['importe'],
                                'categoria_id': split['categoria'],
                                'vehiculo_id': split['vehiculo'],
                                'referencia': row.get('referencia'),
                            })
                    else:
                        # Movimiento normal
                        movimientos_finales.append({
                            'fecha': row['fecha'],
                            'descripcion': row['descripcion'],
                            'importe': row['importe'],
                            'categoria_id': row['categoria_id'],
                            'vehiculo_id': row['vehiculo_id'] if row['vehiculo_id'] else None,
                            'referencia': row.get('referencia'),
                        })

                # Verificar gastos sin vehículo
                gastos_sin_vehiculo = [m for m in movimientos_finales
                                       if float(m['importe']) < 0
                                       and not m['vehiculo_id']
                                       and m['categoria_id'] != 'INGRESO']

                if gastos_sin_vehiculo:
                    st.error(f"Hay {len(gastos_sin_vehiculo)} gastos sin vehículo asignado.")
                else:
                    importacion_id = insertar_movimientos(movimientos_finales, archivo.name if archivo else "manual")
                    st.success(f"✅ Importación #{importacion_id} guardada. {len(movimientos_finales)} movimientos.")

                    # Limpiar estado
                    st.session_state.df_importacion = None
                    st.session_state.stats_importacion = None
                    st.session_state.movimientos_split = {}
                    st.rerun()

        with col_btn2:
            if st.button("🗑️ Cancelar", use_container_width=True):
                st.session_state.df_importacion = None
                st.session_state.stats_importacion = None
                st.session_state.movimientos_split = {}
                st.rerun()

        # Info categorías
        with st.expander("ℹ️ Información sobre categorías y vehículos"):
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown("**Categorías:**")
                for _, cat in categorias_df.iterrows():
                    st.markdown(f"- **{cat['id']}**: {cat['nombre']}")
            with col_info2:
                st.markdown("**Vehículos:**")
                for _, veh in vehiculos_df.iterrows():
                    amort_val = float(veh['amortizacion_mensual']) if veh['amortizacion_mensual'] else 0
                    amort = f"({amort_val:,.0f} €/mes)" if amort_val > 0 else ""
                    st.markdown(f"- **{veh['id']}**: {veh['descripcion']} {amort}")


# ============== PÁGINA: RESUMEN ==============

def pagina_resumen():
    """Vista de resumen general."""
    st.markdown('<p class="main-header">🏠 Resumen</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Dashboard consolidado de la flota</p>', unsafe_allow_html=True)

    movimientos = get_movimientos()

    if len(movimientos) == 0:
        st.info("📭 No hay movimientos importados. Ve a la sección **Importar** para cargar datos.")
        return

    st.info("🚧 Vista en desarrollo. Próximamente: KPIs, gráficos de barras y evolución mensual.")


# ============== PÁGINA: POR VEHÍCULO ==============

def pagina_vehiculo():
    """Vista de análisis por vehículo."""
    st.markdown('<p class="main-header">🚛 Análisis por Vehículo</p>', unsafe_allow_html=True)

    vehiculos = get_vehiculos_operativos()

    if len(vehiculos) == 0:
        st.error("No hay vehículos configurados")
        return

    vehiculo_sel = st.selectbox(
        "Selecciona vehículo",
        options=vehiculos['id'].tolist(),
        format_func=lambda x: f"{x} - {vehiculos[vehiculos['id']==x]['descripcion'].values[0]}"
    )

    st.info(f"🚧 Vista P&L detallado para **{vehiculo_sel}** en desarrollo.")


# ============== PÁGINA: CONFIGURACIÓN ==============

def pagina_config():
    """Vista de configuración."""
    st.markdown('<p class="main-header">⚙️ Configuración</p>', unsafe_allow_html=True)
    st.info("🚧 Configuración de amortizaciones y reglas de categorización en desarrollo.")


# ============== PÁGINA: FACTURAS COMBUSTIBLE/PEAJES ==============

def pagina_facturas():
    """Vista de importación de facturas de combustible y peajes PDF."""

    st.markdown('<p class="main-header">⛽ Facturas Combustible y Peajes</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Importa facturas PDF de StarOil, Solred/Waylet y Valcarce</p>', unsafe_allow_html=True)

    # Estado de sesión para facturas
    if 'facturas_procesadas' not in st.session_state:
        st.session_state.facturas_procesadas = []

    # File uploader para múltiples PDFs
    archivos = st.file_uploader(
        "Selecciona facturas PDF",
        type=['pdf'],
        accept_multiple_files=True,
        help="Puedes seleccionar múltiples facturas PDF de StarOil, Solred/Waylet o Valcarce"
    )

    # Procesar nuevos archivos
    if archivos:
        nombres_procesados = [f['nombre'] for f in st.session_state.facturas_procesadas]
        nuevos_archivos = [a for a in archivos if a.name not in nombres_procesados]

        if nuevos_archivos:
            with st.spinner(f"Procesando {len(nuevos_archivos)} factura(s)..."):
                for archivo in nuevos_archivos:
                    try:
                        resultado = parsear_factura_pdf(archivo.read(), archivo.name)
                        resultado['nombre'] = archivo.name
                        st.session_state.facturas_procesadas.append(resultado)
                    except Exception as e:
                        st.error(f"Error procesando {archivo.name}: {e}")

            st.rerun()

    # Mostrar facturas procesadas
    if st.session_state.facturas_procesadas:
        st.markdown("### 📋 Facturas Procesadas")

        for i, factura in enumerate(st.session_state.facturas_procesadas):
            tipo = factura.get('tipo', 'COMBUSTIBLE')
            icono = "⛽" if tipo == 'COMBUSTIBLE' else "🛣️"

            with st.expander(f"{icono} {factura['nombre']} - {factura['proveedor']} ({tipo})", expanded=True):
                # Información general
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Proveedor", factura['proveedor'])
                with col2:
                    st.metric("Fecha", factura.get('fecha_factura', 'N/D'))
                with col3:
                    st.metric("Nº Factura", factura.get('num_factura', 'N/D'))
                with col4:
                    total = factura.get('total_factura', 0)
                    st.metric("Total", formato_importe_es(total))

                # Errores
                if factura.get('errores'):
                    for error in factura['errores']:
                        st.error(error)

                # Resumen por vehículo
                if factura.get('resumen_vehiculos'):
                    st.markdown("#### 🚛 Resumen por Vehículo")

                    if tipo == 'COMBUSTIBLE':
                        # Tabla para combustible
                        datos_tabla = []
                        for vehiculo, datos in factura['resumen_vehiculos'].items():
                            datos_tabla.append({
                                'Vehículo': vehiculo,
                                'Litros Gasoil': f"{datos['litros_gasoil']:,.1f} L",
                                'Litros AdBlue': f"{datos['litros_adblue']:,.1f} L" if datos['litros_adblue'] > 0 else '-',
                                'Repostajes': datos.get('num_repostajes', 0),
                                'Descuento': formato_importe_es(datos['descuento_total']) if datos['descuento_total'] > 0 else '-',
                                'Importe Neto': formato_importe_es(datos['importe_neto']),
                                '€/Litro': f"{datos['precio_medio_litro']:.3f} €" if datos['precio_medio_litro'] > 0 else '-'
                            })

                        if datos_tabla:
                            df_tabla = pd.DataFrame(datos_tabla)
                            st.dataframe(df_tabla, use_container_width=True, hide_index=True)

                            # Totales combustible
                            total_litros_gasoil = sum(d['litros_gasoil'] for d in factura['resumen_vehiculos'].values())
                            total_litros_adblue = sum(d['litros_adblue'] for d in factura['resumen_vehiculos'].values())
                            total_importe_neto = sum(d['importe_neto'] for d in factura['resumen_vehiculos'].values())
                            total_descuento = sum(d['descuento_total'] for d in factura['resumen_vehiculos'].values())

                            st.markdown("---")
                            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                            with col_t1:
                                st.metric("Total Gasoil", f"{total_litros_gasoil:,.0f} L")
                            with col_t2:
                                st.metric("Total AdBlue", f"{total_litros_adblue:,.0f} L")
                            with col_t3:
                                st.metric("Total Descuentos", formato_importe_es(total_descuento))
                            with col_t4:
                                st.metric("Total Neto", formato_importe_es(total_importe_neto))

                    else:  # PEAJES
                        # Tabla para peajes
                        datos_tabla = []
                        for vehiculo, datos in factura['resumen_vehiculos'].items():
                            datos_tabla.append({
                                'Vehículo': vehiculo,
                                'Nº Peajes': datos.get('num_peajes', 0),
                                'Peajes': formato_importe_es(datos.get('importe_peajes', 0)),
                                'Bonificaciones': formato_importe_es(datos.get('importe_bonificaciones', 0)),
                                'Comisiones': formato_importe_es(datos.get('importe_comisiones', 0)),
                                'Total Neto': formato_importe_es(datos['importe_neto'])
                            })

                        if datos_tabla:
                            df_tabla = pd.DataFrame(datos_tabla)
                            st.dataframe(df_tabla, use_container_width=True, hide_index=True)

                            # Totales peajes
                            total_peajes = sum(d.get('num_peajes', 0) for d in factura['resumen_vehiculos'].values())
                            total_importe_peajes = sum(d.get('importe_peajes', 0) for d in factura['resumen_vehiculos'].values())
                            total_bonificaciones = sum(d.get('importe_bonificaciones', 0) for d in factura['resumen_vehiculos'].values())
                            total_importe_neto = sum(d['importe_neto'] for d in factura['resumen_vehiculos'].values())

                            st.markdown("---")
                            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                            with col_t1:
                                st.metric("Total Peajes", total_peajes)
                            with col_t2:
                                st.metric("Importe Peajes", formato_importe_es(total_importe_peajes))
                            with col_t3:
                                st.metric("Bonificaciones", formato_importe_es(total_bonificaciones))
                            with col_t4:
                                st.metric("Total Neto", formato_importe_es(total_importe_neto))

                # Detalle de operaciones (solo combustible)
                if factura.get('movimientos') and tipo == 'COMBUSTIBLE':
                    with st.expander("📝 Ver detalle de repostajes"):
                        datos_ops = []
                        for mov in factura['movimientos']:
                            litros = mov.get('litros', 0) or 0
                            importe_neto = mov.get('importe', 0) or 0
                            precio_neto = importe_neto / litros if litros > 0 else 0

                            datos_ops.append({
                                'Fecha': mov.get('fecha', ''),
                                'Vehículo': mov.get('vehiculo', ''),
                                'Concepto': mov.get('concepto', ''),
                                'Litros': f"{litros:,.1f}",
                                'Precio Bruto': f"{mov.get('precio_litro', 0):.3f} €",
                                'Precio-Dto': f"{precio_neto:.3f} €",
                                'Descuento': formato_importe_es(mov.get('descuento', 0)) if mov.get('descuento', 0) > 0 else '-',
                                'Importe Neto': formato_importe_es(importe_neto)
                            })
                        if datos_ops:
                            st.dataframe(pd.DataFrame(datos_ops), use_container_width=True, hide_index=True)

                # Botón para eliminar esta factura
                if st.button(f"🗑️ Eliminar", key=f"eliminar_factura_{i}"):
                    st.session_state.facturas_procesadas.pop(i)
                    st.rerun()

        st.markdown("---")

        # Botones de acción
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])

        with col_btn1:
            if st.button("💾 Guardar en Base de Datos", type="primary", use_container_width=True):
                movimientos_totales = []

                for factura in st.session_state.facturas_procesadas:
                    if factura.get('resumen_vehiculos') and not factura.get('errores'):
                        movs = generar_movimientos_para_db(factura)
                        movimientos_totales.extend(movs)

                if movimientos_totales:
                    # Insertar en BD
                    importacion_id = insertar_movimientos(
                        movimientos_totales,
                        "Facturas combustible/peajes"
                    )

                    st.success(f"✅ Guardados {len(movimientos_totales)} movimientos (Importación #{importacion_id})")

                    # Limpiar estado
                    st.session_state.facturas_procesadas = []
                    st.rerun()
                else:
                    st.warning("No hay movimientos válidos para guardar")

        with col_btn2:
            if st.button("🗑️ Limpiar Todo", use_container_width=True):
                st.session_state.facturas_procesadas = []
                st.rerun()

        # Mostrar movimientos que se van a generar
        with st.expander("👁️ Vista previa de movimientos a guardar"):
            movs_preview = []
            for factura in st.session_state.facturas_procesadas:
                if factura.get('resumen_vehiculos') and not factura.get('errores'):
                    for mov in generar_movimientos_para_db(factura):
                        movs_preview.append({
                            'Fecha': mov['fecha'],
                            'Vehículo': mov['vehiculo_id'],
                            'Descripción': mov['descripcion'],
                            'Importe': formato_importe_es(mov['importe']),
                            'Categoría': mov['categoria_id']
                        })

            if movs_preview:
                st.dataframe(pd.DataFrame(movs_preview), use_container_width=True, hide_index=True)
            else:
                st.info("No hay movimientos para guardar")

    else:
        # Instrucciones
        st.info("""
        📌 **Instrucciones:**
        1. Sube una o más facturas PDF
        2. Proveedores soportados:
           - **StarOil** (combustible) - Bonificación fija 0,165€/L gasoil, 0,30€/L AdBlue
           - **Solred/Waylet** (combustible) - Descuento por operación
           - **Valcarce** (combustible y peajes) - Detecta automáticamente el tipo
        3. El sistema detectará automáticamente el proveedor y tipo
        4. Revisa los datos y haz clic en "Guardar" para importar
        """)


# ============== MAIN ==============

def main():
    """Función principal de la aplicación."""
    pagina = render_sidebar()

    if pagina == "resumen":
        pagina_resumen()
    elif pagina == "vehiculo":
        pagina_vehiculo()
    elif pagina == "importar":
        pagina_importar()
    elif pagina == "facturas":
        pagina_facturas()
    elif pagina == "config":
        pagina_config()


if __name__ == "__main__":
    main()
