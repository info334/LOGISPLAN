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
    insertar_movimientos, get_vehiculos_operativos,
    get_amortizaciones, guardar_amortizaciones, inicializar_amortizaciones_default,
    get_costes_laborales, insertar_costes_laborales_batch, get_resumen_costes_por_vehiculo,
    eliminar_movimientos, get_movimientos_con_filtros,
    get_facturacion, insertar_facturacion, eliminar_facturacion
)
from importador import (
    parsear_csv_abanca, auto_categorizar, preparar_para_guardado,
    validar_importacion, detectar_duplicados
)
from importador_facturas import parsear_factura_pdf, generar_movimientos_para_db

# Para parseo de PDF de costes laborales
import pdfplumber
import re

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
        "📋 Registros": "registros",
        "👷 Costes Laborales": "costes_laborales",
        "💰 Facturación": "facturacion",
        "⚙️ Configuración": "config"
    }

    seleccion = st.sidebar.radio(
        "Navegación",
        options=list(paginas.keys()),
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")

    # Checklist de tareas mensuales
    st.sidebar.markdown("### 📝 Tareas del mes")

    # Inicializar estado de checklist si no existe
    if 'checklist_gasoil' not in st.session_state:
        st.session_state.checklist_gasoil = False
    if 'checklist_costes_laborales' not in st.session_state:
        st.session_state.checklist_costes_laborales = False
    if 'checklist_banco' not in st.session_state:
        st.session_state.checklist_banco = False
    if 'checklist_facturacion' not in st.session_state:
        st.session_state.checklist_facturacion = False

    st.session_state.checklist_gasoil = st.sidebar.checkbox(
        "⛽ Gasoil",
        value=st.session_state.checklist_gasoil,
        key="check_gasoil"
    )
    st.session_state.checklist_costes_laborales = st.sidebar.checkbox(
        "👷 Costes laborales",
        value=st.session_state.checklist_costes_laborales,
        key="check_costes"
    )
    st.session_state.checklist_banco = st.sidebar.checkbox(
        "🏦 Fichero banco",
        value=st.session_state.checklist_banco,
        key="check_banco"
    )
    st.session_state.checklist_facturacion = st.sidebar.checkbox(
        "📄 Facturación",
        value=st.session_state.checklist_facturacion,
        key="check_facturacion"
    )

    # Mostrar progreso
    tareas_completadas = sum([
        st.session_state.checklist_gasoil,
        st.session_state.checklist_costes_laborales,
        st.session_state.checklist_banco,
        st.session_state.checklist_facturacion
    ])
    st.sidebar.progress(tareas_completadas / 4)
    st.sidebar.caption(f"{tareas_completadas}/4 tareas completadas")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"v2.0 | {datetime.now().strftime('%Y')}")
    st.sidebar.caption("Seve Fernández")

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
    """Vista de configuración de amortizaciones."""
    st.markdown('<p class="main-header">⚙️ Configuración</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Configuración de amortizaciones por activo</p>', unsafe_allow_html=True)

    # Inicializar amortizaciones por defecto si está vacía
    inicializar_amortizaciones_default()

    # Obtener amortizaciones actuales
    df_amort = get_amortizaciones()

    # Opciones de vehículos
    vehiculos_options = ["MTY", "LVX", "MJC", "MLB", "COMÚN"]

    st.markdown("### 📊 Amortizaciones por Activo")
    st.caption("Edita los valores y pulsa 'Guardar' para actualizar. La amortización mensual se calcula automáticamente.")

    # Estado de sesión para edición
    if 'df_amort_edit' not in st.session_state or st.session_state.get('reload_amort', False):
        if len(df_amort) > 0:
            st.session_state.df_amort_edit = df_amort[['activo', 'matricula', 'vehiculo_id', 'amortizacion_anual', 'amortizacion_mensual']].copy()
        else:
            st.session_state.df_amort_edit = pd.DataFrame({
                'activo': [''],
                'matricula': [''],
                'vehiculo_id': ['COMÚN'],
                'amortizacion_anual': [0.0],
                'amortizacion_mensual': [0.0]
            })
        st.session_state.reload_amort = False

    # Configuración del editor
    column_config = {
        "activo": st.column_config.TextColumn(
            "Activo",
            help="Nombre del activo",
            width="medium",
            required=True
        ),
        "matricula": st.column_config.TextColumn(
            "Matrícula",
            help="Matrícula del vehículo",
            width="small"
        ),
        "vehiculo_id": st.column_config.SelectboxColumn(
            "Vehículo",
            help="Vehículo al que se asigna",
            options=vehiculos_options,
            width="small",
            required=True
        ),
        "amortizacion_anual": st.column_config.NumberColumn(
            "Amort. Anual €",
            help="Amortización anual en euros",
            min_value=0,
            format="%.2f €",
            width="small",
            required=True
        ),
        "amortizacion_mensual": st.column_config.NumberColumn(
            "Amort. Mensual €",
            help="Se calcula automáticamente (anual / 12)",
            format="%.2f €",
            width="small",
            disabled=True
        )
    }

    # Editor de datos
    edited_df = st.data_editor(
        st.session_state.df_amort_edit,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="amort_editor"
    )

    # Auto-calcular amortización mensual
    if edited_df is not None:
        edited_df['amortizacion_mensual'] = edited_df['amortizacion_anual'] / 12
        st.session_state.df_amort_edit = edited_df

    # Resumen por vehículo
    if len(edited_df) > 0 and edited_df['amortizacion_anual'].sum() > 0:
        st.markdown("---")
        st.markdown("### 📈 Resumen por Vehículo")

        resumen = edited_df.groupby('vehiculo_id').agg({
            'amortizacion_anual': 'sum',
            'amortizacion_mensual': 'sum'
        }).reset_index()

        # Mostrar como métricas
        cols = st.columns(len(resumen))
        for i, (_, row) in enumerate(resumen.iterrows()):
            with cols[i]:
                st.metric(
                    row['vehiculo_id'],
                    formato_importe_es(row['amortizacion_mensual']) + "/mes",
                    f"{formato_importe_es(row['amortizacion_anual'])}/año"
                )

        # Total
        st.markdown("---")
        col_total1, col_total2, col_total3 = st.columns([1, 1, 2])
        with col_total1:
            st.metric("Total Anual", formato_importe_es(edited_df['amortizacion_anual'].sum()))
        with col_total2:
            st.metric("Total Mensual", formato_importe_es(edited_df['amortizacion_mensual'].sum()))

    st.markdown("---")

    # Botones de acción
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])

    with col_btn1:
        if st.button("💾 Guardar amortizaciones", type="primary", use_container_width=True):
            # Validar datos
            df_guardar = edited_df[edited_df['activo'].str.strip() != ''].copy()

            if len(df_guardar) == 0:
                st.error("No hay activos válidos para guardar")
            else:
                # Preparar para guardar
                amortizaciones_lista = []
                for _, row in df_guardar.iterrows():
                    amortizaciones_lista.append({
                        'activo': row['activo'],
                        'matricula': row['matricula'] if pd.notna(row['matricula']) else None,
                        'vehiculo_id': row['vehiculo_id'],
                        'amortizacion_anual': float(row['amortizacion_anual']),
                        'amortizacion_mensual': float(row['amortizacion_anual']) / 12
                    })

                guardar_amortizaciones(amortizaciones_lista)
                st.success(f"✅ Guardadas {len(amortizaciones_lista)} amortizaciones")
                st.session_state.reload_amort = True
                st.rerun()

    with col_btn2:
        if st.button("🔄 Recargar", use_container_width=True):
            st.session_state.reload_amort = True
            st.rerun()


