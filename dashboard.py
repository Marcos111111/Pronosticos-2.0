'''
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitoreo Agrícola", layout="wide", initial_sidebar_state="collapsed")

# Estilo CSS para móviles
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 5px; }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 10px;
        background-color: #1e1e1e;
        border-radius: 5px;
        color: white;
        font-size: 0.9rem;
    }
    .stDataFrame { font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE TRADUCCIÓN ---
def nombre_dia_es(fecha):
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    return f"{dias[fecha.weekday()]} {fecha.day}"

def fecha_completa_es(fecha):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    return f"{dias[fecha.weekday()]} {fecha.day} de {meses[fecha.month - 1]}"

def grados_a_direccion(grados):
    if grados is None or pd.isna(grados): return "-"
    direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return direcciones[int(((grados + 22.5) % 360) // 45)]

# --- CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos(lote_nombre):
    conn = sqlite3.connect("monitoreo_agricola.db") # Asegurate de usar DB_PATH que definimos antes
    
    query = """
    SELECT p.*, m.nombre as modelo_nombre, c.nombre as campo_nombre
    FROM pronosticos_full p
    JOIN modelos m ON p.modelo_id = m.id
    JOIN campos c ON p.campo_id = c.id
    WHERE c.nombre = ?
    AND p.id IN (
        -- Aquí seleccionamos los IDs más altos (los últimos en entrar)
        -- filtrando por una ventana razonable para no barrer toda la tabla
        SELECT MAX(id)
        FROM pronosticos_full
        WHERE id > (SELECT MAX(id) FROM pronosticos_full) - 10000
        GROUP BY campo_id, modelo_id, fecha_pronosticada
    )
    ORDER BY p.fecha_pronosticada ASC
    """
    
    df = pd.read_sql_query(query, conn, params=(lote_nombre,))
    
    if not df.empty:
        df['fecha_pronosticada'] = pd.to_datetime(df['fecha_pronosticada'])
        
    conn.close()
    return df
# --- INTERFAZ ---
try:
    conn = sqlite3.connect("monitoreo_agricola.db")
    lotes = pd.read_sql("SELECT nombre FROM campos", conn)['nombre'].tolist()
    conn.close()
except:
    lotes = ["Sin datos"]

lote_sel = st.sidebar.selectbox("Lote", lotes)
df_lote = cargar_datos(lote_sel)

if not df_lote.empty:
    modelos = sorted(df_lote['modelo_nombre'].unique())
    mod_sel = st.sidebar.radio("Modelo para Detalle", options=modelos)
    
    st.title(f"📍 {lote_sel}")

    # Función para bloquear zoom/interacción molesta en móvil
    def config_estatico(fig):
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        fig.update_layout(dragmode=False, template="plotly_dark")
        return fig

    # --- SECCIÓN 1: COMPARATIVA DE LLUVIAS ---
    st.subheader("🌧️ Comparativa de Precipitaciones")
    dias_disp = sorted(df_lote['fecha_pronosticada'].dt.date.unique())
    nombres_tabs_comp = ["Toda la Semana"] + [nombre_dia_es(d) for d in dias_disp]
    tabs_comp = st.tabs(nombres_tabs_comp)

    with tabs_comp[0]:
        fig_total = px.bar(df_lote, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                           barmode='group', height=350, title="Pronóstico Semanal Agrupado",
                           labels={'lluvia_mm': 'Lluvia (mm)', 'fecha_pronosticada': 'Fecha', 'modelo_nombre': 'Modelo'})
        st.plotly_chart(config_estatico(fig_total), use_container_width=True, config={'displayModeBar': False}, key="comp_total")

    for i, fecha in enumerate(dias_disp):
        with tabs_comp[i+1]:
            df_f = df_lote[df_lote['fecha_pronosticada'].dt.date == fecha]
            fig_dia = px.bar(df_f, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                             barmode='group', height=300, title=f"Comparativa: {nombre_dia_es(fecha)}",
                             labels={'lluvia_mm': 'Lluvia (mm)', 'fecha_pronosticada': 'Hora'})
            st.plotly_chart(config_estatico(fig_dia), use_container_width=True, config={'displayModeBar': False}, key=f"comp_{fecha}")

    st.markdown("---")

    # --- SECCIÓN 2: DETALLE DIARIO DEL MODELO ---
    st.subheader(f"📅 Detalle Diario: {mod_sel}")
    tabs_det = st.tabs([nombre_dia_es(d) for d in dias_disp])

    for i, tab in enumerate(tabs_det):
        with tab:
            dia_actual = dias_disp[i]
            df_dia = df_lote[(df_lote['modelo_nombre'] == mod_sel) & (df_lote['fecha_pronosticada'].dt.date == dia_actual)].copy()
            
            if df_dia.empty:
                st.info("No hay datos para este día.")
                continue

            # 1. MÉTRICAS
            st.markdown(f"#### {fecha_completa_es(dia_actual)}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Máx T°", f"{df_dia['temp_c'].max():.1f}°")
            m2.metric("Mín T°", f"{df_dia['temp_c'].min():.1f}°")
            m3.metric("Lluvia", f"{df_dia['lluvia_mm'].sum():.1f} mm")
            m4.metric("Viento Máx", f"{df_dia['viento_ms'].max():.1f} m/s")

            # 3. LLUVIA Y VIENTO
            c1, c2 = st.columns(2)
            with c1:
                fig_l = px.bar(df_dia, x='fecha_pronosticada', y='lluvia_mm', title="Lluvia (mm)", color_discrete_sequence=['#00CC96'])
                st.plotly_chart(config_estatico(fig_l), use_container_width=True, config={'displayModeBar': False}, key=f"l_{mod_sel}_{dia_actual}")
            with c2:
                fig_v = px.line(df_dia, x='fecha_pronosticada', y='viento_ms', title="Viento (m/s)", color_discrete_sequence=['#AB63FA'])
                st.plotly_chart(config_estatico(fig_v), use_container_width=True, config={'displayModeBar': False}, key=f"v_{mod_sel}_{dia_actual}")
            
            # 2. GRÁFICO TEMP VS ROCÍO
            df_dia['dif'] = df_dia['temp_c'] - df_dia['punto_rocio_c']
            fig_t = go.Figure()
            for _, r in df_dia.iterrows():
                color = "#ff4b4b" if r['dif'] < 4 else ("#f9d71c" if r['dif'] < 8 else "#00cc96")
                fig_t.add_shape(type="line", x0=r['fecha_pronosticada'], x1=r['fecha_pronosticada'],
                               y0=r['punto_rocio_c'], y1=r['temp_c'], line=dict(color=color, width=4))
            
            fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['temp_c'], name='Temp', line=dict(color='red', width=3)))
            fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['punto_rocio_c'], name='Rocío', line=dict(color='cyan', width=3)))
            fig_t.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(config_estatico(fig_t), use_container_width=True, config={'displayModeBar': False}, key=f"t_rocio_{mod_sel}_{dia_actual}")

            # 4. TABLA DETALLADA (DATOS QUE FALTABAN)
            with st.expander("📋 Ver Tabla Horaria Detallada"):
                df_tab = df_dia.copy()
                df_tab['Dir'] = df_tab['viento_dir_deg'].apply(grados_a_direccion)
                df_tab['Hora'] = df_tab['fecha_pronosticada'].dt.strftime('%H:%M')
                cols = ['Hora', 'temp_c', 'punto_rocio_c', 'humedad_relativa', 'viento_ms', 'Dir', 'lluvia_mm']
                st.dataframe(df_tab[cols].rename(columns={
                    'temp_c': 'T°C', 'punto_rocio_c': 'Rocío', 'humedad_relativa': 'H%', 'viento_ms': 'V.m/s'
                }), hide_index=True, use_container_width=True)

else:
    st.warning("No hay datos disponibles.")
'''
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitoreo Agrícola", layout="wide", initial_sidebar_state="expanded")

