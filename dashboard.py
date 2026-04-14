import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitoreo Agrícola v2.0", layout="wide", initial_sidebar_state="expanded")

# Estilo para mejorar visualización
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stDataFrame { font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE APOYO ---

def fecha_en_español(fecha):
    meses = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    return f"{dias[fecha.weekday()]} {fecha.day} de {meses[fecha.month - 1]}"

def grados_a_direccion(grados):
    if grados is None or pd.isna(grados) or grados == 0: return "-"
    direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return direcciones[int((grados + 22.5) % 360 // 45)]

def cargar_datos_completos(lote_nombre):
    conn = sqlite3.connect("monitoreo_agricola.db")
    query = """
    SELECT p.*, m.nombre as modelo_nombre, c.nombre as campo_nombre
    FROM pronosticos_full p
    JOIN modelos m ON p.modelo_id = m.id
    JOIN campos c ON p.campo_id = c.id
    WHERE c.nombre = ?
    AND p.fecha_consulta = (SELECT MAX(fecha_consulta) FROM pronosticos_full WHERE campo_id = c.id)
    ORDER BY p.fecha_pronosticada ASC
    """
    try:
        df = pd.read_sql_query(query, conn, params=(lote_nombre,))
        if not df.empty:
            df['fecha_pronosticada'] = pd.to_datetime(df['fecha_pronosticada'])
        return df
    except Exception as e:
        st.error(f"Error DB: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuración")

# Obtener nombres de lotes de la DB
conn = sqlite3.connect("monitoreo_agricola.db")
lotes_disponibles = pd.read_sql("SELECT nombre FROM campos", conn)['nombre'].tolist()
conn.close()

lote_sel = st.sidebar.selectbox("Seleccioná el Lote", lotes_disponibles)

# Cargar datos una sola vez
df_lote = cargar_datos_completos(lote_sel)

# Switch para el gráfico comparativo
ver_comparativo = st.sidebar.toggle("Ver Comparativa de Modelos", value=False)

if not df_lote.empty:
    modelos_nombres = df_lote['modelo_nombre'].unique()
    mod_sel = st.sidebar.radio("Modelo Principal (Detalle)", options=modelos_nombres)

    # --- NAVEGACIÓN DIARIA ---
    dias_disponibles = sorted(df_lote['fecha_pronosticada'].dt.date.unique())
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Navegación")
    
    dia_elegido = st.sidebar.select_slider(
        "Cambiar día:", 
        options=dias_disponibles,
        format_func=lambda x: x.strftime("%d/%m (Hoy)") if x == dias_disponibles[0] else x.strftime("%d/%m")
    )

    # Filtrar para la vista detallada
    df_dia = df_lote[(df_lote['modelo_nombre'] == mod_sel) & (df_lote['fecha_pronosticada'].dt.date == dia_elegido)].copy()

    # --- TÍTULO PRINCIPAL ---
    st.title("📊 Panel Meteorológico")
    
    # --- SECCIÓN COMPARATIVA (Opcional) ---
    # --- SECCIÓN COMPARATIVA (Opcional) ---
    if ver_comparativo:
        st.subheader("🔍 Comparativa Multi-Modelo (Toda la semana)")
        
        # 1. Gráfico de Temperaturas
        fig_comp_t = px.line(df_lote, x='fecha_pronosticada', y='temp_c', color='modelo_nombre',
                          title="Evolución de Temperatura (°C)",
                          labels={'temp_c': 'T°C', 'fecha_pronosticada': 'Fecha', 'modelo_nombre': 'Modelo'})
        fig_comp_t.update_layout(template="plotly_dark", height=350, hovermode="x unified", margin=dict(b=0))
        st.plotly_chart(fig_comp_t, use_container_width=True)

        # 2. NUEVO: Gráfico de Precipitaciones Comparativo
        # Filtramos modelos que tengan al menos algo de lluvia para no ensuciar el gráfico
        df_lluvia = df_lote[df_lote['lluvia_mm'] >= 0] 
        
        fig_comp_ll = px.bar(df_lluvia, x='fecha_pronosticada', y='lluvia_mm', color='modelo_nombre',
                           title="Comparativa de Precipitaciones (mm por hora)",
                           barmode='group', # Las barras se ponen una al lado de la otra para comparar la misma hora
                           labels={'lluvia_mm': 'Lluvia (mm)', 'fecha_pronosticada': 'Fecha', 'modelo_nombre': 'Modelo'})
        
        fig_comp_ll.update_layout(template="plotly_dark", height=350, hovermode="x unified", 
                                 legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_comp_ll, use_container_width=True)
        
        st.markdown("---")

    # --- VISTA DETALLADA DEL DÍA ---
    c1, c2 = st.columns([3, 1])
    with c1:
        st.subheader(f"📅 {fecha_en_español(dia_elegido)}")
    with c2:
        st.info(f"**Lote:** {lote_sel} | **Modelo:** {mod_sel}")

    # --- GRÁFICO T° vs ROCÍO (Con Alertas Delta T) ---
    st.subheader("🌡️ Temperatura vs Punto de Rocío")
    df_dia['dif'] = df_dia['temp_c'] - df_dia['punto_rocio_c']
    
    fig_temp = go.Figure()

    for _, row in df_dia.iterrows():
        # Lógica de color Delta T (Diferencia T - Rocío)
        color_l = "red" if row['dif'] < 4 else ("yellow" if row['dif'] < 8 else "green")
        fig_temp.add_shape(type="line", x0=row['fecha_pronosticada'], x1=row['fecha_pronosticada'],
                           y0=row['punto_rocio_c'], y1=row['temp_c'],
                           line=dict(color=color_l, width=4), layer="below")

    fig_temp.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['temp_c'], name='Temp C', 
                                 line=dict(color='#ff5757', width=3), mode='lines+markers'))
    fig_temp.add_trace(go.Scatter(x=df_dia['fecha_pronosticada'], y=df_dia['punto_rocio_c'], name='Rocío C', 
                                 line=dict(color='#3ac0ff', width=3), mode='lines+markers'))

    fig_temp.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=20, b=20),
                          legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    st.plotly_chart(fig_temp, use_container_width=True, config={'displayModeBar': False})

    # --- LLUVIA Y VIENTO ---
    col_lluvia, col_viento = st.columns(2)
    
    with col_lluvia:
        total_lluvia = df_dia['lluvia_mm'].sum()
        if total_lluvia > 0:
            fig_ll = px.bar(df_dia, x='fecha_pronosticada', y='lluvia_mm', title=f"Precipitación: {total_lluvia:.1f}mm",
                            color_discrete_sequence=['#00CC96'])
            fig_ll.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig_ll, use_container_width=True)
        else:
            st.success("✅ Sin lluvias previstas para este día")

    with col_viento:
        v_max = df_dia['viento_ms'].max()
        fig_v = px.line(df_dia, x='fecha_pronosticada', y='viento_ms', title=f"Viento Máx: {v_max} m/s",
                        color_discrete_sequence=['#AB63FA'])
        fig_v.update_layout(template="plotly_dark", height=300)
        st.plotly_chart(fig_v, use_container_width=True)

    # --- TABLA DETALLADA ---
    with st.expander("🔍 Ver Tabla de Datos Horaria"):
        df_tab = df_dia.copy()
        df_tab['Dir'] = df_tab['viento_dir_deg'].apply(grados_a_direccion)
        df_tab['Hora'] = df_tab['fecha_pronosticada'].dt.strftime('%H:%M')
        
        cols = {'Hora': 'Hora', 'temp_c': 'T°C', 'punto_rocio_c': 'Rocío', 
                'humedad_relativa': 'H %', 'viento_ms': 'V. m/s', 'Dir': 'Dir', 
                'lluvia_mm': 'Lluvia', 'presion_hpa': 'Presión'}
        st.dataframe(df_tab[cols.keys()].rename(columns=cols), hide_index=True, use_container_width=True)

else:
    st.warning("No hay datos cargados para este lote.")
    st.info("Asegurate de correr el orquestador.py")