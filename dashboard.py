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

# --- CUERPO PRINCIPAL ---
if not df_lote.empty:
    st.header(f"{lote_sel}")
    dias_disp = sorted(df_lote['fecha_pronosticada'].dt.date.unique())

    # --- LÓGICA DE SECCIONES ---
    
    if seccion == "Resumen General":
        st.subheader("📊 Comparativa de Precipitaciones")
        
        # 1. Preparación de datos de promedio
        # Promedio por hora/fecha (lo que se ve en el gráfico)
        df_prom_hora = df_lote.groupby('fecha_pronosticada')['lluvia_mm'].mean().reset_index()
        # Promedio acumulado diario (para las métricas)
        df_lote['fecha_solo_dia'] = df_lote['fecha_pronosticada'].dt.date
        df_prom_dia = df_lote.groupby('fecha_solo_dia')['lluvia_mm'].mean().reset_index()

        # --- TABS DEL RESUMEN ---
        nombres_tabs_comp = ["Toda la Semana", "Tendencia (Promedio)"] + [nombre_dia_es(d) for d in dias_disp]
        tabs_comp = st.tabs(nombres_tabs_comp)

        # TAB 1: La comparativa de barras que ya tenías
        with tabs_comp[0]:
            fig_total = px.bar(df_lote, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                            barmode='group', height=400, color_discrete_map=MAPA_COLORES)
            st.plotly_chart(config_estatico(fig_total), use_container_width=True, key="resumen_barras")

        # TAB 2: EL NUEVO GRÁFICO DE PROMEDIO (CONSENSO)
        with tabs_comp[1]:
            st.markdown("#### 📅 Promedio por dia")
            
            # 1. Calculamos el acumulado por modelo por día
            df_diario_modelos = df_lote.groupby(['fecha_solo_dia', 'modelo_nombre'])['lluvia_mm'].sum().reset_index()
            
            # 2. Calculamos el promedio de esos acumulados por día
            df_consenso_diario = df_diario_modelos.groupby('fecha_solo_dia')['lluvia_mm'].mean().reset_index()

            # Gráfico de barras simples para el consenso diario
            fig_cons = px.bar(df_consenso_diario, 
                            x='fecha_solo_dia', 
                            y='lluvia_mm',
                            title="Lluvia Total Promedio por Día",
                            labels={'lluvia_mm': 'Milímetros (Promedio)', 'fecha_solo_dia': 'Día'},
                            text_auto='.1f') # Muestra el numerito arriba de la barra
            
            fig_cons.update_traces(marker_color='#00CC96', marker_line_color='white', marker_line_width=1, opacity=0.8)
            
            # Ajustamos el eje X para que muestre los nombres de los días
            fig_cons.update_layout(
                xaxis=dict(
                    tickmode='array',
                    tickvals=df_consenso_diario['fecha_solo_dia'],
                    ticktext=[nombre_dia_es(d) for d in df_consenso_diario['fecha_solo_dia']]
                )
            )
            
            st.plotly_chart(config_estatico(fig_cons), use_container_width=True, key="resumen_consenso_diario")

            # Métricas de resumen debajo
            c1, c2, c3 = st.columns(3)
            total_semana = df_consenso_diario['lluvia_mm'].sum()
            max_valor = df_consenso_diario['lluvia_mm'].max()
            dia_max = df_consenso_diario.loc[df_consenso_diario['lluvia_mm'].idxmax(), 'fecha_solo_dia']

            c1.metric("Acumulado Semanal", f"{total_semana:.1f} mm")
            c2.metric("Día más lluvioso", nombre_dia_es(dia_max))
            c3.metric("Máximo esperado", f"{max_valor:.1f} mm")

            # EL RESTO DE TABS (Días individuales)
            for i, fecha in enumerate(dias_disp):
                with tabs_comp[i+2]: # +2 porque agregamos "Tendencia" al principio
                    df_f = df_lote[df_lote['fecha_pronosticada'].dt.date == fecha]
                    fig_dia = px.bar(df_f, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                                    barmode='group', height=350, color_discrete_map=MAPA_COLORES)
                    st.plotly_chart(config_estatico(fig_dia), use_container_width=True, key=f"resumen_dia_{fecha.strftime('%Y%m%d')}")
    else:
        # --- PARA LAS DEMÁS SECCIONES (Precipitaciones, Aire y térmica, Tabla) ---
        modelos = sorted(df_lote['modelo_nombre'].unique())
        
        # 1. PESTAÑAS DE MODELOS (Nivel Superior)
        tabs_modelos = st.tabs([f" {m}" for m in modelos])

        for m_idx, m_tab in enumerate(tabs_modelos):
            with m_tab:
                modelo_actual = modelos[m_idx]
                
                # 2. PESTAÑAS DE DÍAS (Nivel Inferior, dentro de cada modelo)
                tabs_dias = st.tabs([nombre_dia_es(d) for d in dias_disp])
                
                for d_idx, d_tab in enumerate(tabs_dias):
                    with d_tab:
                        dia_actual = dias_disp[d_idx]
                        fecha_str = dia_actual.strftime('%Y%m%d')
                        
                        # Filtramos los datos para este modelo y este día
                        df_dia = df_lote[(df_lote['modelo_nombre'] == modelo_actual) & 
                                        (df_lote['fecha_pronosticada'].dt.date == dia_actual)].copy()

                        if df_dia.empty:
                            st.info("No hay datos para este día.")
                            continue

                        if seccion == "Precipitaciones":
                            st.metric("Total Acumulado", f"{df_dia['lluvia_mm'].sum():.1f} mm")
                            fig = px.bar(df_dia, x='fecha_pronosticada', y='lluvia_mm', 
                                     color_discrete_sequence=['#00CC96'],
                                     title=f"Lluvia: {modelo_actual} - {nombre_dia_es(dia_actual)}")
                            st.plotly_chart(config_estatico(fig), use_container_width=True, key=f"ll_{modelo_actual}_{fecha_str}")
        
                        elif seccion == "Aire y termica": # SECCIÓN UNIFICADA
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Máx T°", f"{df_dia['temp_c'].max():.1f}°")
                            m2.metric("Mín T°", f"{df_dia['temp_c'].min():.1f}°")
                            m3.metric("Viento Máx", f"{df_dia['viento_ms'].max():.1f} m/s")

                            fig_v = px.line(df_dia, x='fecha_pronosticada', y='viento_ms', 
                                            color_discrete_sequence=['#AB63FA'])
                            st.plotly_chart(config_estatico(fig_v), use_container_width=True, key=f"v_{modelo_actual}_{fecha_str}")

                            st.markdown("---")
                            df_dia['dif'] = df_dia['temp_c'] - df_dia['punto_rocio_c']
                            fig_t = go.Figure()
                            for _, r in df_dia.iterrows():
                                color = "#ff4b4b" if r['dif'] < 4 else ("#f9d71c" if r['dif'] < 8 else "#00cc96")
                                fig_t.add_shape(type="line", x0=r['fecha_pronosticada'], x1=r['fecha_pronosticada'],
                                            y0=r['punto_rocio_c'], y1=r['temp_c'], line=dict(color=color, width=4))
                            fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['temp_c'], name='T', line=dict(color='red')))
                            fig_t.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['punto_rocio_c'], name='R', line=dict(color='cyan')))
                            st.plotly_chart(config_estatico(fig_t), use_container_width=True, key=f"t_{modelo_actual}_{fecha_str}")
                        elif seccion == "Tabla Detallada":
                            df_dia['Dir'] = df_dia['viento_dir_deg'].apply(grados_a_direccion)
                            df_dia['Hora'] = df_dia['fecha_pronosticada'].dt.strftime('%H:%M')
                            cols = ['Hora', 'temp_c', 'punto_rocio_c', 'humedad_relativa', 'viento_ms', 'Dir', 'lluvia_mm']
                            st.dataframe(df_dia[cols].rename(columns={'temp_c': 'T°C', 'punto_rocio_c': 'Rocío', 'humedad_relativa': 'H%'}), 
                                        hide_index=True, use_container_width=True)

else:
    st.warning("No hay datos disponibles para el lote seleccionado.")
