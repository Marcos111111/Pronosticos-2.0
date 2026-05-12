import json
import os
import numpy as np
from datetime import datetime
import sqlite3
from config import CAMPOS

def agregar_modelo_consenso(series_por_modelo):
    modelos = list(series_por_modelo.keys())
    if len(modelos) < 2: return series_por_modelo
    
    # Usamos el modelo con más puntos como base
    ref_key = max(series_por_modelo, key=lambda k: len(series_por_modelo[k]))
    referencia = series_por_modelo[ref_key]
    consenso = []
    for i in range(len(referencia)):
        fecha = referencia[i]['x']
        puntos = [series_por_modelo[m][i] for m in modelos if i < len(series_por_modelo[m])]
        
        if not puntos: continue
        
        consenso.append({
            'x': fecha,
            'temp': round(sum(p['temp'] for p in puntos) / len(puntos), 1),
            'rocio': round(sum(p['rocio'] for p in puntos) / len(puntos), 1),
            'hum': round(sum(p['hum'] for p in puntos) / len(puntos), 0),
            'viento': round(sum(p['viento'] for p in puntos) / len(puntos), 1),
            'y': round(sum(p['y'] for p in puntos) / len(puntos), 1)
        })
    series_por_modelo['CONSENSO'] = consenso
    return series_por_modelo

def actualizar_json(db_path):
    # Crear carpeta si no existe
    if not os.path.exists('web/data'):
        os.makedirs('web/data')
    for campo in CAMPOS:
        nombre = campo['nombre']
        # Generamos un nombre de archivo seguro (ej: data/elida.json)
        archivo_nombre = f"web/data/{nombre.lower()}.json"
        
        # Llamamos a la función que creamos antes
        exportar_dashboard_v2(db_path, nombre, archivo_nombre)
    
    print(f"✅ Se han actualizado {len(CAMPOS)} archivos de pronóstico.")

def exportar_dashboard_v2(db_path, campo_nombre, output_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
        SELECT p.*, m.nombre as modelo_nombre
        FROM pronosticos_full p
        JOIN modelos m ON p.modelo_id = m.id
        JOIN campos c ON p.campo_id = c.id
        WHERE c.nombre = ? 
        -- Filtro 1: Solo datos desde hace 1 hora (por si querés ver el pasado inmediato) o desde YA
        AND p.fecha_pronosticada >= datetime('now', '-1 hour', 'localtime')
        -- Filtro 2: Asegurar que traemos solo la última versión de cada pronóstico
        AND p.id IN (
            SELECT MAX(id)
            FROM pronosticos_full
            GROUP BY campo_id, modelo_id, fecha_pronosticada
        )
        ORDER BY p.fecha_pronosticada ASC
        """
        
        cursor.execute(query, (campo_nombre,))
        filas = cursor.fetchall()
        
        if not filas:
            print(f"⚠️ Sin datos para: {campo_nombre}")
            return

        series_por_modelo = {}
        acumulados_diarios_por_modelo = {} 

        for r in filas:
            mod = r['modelo_nombre']
            fecha_str = r['fecha_pronosticada']
            dia = fecha_str.split(' ')[0]
            
            lluvia = float(r['lluvia_mm'] or 0)
            temp = float(r['temp_c'] or 0)
            rocio = float(r['punto_rocio_c'] or 0)
            viento = float(r['viento_ms'] or 0)
            hum = float(r['humedad_relativa'] or 0)

            if mod not in series_por_modelo:
                series_por_modelo[mod] = []
            
            series_por_modelo[mod].append({
                "x": fecha_str,
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

        # --- NUEVO: INYECTAR MODELO CONSENSO ---
        # Solo si tenemos al menos 2 modelos para promediar
        if len(series_por_modelo) > 1:
            series_por_modelo = agregar_modelo_consenso(series_por_modelo)

        # --- CÁLCULO DE MÉTRICAS DE RESUMEN ---
        lista_dias = sorted(acumulados_diarios_por_modelo.keys())
        labels_diarios = []
        valores_diarios = []

        for d in lista_dias:
            valores = list(acumulados_diarios_por_modelo[d].values())
            promedio_dia = np.mean(valores) if valores else 0
            fecha_dt = datetime.strptime(d, '%Y-%m-%d')
            labels_diarios.append(fecha_dt.strftime('%a %d'))
            valores_diarios.append(round(promedio_dia, 1))

        # --- CÁLCULO DE CERTEZA ---
        # Excluimos 'CONSENSO' del cálculo de certeza para no sesgar el desvío estándar
        modelos_reales = [m for m in series_por_modelo.keys() if m != 'CONSENSO']
        totales_semanales = [sum(pt['y'] for pt in series_por_modelo[mod]) for mod in modelos_reales]
        
        certeza = 100
        if len(totales_semanales) > 1 and np.mean(totales_semanales) > 0:
            cv = np.std(totales_semanales) / np.mean(totales_semanales)
            certeza = int(max(0, 100 - (cv * 100)))

        # --- ENSAMBLADO FINAL ---
        json_final = {
            "metadata": {
                "lote": campo_nombre,
                "actualizado": datetime.now().strftime("%d/%m %H:%M"),
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