# ============== PÁGINA: REGISTROS ==============

def pagina_registros():
    """Vista de registros con filtros y borrado."""
    st.markdown('<p class="main-header">📋 Registros</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Visualiza, filtra y gestiona los movimientos importados</p>', unsafe_allow_html=True)

    # Obtener opciones para filtros
    vehiculos_df = get_vehiculos()
    categorias_df = get_categorias()

    vehiculo_options = ["Todos"] + vehiculos_df['id'].tolist()
    categoria_options = ["Todas"] + categorias_df['id'].tolist()

    # Estado de sesión
    if 'registros_pagina' not in st.session_state:
        st.session_state.registros_pagina = 0
    if 'registros_seleccionados' not in st.session_state:
        st.session_state.registros_seleccionados = set()

    # Filtros en columnas
    st.markdown("### 🔍 Filtros")
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])

    with col_f1:
        fecha_desde = st.date_input(
            "Fecha desde",
            value=None,
            key="filtro_fecha_desde"
        )

    with col_f2:
        fecha_hasta = st.date_input(
            "Fecha hasta",
            value=None,
            key="filtro_fecha_hasta"
        )

    with col_f3:
        vehiculos_sel = st.multiselect(
            "Vehículo",
            options=vehiculo_options,
            default=["Todos"],
            key="filtro_vehiculos"
        )

    with col_f4:
        categorias_sel = st.multiselect(
            "Categoría",
            options=categoria_options,
            default=["Todas"],
            key="filtro_categorias"
        )

    with col_f5:
        tipo_sel = st.selectbox(
            "Tipo",
            options=["Todos", "Ingresos", "Gastos"],
            key="filtro_tipo"
        )

    # Procesar filtros
    vehiculos_filtro = None if "Todos" in vehiculos_sel or len(vehiculos_sel) == 0 else vehiculos_sel
    categorias_filtro = None if "Todas" in categorias_sel or len(categorias_sel) == 0 else categorias_sel
    tipo_filtro = None if tipo_sel == "Todos" else tipo_sel

    # Obtener datos con paginación
    REGISTROS_POR_PAGINA = 50
    offset = st.session_state.registros_pagina * REGISTROS_POR_PAGINA

    df_registros, total_registros = get_movimientos_con_filtros(
        fecha_desde=fecha_desde.strftime('%Y-%m-%d') if fecha_desde else None,
        fecha_hasta=fecha_hasta.strftime('%Y-%m-%d') if fecha_hasta else None,
        vehiculos=vehiculos_filtro,
        categorias=categorias_filtro,
        tipo=tipo_filtro,
        limit=REGISTROS_POR_PAGINA,
        offset=offset
    )

    total_paginas = max(1, (total_registros + REGISTROS_POR_PAGINA - 1) // REGISTROS_POR_PAGINA)

    st.markdown("---")

    # Información de resultados
    st.markdown(f"**{total_registros:,}** registros encontrados | Página **{st.session_state.registros_pagina + 1}** de **{total_paginas}**")

    if len(df_registros) == 0:
        st.info("📭 No hay registros que coincidan con los filtros seleccionados.")
        return

    # Botones de selección
    col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 4])

    with col_sel1:
        if st.button("☑️ Seleccionar todos", key="sel_todos"):
            for idx in df_registros['id'].tolist():
                st.session_state.registros_seleccionados.add(idx)
            st.rerun()

    with col_sel2:
        if st.button("☐ Deseleccionar todos", key="desel_todos"):
            st.session_state.registros_seleccionados.clear()
            st.rerun()

    # Tabla de registros con checkboxes
    st.markdown("### 📊 Registros")

    # Cabecera
    col_check, col_fecha, col_desc, col_cat, col_veh, col_importe = st.columns([0.5, 1, 4, 1.2, 1, 1.5])
    with col_check:
        st.write("**☑️**")
    with col_fecha:
        st.write("**Fecha**")
    with col_desc:
        st.write("**Descripción**")
    with col_cat:
        st.write("**Categoría**")
    with col_veh:
        st.write("**Vehículo**")
    with col_importe:
        st.write("**Importe**")

    st.markdown("<hr style='margin:5px 0; border:none; border-top:2px solid #1f4e79;'>", unsafe_allow_html=True)

    # Filas de datos
    for _, row in df_registros.iterrows():
        reg_id = int(row['id'])
        importe = float(row['importe'])
        es_gasto = importe < 0

        col_check, col_fecha, col_desc, col_cat, col_veh, col_importe = st.columns([0.5, 1, 4, 1.2, 1, 1.5])

        with col_check:
            checked = st.checkbox(
                "",
                value=reg_id in st.session_state.registros_seleccionados,
                key=f"check_{reg_id}",
                label_visibility="collapsed"
            )
            if checked:
                st.session_state.registros_seleccionados.add(reg_id)
            elif reg_id in st.session_state.registros_seleccionados:
                st.session_state.registros_seleccionados.discard(reg_id)

        with col_fecha:
            st.write(str(row['fecha'])[:10])

        with col_desc:
            desc_text = str(row['descripcion'])[:50]
            if len(str(row['descripcion'])) > 50:
                desc_text += "..."
            st.write(desc_text)

        with col_cat:
            cat_nombre = row['categoria_nombre'] if row['categoria_nombre'] else row['categoria_id']
            st.write(cat_nombre or "-")

        with col_veh:
            st.write(row['vehiculo_id'] or "-")

        with col_importe:
            color = "red" if es_gasto else "green"
            st.markdown(f"<span style='color:{color}'>{formato_importe_es(importe)}</span>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:5px 0; border:none; border-top:1px solid #ddd;'>", unsafe_allow_html=True)

    # Paginación
    st.markdown("---")
    col_pag1, col_pag2, col_pag3, col_pag4, col_pag5 = st.columns([1, 1, 2, 1, 1])

    with col_pag1:
        if st.button("⏮️ Primera", disabled=st.session_state.registros_pagina == 0):
            st.session_state.registros_pagina = 0
            st.rerun()

    with col_pag2:
        if st.button("◀️ Anterior", disabled=st.session_state.registros_pagina == 0):
            st.session_state.registros_pagina -= 1
            st.rerun()

    with col_pag3:
        st.write(f"Página {st.session_state.registros_pagina + 1} de {total_paginas}")

    with col_pag4:
        if st.button("▶️ Siguiente", disabled=st.session_state.registros_pagina >= total_paginas - 1):
            st.session_state.registros_pagina += 1
            st.rerun()

    with col_pag5:
        if st.button("⏭️ Última", disabled=st.session_state.registros_pagina >= total_paginas - 1):
            st.session_state.registros_pagina = total_paginas - 1
            st.rerun()

    # Resumen de selección y borrado
    st.markdown("---")

    num_seleccionados = len(st.session_state.registros_seleccionados)

    if num_seleccionados > 0:
        # Calcular total de seleccionados (solo los que están en la página actual para mostrar)
        ids_seleccionados_en_pagina = [id for id in st.session_state.registros_seleccionados if id in df_registros['id'].values]
        total_seleccionados = df_registros[df_registros['id'].isin(st.session_state.registros_seleccionados)]['importe'].sum()

        st.markdown(f"### 🗑️ **{num_seleccionados}** registros seleccionados | Total visible: **{formato_importe_es(total_seleccionados)}**")

        col_del1, col_del2 = st.columns([1, 4])

        with col_del1:
            if st.button("🗑️ Borrar seleccionados", type="primary", use_container_width=True):
                st.session_state.confirmar_borrado = True

        # Confirmación de borrado
        if st.session_state.get('confirmar_borrado', False):
            st.warning(f"⚠️ ¿Estás seguro de que quieres borrar **{num_seleccionados}** registros? Esta acción no se puede deshacer.")

            col_conf1, col_conf2, col_conf3 = st.columns([1, 1, 3])

            with col_conf1:
                if st.button("✅ Confirmar borrado", type="primary"):
                    # Ejecutar borrado
                    ids_a_borrar = list(st.session_state.registros_seleccionados)
                    eliminados = eliminar_movimientos(ids_a_borrar)
                    st.success(f"✅ Se han eliminado {eliminados} registros")
                    st.session_state.registros_seleccionados.clear()
                    st.session_state.confirmar_borrado = False
                    st.rerun()

            with col_conf2:
                if st.button("❌ Cancelar"):
                    st.session_state.confirmar_borrado = False
                    st.rerun()
    else:
        st.info("Selecciona registros usando los checkboxes para poder borrarlos")