# Colores fijos para mantener identidad visual entre pestañas
MAPA_COLORES = {
    "GFS": "#0212A5",
    "OpenMeteo": "#FF5757",
    "Met_Norway": "#00CC96",
    "SMN_WRF": "#D6D306"
}

# Estilo CSS optimizado
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    .stTabs [data-baseweb="tab"] { padding: 6px 10px; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE SOPORTE ---
def nombre_dia_es(fecha):
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    return f"{dias[fecha.weekday()]} {fecha.day}"

def fecha_completa_es(fecha):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    return f"{dias[fecha.weekday()]} {fecha.day} de {meses[fecha.month - 1]}"

def grados_a_direccion(grados):
    if grados is None or pd.isna(grados): return "-"
    direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return direcciones[int(((grados + 22.5) % 360) // 45)]

def config_estatico(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    fig.update_layout(dragmode=False, template="plotly_dark", margin=dict(l=10, r=10, t=40, b=10))
    return fig

# --- CARGA DE DATOS CON CACHE ---
@st.cache_data(ttl=600)
def cargar_datos(lote_nombre):
    conn = sqlite3.connect("monitoreo_agricola.db")
    query = """
    SELECT p.*, m.nombre as modelo_nombre, c.nombre as campo_nombre
    FROM pronosticos_full p
    JOIN modelos m ON p.modelo_id = m.id
    JOIN campos c ON p.campo_id = c.id
    WHERE c.nombre = ?
    AND p.id IN (
        SELECT MAX(id)
        FROM pronosticos_full
        WHERE id > (SELECT MAX(id) FROM pronosticos_full) - 10000
        GROUP BY campo_id, modelo_id, fecha_pronosticada
    )
    ORDER BY p.fecha_pronosticada ASC
    """
    df = pd.read_sql_query(query, conn, params=(lote_nombre,))
    if not df.empty:
        df['fecha_pronosticada'] = pd.to_datetime(df['fecha_pronosticada'])
    conn.close()
    return df

# --- SIDEBAR: NAVEGACIÓN Y FILTROS ---
with st.sidebar:
    st.title("🚜 Panel de Control")
    
    # 1. Selección de Lote
    try:
        conn = sqlite3.connect("monitoreo_agricola.db")
        lotes = pd.read_sql("SELECT nombre FROM campos", conn)['nombre'].tolist()
        conn.close()
    except:
        lotes = ["Sin datos"]
    
    lote_sel = st.selectbox("📍 Seleccionar Lote", lotes)
    
    st.markdown("---")
    
    # 2. Navegación por Secciones
    seccion = st.radio(
        "📂 Ver sección:",
        ["Resumen General", "Precipitaciones", "Aire y termica", "Tabla Detallada"]
    )
    
    st.markdown("---")
    
    # 3. Selección de Modelo (solo si no es Resumen General)
    df_lote = cargar_datos(lote_sel)
    mod_sel = None
    if not df_lote.empty and seccion != "Resumen General":
        modelos = sorted(df_lote['modelo_nombre'].unique())
        mod_sel = st.selectbox("🤖 Modelo de pronóstico", modelos)

# --- CUERPO PRINCIPAL ---
if not df_lote.empty:
    st.header(f"{lote_sel}")
    dias_disp = sorted(df_lote['fecha_pronosticada'].dt.date.unique())

    # --- LÓGICA DE SECCIONES ---
    
    if seccion == "Resumen General":
        st.subheader("📊 Comparativa de Precipitaciones (Todos los Modelos)")
        
        # Recuperamos las pestañas para el resumen
        nombres_tabs_comp = ["Toda la Semana"] + [nombre_dia_es(d) for d in dias_disp]
        tabs_comp = st.tabs(nombres_tabs_comp)

        with tabs_comp[0]:
            fig_total = px.bar(df_lote, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                            barmode='group', height=400, color_discrete_map=MAPA_COLORES,
                            title="Pronóstico Semanal Agrupado")
            st.plotly_chart(config_estatico(fig_total), use_container_width=True, key="resumen_semanal_total")

        for i, fecha in enumerate(dias_disp):
            with tabs_comp[i+1]:
                df_f = df_lote[df_lote['fecha_pronosticada'].dt.date == fecha]
                fig_dia = px.bar(df_f, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                                barmode='group', height=350, title=f"Comparativa: {nombre_dia_es(fecha)}",
                                color_discrete_map=MAPA_COLORES)
                st.plotly_chart(config_estatico(fig_dia), use_container_width=True, key=f"resumen_dia_{fecha.strftime('%Y%m%d')}")

    elif seccion == "Precipitaciones":
        st.subheader(f"🌧️ Detalle de Lluvia: {mod_sel}")
        tabs = st.tabs([nombre_dia_es(d) for d in dias_disp])
        for i, tab in enumerate(tabs):
            with tab:
                fecha_str = dias_disp[i].strftime('%Y%m%d')
                df_dia = df_lote[(df_lote['modelo_nombre'] == mod_sel) & (df_lote['fecha_pronosticada'].dt.date == dias_disp[i])]
                st.metric("Total Acumulado", f"{df_dia['lluvia_mm'].sum():.1f} mm")
                fig = px.bar(df_dia, x='fecha_pronosticada', y='lluvia_mm', 
                            color_discrete_sequence=['#00CC96'],
                            title=f"Lluvia estimada - {mod_sel}")
                st.plotly_chart(config_estatico(fig), use_container_width=True, key=f"solo_lluvia_{mod_sel}_{fecha_str}")

    elif seccion == "Aire y termica": # SECCIÓN UNIFICADA
        st.subheader(f"🌬️ Condiciones de Aire y Térmicas: {mod_sel}")
        tabs = st.tabs([nombre_dia_es(d) for d in dias_disp])
        for i, tab in enumerate(tabs):
            with tab:
                fecha_str = dias_disp[i].strftime('%Y%m%d')
                df_dia = df_lote[(df_lote['modelo_nombre'] == mod_sel) & (df_lote['fecha_pronosticada'].dt.date == dias_disp[i])].copy()
                
                # Métricas rápidas
                m1, m2, m3 = st.columns(3)
                m1.metric("Máx T°", f"{df_dia['temp_c'].max():.1f}°")
                m2.metric("Mín T°", f"{df_dia['temp_c'].min():.1f}°")
                m3.metric("Viento Máx", f"{df_dia['viento_ms'].max():.1f} m/s")

                # Gráfico de Viento
                fig_v = px.line(df_dia, x='fecha_pronosticada', y='viento_ms', title="Velocidad del Viento (m/s)",
                                color_discrete_sequence=['#AB63FA'])
                st.plotly_chart(config_estatico(fig_v), use_container_width=True, key=f"viento_unif_{mod_sel}_{fecha_str}")

                # Gráfico de Temp vs Rocío (El de las barras de colores)
                st.markdown("---")
                st.write("**Delta T (Inversión Térmica)**")
                df_dia['dif'] = df_dia['temp_c'] - df_dia['punto_rocio_c']
                fig_t = go.Figure()
                for _, r in df_dia.iterrows():
                    color = "#ff4b4b" if r['dif'] < 4 else ("#f9d71c" if r['dif'] < 8 else "#00cc96")
                    fig_t.add_shape(type="line", x0=r['fecha_pronosticada'], x1=r['fecha_pronosticada'],
                                y0=r['punto_rocio_c'], y1=r['temp_c'], line=dict(color=color, width=4))
                
                fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['temp_c'], name='Temp', line=dict(color='red', width=3)))
                fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['punto_rocio_c'], name='Rocío', line=dict(color='cyan', width=3)))
                fig_t.update_layout(height=350, legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(config_estatico(fig_t), use_container_width=True, key=f"rocio_unif_{mod_sel}_{fecha_str}")

    elif seccion == "Tabla Detallada":
        st.subheader(f"📋 Datos Horarios: {mod_sel}")
        tabs = st.tabs([nombre_dia_es(d) for d in dias_disp])
        for i, tab in enumerate(tabs):
            with tab:
                df_dia = df_lote[(df_lote['modelo_nombre'] == mod_sel) & (df_lote['fecha_pronosticada'].dt.date == dias_disp[i])].copy()
                df_dia['Dir'] = df_dia['viento_dir_deg'].apply(grados_a_direccion)
                df_dia['Hora'] = df_dia['fecha_pronosticada'].dt.strftime('%H:%M')
                cols = ['Hora', 'temp_c', 'punto_rocio_c', 'humedad_relativa', 'viento_ms', 'Dir', 'lluvia_mm']
                st.dataframe(df_dia[cols].rename(columns={
                    'temp_c': 'T°C', 'punto_rocio_c': 'Rocío', 'humedad_relativa': 'H%', 'viento_ms': 'V.m/s'
                }), hide_index=True, use_container_width=True)

else:
    st.warning("No hay datos disponibles para el lote seleccionado.")
