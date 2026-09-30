import json
import os
from datetime import timezone
import numpy as np
from datetime import datetime, timedelta
import sqlite3
from config import CAMPOS

def agregar_modelo_consenso(series_por_modelo):
    # Nombres exactos de los modelos a promediar
    modelos_deseados = ['OpenMeteo', 'MET_Norway']
    
    # 1. Filtrar asegurando coincidencia exacta (case-insensitive por si acaso)
    modelos_filtrados = [
        k for k in series_por_modelo.keys() 
        if k in modelos_deseados
    ]
    
    # Si no están los 2 modelos presentes, no calculamos consenso
    if len(modelos_filtrados) < 2:
        print("⚠️ No se encontraron los 2 modelos requeridos para el consenso.")
        return series_por_modelo

    # 2. Agrupar por fecha/timestamp 'x' solo de los modelos filtrados
    puntos_por_fecha = {}
    for mod in modelos_filtrados:
        for punto in series_por_modelo[mod]:
            fecha = punto['x']
            if fecha not in puntos_por_fecha:
                puntos_por_fecha[fecha] = []
            puntos_por_fecha[fecha].append(punto)

    consenso = []
    
    # 3. Promediar SOLO si ambos modelos tienen dato en esa fecha/hora
    for fecha, puntos in sorted(puntos_por_fecha.items()):
        if len(puntos) == 2:  # Solo si están OpenMeteo Y MET_Norway exactos
            consenso.append({
                'x': fecha,
                'temp': round(sum(p['temp'] for p in puntos) / 2.0, 1),
                'rocio': round(sum(p['rocio'] for p in puntos) / 2.0, 1),
                'hum': round(sum(p['hum'] for p in puntos) / 2.0, 0),
                'viento': round(sum(p['viento'] for p in puntos) / 2.0, 1),
                'y': round(sum(p.get('y', 0) for p in puntos) / 2.0, 1)
            })

    # 4. Asignar el nuevo consenso
    series_por_modelo['CONSENSO'] = consenso
    print(f"✅ Consenso generado con {len(consenso)} puntos de datos.")
    
    return series_por_modelo

def actualizar_json(db_path):
    if not os.path.exists('web/data'):
        os.makedirs('web/data')
    for campo in CAMPOS:
        nombre = campo['nombre']
        archivo_nombre = f"web/data/{nombre.lower()}.json"
        exportar_dashboard_v2(db_path, nombre, archivo_nombre)
    
    print(f"✅ Se han actualizado {len(CAMPOS)} archivos de pronóstico.")

def exportar_dashboard_v2(db_path, campo_nombre, output_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- CORRECCIÓN DE ZONA HORARIA Y FILTRO DE INICIO ---
        ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        ahora_arg = ahora_utc - timedelta(hours=3)

        # 1. Creamos el piso de HOY a las 00:00:00 en hora de Argentina
        inicio_hoy_arg = ahora_arg.replace(hour=0, minute=0, second=0, microsecond=0)

        # 2. Lo pasamos a UTC (+3 horas) para consultar la base de datos correctamente
        inicio_hoy_utc = inicio_hoy_arg + timedelta(hours=3)
        filtro_desde_utc = inicio_hoy_utc.strftime('%Y-%m-%d %H:%M:%S')

        query = """
        SELECT p.*, m.nombre as modelo_nombre
        FROM pronosticos_full p
        JOIN modelos m ON p.modelo_id = m.id
        JOIN campos c ON p.campo_id = c.id
        WHERE c.nombre = ? 
        -- Filtramos para que solo traiga fechas pronosticadas desde hoy en adelante
        AND p.fecha_pronosticada >= ?
        AND p.id IN (
            SELECT MAX(id)
            FROM pronosticos_full
            GROUP BY campo_id, modelo_id, fecha_pronosticada
        )
        ORDER BY p.fecha_pronosticada ASC
        """
        
        # Pasamos el nuevo filtro_desde_utc a la query
        cursor.execute(query, (campo_nombre, filtro_desde_utc))
        filas = cursor.fetchall()
        
        if not filas:
            print(f"⚠️ Sin datos para: {campo_nombre}")
            return

        series_por_modelo = {}
        acumulados_diarios_por_modelo = {} 

        for r in filas:
            mod = r['modelo_nombre']
            fecha_str_utc = r['fecha_pronosticada']
            
            # --- CONVERSIÓN A HORA LOCAL ---
            try:
                dt_utc = datetime.strptime(fecha_str_utc, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                dt_utc = datetime.strptime(fecha_str_utc, '%Y-%m-%d %H:%M')
            dt_arg = dt_utc - timedelta(hours=3)
            fecha_str_local = dt_arg.strftime('%Y-%m-%d %H:%M:%S')
            
            dia = fecha_str_local.split(' ')[0]
            
            lluvia = float(r['lluvia_mm'] or 0)
            temp = float(r['temp_c'] or 0)
            rocio = float(r['punto_rocio_c'] or 0)
            viento = float(r['viento_ms'] or 0)
            hum = float(r['humedad_relativa'] or 0)

            if mod not in series_por_modelo:
                series_por_modelo[mod] = []
            
            series_por_modelo[mod].append({
                "x": fecha_str_local,
                "y": lluvia,
                "temp": temp,
                "rocio": rocio,
                "viento": viento,
                "hum": hum
            })

            if dia not in acumulados_diarios_por_modelo:
                acumulados_diarios_por_modelo[dia] = {}
            if mod not in acumulados_diarios_por_modelo[dia]:
                acumulados_diarios_por_modelo[dia][mod] = 0
            
            acumulados_diarios_por_modelo[dia][mod] += lluvia

        if len(series_por_modelo) > 1:
            series_por_modelo = agregar_modelo_consenso(series_por_modelo)

        lista_dias = sorted(acumulados_diarios_por_modelo.keys())
        labels_diarios = []
        valores_diarios = []

        for d in lista_dias:
            valores = list(acumulados_diarios_por_modelo[d].values())
            promedio_dia = np.mean(valores) if valores else 0
            fecha_dt = datetime.strptime(d, '%Y-%m-%d')
            labels_diarios.append(fecha_dt.strftime('%a %d'))
            valores_diarios.append(round(promedio_dia, 1))

        modelos_reales = [m for m in series_por_modelo.keys() if m != 'CONSENSO']
        totales_semanales = [sum(pt['y'] for pt in series_por_modelo[mod]) for mod in modelos_reales]
        
        certeza = 100
        if len(totales_semanales) > 1 and np.mean(totales_semanales) > 0:
            cv = np.std(totales_semanales) / np.mean(totales_semanales)
            certeza = int(max(0, 100 - (cv * 100)))

        json_final = {
            "metadata": {
                "lote": campo_nombre,
                "actualizado": ahora_arg.strftime("%d/%m %H:%M"),
                "total_semana": round(sum(valores_diarios), 1),
                "certeza": certeza
            },
            "diario": {
                "labels": labels_diarios,
                "data": valores_diarios
            },
            "horario": series_por_modelo
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_final, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON con CONSENSO generado: {output_path}")

    except Exception as e:
        print(f"❌ Error procesando {campo_nombre}: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    actualizar_json("monitoreo_agricola.db")