# ============== PÁGINA: COSTES LABORALES ==============

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

    # Extraer mes del nombre del archivo (formato COST_YYYYMM_...)
    mes_match = re.search(r'COST_(\d{6})', filename)
    if mes_match:
        year_month = mes_match.group(1)
        mes = f"{year_month[:4]}-{year_month[4:6]}"  # Formato YYYY-MM
    else:
        errores.append(f"No se pudo extraer el mes del nombre del archivo: {filename}")
        return resultados, errores, None

    try:
        import io
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
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


def pagina_costes_laborales():
    """Vista de gestión de costes laborales."""
    st.markdown('<p class="main-header">👷 Costes Laborales</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Importa y gestiona los costes laborales por trabajador y vehículo</p>', unsafe_allow_html=True)

    # Estado de sesión
    if 'costes_preview' not in st.session_state:
        st.session_state.costes_preview = None
    if 'costes_mes' not in st.session_state:
        st.session_state.costes_mes = None

    # Tabs para las opciones
    tab1, tab2, tab3 = st.tabs(["📄 Importar PDF", "✏️ Entrada Manual", "📊 Resumen"])

    with tab1:
        st.markdown("### 📄 Importar PDF de Costes")
        st.caption("Sube un PDF con formato COST_YYYYMM_Emp_65.pdf")

        archivo_pdf = st.file_uploader(
            "Selecciona archivo PDF",
            type=['pdf'],
            key="pdf_costes",
            help="Formato esperado: COST_YYYYMM_Emp_65.pdf (ej: COST_202401_Emp_65.pdf)"
        )

        if archivo_pdf is not None:
            with st.spinner("Procesando PDF..."):
                resultados, errores, mes = parsear_pdf_costes_laborales(
                    archivo_pdf.read(),
                    archivo_pdf.name
                )

            if errores:
                for error in errores:
                    st.error(error)

            if resultados:
                st.session_state.costes_preview = resultados
                st.session_state.costes_mes = mes

                st.success(f"✅ Se encontraron {len(resultados)} trabajadores para el mes **{mes}**")

                # Vista previa
                st.markdown("### 👁️ Vista Previa")

                datos_preview = []
                for r in resultados:
                    datos_preview.append({
                        'Trabajador': r['nombre'],
                        'Vehículo': r['vehiculo_id'],
                        'Bruto': formato_importe_es(r['bruto']),
                        'SS Trabajador': formato_importe_es(r['ss_trabajador']),
                        'IRPF': formato_importe_es(r['irpf']),
                        'Líquido': formato_importe_es(r['liquido']),
                        'SS Empresa': formato_importe_es(r['ss_empresa']),
                        'Coste Total': formato_importe_es(r['coste_total'])
                    })

                df_preview = pd.DataFrame(datos_preview)
                st.dataframe(df_preview, use_container_width=True, hide_index=True)

                # Totales
                total_coste = sum(r['coste_total'] for r in resultados)
                total_bruto = sum(r['bruto'] for r in resultados)
                total_ss_emp = sum(r['ss_empresa'] for r in resultados)

                st.markdown("---")
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1:
                    st.metric("Total Bruto", formato_importe_es(total_bruto))
                with col_t2:
                    st.metric("Total SS Empresa", formato_importe_es(total_ss_emp))
                with col_t3:
                    st.metric("Coste Total", formato_importe_es(total_coste))

                # Botón importar
                st.markdown("---")
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("💾 Importar costes", type="primary", use_container_width=True):
                        num_insertados = insertar_costes_laborales_batch(resultados)
                        st.success(f"✅ Importados {num_insertados} registros de costes laborales")
                        st.session_state.costes_preview = None
                        st.session_state.costes_mes = None
                        st.rerun()

            elif not errores:
                st.warning("No se encontraron datos de trabajadores en el PDF. Verifica el formato.")

        # Mapeo de trabajadores
        with st.expander("ℹ️ Mapeo de trabajadores"):
            st.markdown("**Trabajadores configurados:**")
            for tid, info in TRABAJADORES.items():
                st.markdown(f"- **{tid}**: {info['nombre']} → Vehículo: **{info['vehiculo']}**")

    with tab2:
        st.markdown("### ✏️ Entrada Manual de Costes")

        # Selector de mes
        col_mes1, col_mes2 = st.columns(2)
        with col_mes1:
            anio = st.selectbox(
                "Año",
                options=list(range(datetime.now().year, datetime.now().year - 5, -1)),
                key="manual_anio"
            )
        with col_mes2:
            mes_num = st.selectbox(
                "Mes",
                options=list(range(1, 13)),
                format_func=lambda x: f"{x:02d} - {['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][x-1]}",
                key="manual_mes"
            )

        mes_str = f"{anio}-{mes_num:02d}"

        st.markdown("---")

        # Selector de trabajador
        trabajador_options = {f"{tid}: {info['nombre']} ({info['vehiculo']})": tid for tid, info in TRABAJADORES.items()}
        trabajador_sel = st.selectbox(
            "Trabajador",
            options=list(trabajador_options.keys()),
            key="manual_trabajador"
        )
        trabajador_id = trabajador_options[trabajador_sel]
        trabajador_info = TRABAJADORES[trabajador_id]

        # Campos de entrada
        col_inp1, col_inp2 = st.columns(2)
        with col_inp1:
            bruto = st.number_input("Salario Bruto (€)", min_value=0.0, step=100.0, key="manual_bruto")
            ss_trabajador = st.number_input("SS Trabajador (€)", min_value=0.0, step=50.0, key="manual_ss_trab")
            irpf = st.number_input("IRPF (€)", min_value=0.0, step=50.0, key="manual_irpf")

        with col_inp2:
            liquido = st.number_input("Líquido (€)", min_value=0.0, step=100.0, key="manual_liquido")
            ss_empresa = st.number_input("SS Empresa (€)", min_value=0.0, step=50.0, key="manual_ss_emp")
            otros = st.number_input("Otros costes (€)", min_value=0.0, step=10.0, key="manual_otros")

        # Calcular coste total
        coste_total = bruto + ss_empresa + otros

        st.markdown("---")
        st.metric("Coste Total Calculado", formato_importe_es(coste_total))

        # Botón añadir
        if st.button("➕ Añadir coste laboral", type="primary"):
            if bruto <= 0:
                st.error("El salario bruto debe ser mayor que 0")
            else:
                coste = {
                    'mes': mes_str,
                    'trabajador_id': trabajador_id,
                    'nombre': trabajador_info['nombre'],
                    'vehiculo_id': trabajador_info['vehiculo'],
                    'bruto': bruto,
                    'ss_trabajador': ss_trabajador,
                    'irpf': irpf,
                    'liquido': liquido,
                    'ss_empresa': ss_empresa,
                    'coste_total': coste_total
                }
                insertar_costes_laborales_batch([coste])
                st.success(f"✅ Coste laboral añadido para {trabajador_info['nombre']} ({mes_str})")
                st.rerun()

    with tab3:
        st.markdown("### 📊 Resumen de Costes Laborales")

        # Obtener todos los costes
        df_costes = get_costes_laborales()

        if len(df_costes) == 0:
            st.info("📭 No hay costes laborales registrados. Importa un PDF o añade manualmente.")
            return

        # Tabla pivote: mes vs vehículo
        resumen = df_costes.groupby(['mes', 'vehiculo_id']).agg({
            'coste_total': 'sum'
        }).reset_index()

        # Crear tabla pivote
        pivot = resumen.pivot(index='mes', columns='vehiculo_id', values='coste_total').fillna(0)

        # Añadir columna de total
        pivot['TOTAL'] = pivot.sum(axis=1)

        # Ordenar por mes descendente
        pivot = pivot.sort_index(ascending=False)

        # Formatear valores
        pivot_formatted = pivot.copy()
        for col in pivot_formatted.columns:
            pivot_formatted[col] = pivot_formatted[col].apply(lambda x: formato_importe_es(x) if x > 0 else '-')

        st.markdown("#### Costes por Vehículo/Mes")
        st.dataframe(pivot_formatted, use_container_width=True)

        # Métricas totales
        st.markdown("---")
        st.markdown("#### Totales por Vehículo")

        totales_vehiculo = df_costes.groupby('vehiculo_id')['coste_total'].sum()

        cols = st.columns(len(totales_vehiculo) + 1)
        for i, (veh, total) in enumerate(totales_vehiculo.items()):
            with cols[i]:
                st.metric(veh, formato_importe_es(total))

        with cols[-1]:
            st.metric("TOTAL", formato_importe_es(totales_vehiculo.sum()))

        # Detalle por trabajador
        st.markdown("---")
        with st.expander("📋 Detalle por Trabajador"):
            # Filtro de mes
            meses_disponibles = ["Todos"] + sorted(df_costes['mes'].unique().tolist(), reverse=True)
            mes_filtro = st.selectbox("Filtrar por mes", options=meses_disponibles, key="filtro_mes_costes")

            df_detalle = df_costes.copy()
            if mes_filtro != "Todos":
                df_detalle = df_detalle[df_detalle['mes'] == mes_filtro]

            # Mostrar tabla
            datos_detalle = []
            for _, row in df_detalle.iterrows():
                datos_detalle.append({
                    'Mes': row['mes'],
                    'Trabajador': row['nombre'],
                    'Vehículo': row['vehiculo_id'],
                    'Bruto': formato_importe_es(row['bruto']),
                    'SS Empresa': formato_importe_es(row['ss_empresa']),
                    'Coste Total': formato_importe_es(row['coste_total'])
                })

            if datos_detalle:
                st.dataframe(pd.DataFrame(datos_detalle), use_container_width=True, hide_index=True)


# ============== PÁGINA: FACTURACIÓN ==============

def pagina_facturacion():
    """Vista de gestión de facturación por vehículo."""
    st.markdown('<p class="main-header">💰 Facturación</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Registra la facturación mensual por vehículo</p>', unsafe_allow_html=True)

    # Obtener vehículos operativos
    vehiculos_df = get_vehiculos_operativos()
    vehiculos_options = vehiculos_df['id'].tolist()

    # Tabs para entrada y resumen
    tab1, tab2 = st.tabs(["✏️ Introducir Facturación", "📊 Resumen"])

    with tab1:
        st.markdown("### ✏️ Nueva Facturación")

        # Formulario de entrada
        col_form1, col_form2 = st.columns(2)

        with col_form1:
            # Selector de año y mes
            anio = st.selectbox(
                "Año",
                options=list(range(datetime.now().year, datetime.now().year - 5, -1)),
                key="fact_anio"
            )
            mes_num = st.selectbox(
                "Mes",
                options=list(range(1, 13)),
                format_func=lambda x: f"{x:02d} - {['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][x-1]}",
                key="fact_mes"
            )

        with col_form2:
            # Selector de vehículo
            vehiculo_sel = st.selectbox(
                "Vehículo",
                options=vehiculos_options,
                key="fact_vehiculo"
            )

            # Importe
            importe = st.number_input(
                "Importe facturado (€)",
                min_value=0.0,
                step=500.0,
                format="%.2f",
                key="fact_importe"
            )

        # Descripción opcional
        descripcion = st.text_input(
            "Descripción (opcional)",
            placeholder="Ej: Factura cliente X, portes mes...",
            key="fact_descripcion"
        )

        mes_str = f"{anio}-{mes_num:02d}"

        st.markdown("---")

        # Botón añadir
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("💾 Guardar facturación", type="primary", use_container_width=True):
                if importe <= 0:
                    st.error("El importe debe ser mayor que 0")
                else:
                    factura = {
                        'mes': mes_str,
                        'vehiculo_id': vehiculo_sel,
                        'importe': importe,
                        'descripcion': descripcion if descripcion else None
                    }
                    insertar_facturacion(factura)
                    st.success(f"✅ Facturación guardada: {vehiculo_sel} - {mes_str} - {formato_importe_es(importe)}")
                    st.rerun()

        # Mostrar facturación existente del mes seleccionado
        st.markdown("---")
        st.markdown(f"### 📋 Facturación registrada en {mes_str}")

        df_mes = get_facturacion(mes=mes_str)

        if len(df_mes) > 0:
            datos_mes = []
            for _, row in df_mes.iterrows():
                datos_mes.append({
                    'Vehículo': row['vehiculo_id'],
                    'Importe': formato_importe_es(row['importe']),
                    'Descripción': row['descripcion'] or '-',
                    'ID': row['id']
                })

            # Mostrar tabla
            for dato in datos_mes:
                col_v, col_i, col_d, col_del = st.columns([1, 1.5, 2, 0.5])
                with col_v:
                    st.write(f"**{dato['Vehículo']}**")
                with col_i:
                    st.write(dato['Importe'])
                with col_d:
                    st.write(dato['Descripción'])
                with col_del:
                    if st.button("🗑️", key=f"del_fact_{dato['ID']}"):
                        eliminar_facturacion(dato['ID'])
                        st.rerun()

            # Total del mes
            total_mes = df_mes['importe'].sum()
            st.markdown("---")
            st.metric(f"Total {mes_str}", formato_importe_es(total_mes))
        else:
            st.info(f"No hay facturación registrada para {mes_str}")

    with tab2:
        st.markdown("### 📊 Resumen de Facturación")

        # Obtener toda la facturación
        df_fact = get_facturacion()

        if len(df_fact) == 0:
            st.info("📭 No hay facturación registrada. Introduce datos en la pestaña anterior.")
            return

        # Tabla pivote: mes vs vehículo
        resumen = df_fact.groupby(['mes', 'vehiculo_id']).agg({
            'importe': 'sum'
        }).reset_index()

        # Crear tabla pivote
        pivot = resumen.pivot(index='mes', columns='vehiculo_id', values='importe').fillna(0)

        # Añadir columna de total
        pivot['TOTAL'] = pivot.sum(axis=1)

        # Ordenar por mes descendente
        pivot = pivot.sort_index(ascending=False)

        # Formatear valores
        pivot_formatted = pivot.copy()
        for col in pivot_formatted.columns:
            pivot_formatted[col] = pivot_formatted[col].apply(lambda x: formato_importe_es(x) if x > 0 else '-')

        st.markdown("#### Facturación por Vehículo/Mes")
        st.dataframe(pivot_formatted, use_container_width=True)

        # Métricas totales
        st.markdown("---")
        st.markdown("#### Totales por Vehículo")

        totales_vehiculo = df_fact.groupby('vehiculo_id')['importe'].sum()

        cols = st.columns(len(totales_vehiculo) + 1)
        for i, (veh, total) in enumerate(totales_vehiculo.items()):
            with cols[i]:
                st.metric(veh, formato_importe_es(total))

        with cols[-1]:
            st.metric("TOTAL", formato_importe_es(totales_vehiculo.sum()))

        # Media mensual
        st.markdown("---")
        meses_con_datos = len(pivot)
        if meses_con_datos > 0:
            media_mensual = totales_vehiculo.sum() / meses_con_datos
            st.metric("Media mensual", formato_importe_es(media_mensual), f"({meses_con_datos} meses)")


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
    elif pagina == "registros":
        pagina_registros()
    elif pagina == "costes_laborales":
        pagina_costes_laborales()
    elif pagina == "facturacion":
        pagina_facturacion()
    elif pagina == "config":
        pagina_config()


if __name__ == "__main__":
    main()
