# db_manager.py
import sqlite3
from models import Campo, ForecastData

class DatabaseManager:
    def __init__(self, db_path="monitoreo_agricola.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Crea las tablas necesarias si no existen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de campos (Lotes)
        cursor.execute('''CREATE TABLE IF NOT EXISTS campos (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            nombre TEXT UNIQUE NOT NULL
                        )''')
        
        # Tabla de modelos (Para saber qué ID es cada uno)
        cursor.execute('''CREATE TABLE IF NOT EXISTS modelos (
                            id INTEGER PRIMARY KEY,
                            nombre TEXT UNIQUE NOT NULL
                        )''')
        
        # Insertar modelos por defecto si no existen
        cursor.executemany("INSERT OR IGNORE INTO modelos (id, nombre) VALUES (?, ?)", 
                           [(1, 'OpenMeteo'), (2, 'MET_Norway'), (3, 'GFS'), (4, 'SMN_WRF')])

        # Tabla de pronósticos (El "Big Data" del proyecto)
        cursor.execute('''CREATE TABLE IF NOT EXISTS pronosticos_full (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            campo_id INTEGER,
                            modelo_id INTEGER,
                            fecha_pronosticada TEXT,
                            dias_antelacion INTEGER,
                            temp_c REAL,
                            punto_rocio_c REAL,
                            humedad_relativa REAL,
                            viento_ms REAL,
                            viento_dir_deg INTEGER,
                            lluvia_mm REAL,
                            presion_hpa REAL,
                            fecha_consulta TEXT,
                            FOREIGN KEY (campo_id) REFERENCES campos (id),
                            FOREIGN KEY (modelo_id) REFERENCES modelos (id)
                        )''')
        conn.commit()
        conn.close()

    def sincronizar_campos(self, lista_diccionarios) -> list[Campo]:
        """
        Toma la lista de CAMPOS de config.py y asegura que existan en la DB.
        Retorna una lista de objetos de la clase Campo.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        campos_objetos = []

        for lote in lista_diccionarios:
            # Buscamos por nombre
            cursor.execute("SELECT id FROM campos WHERE nombre = ?", (lote['nombre'],))
            resultado = cursor.fetchone()
            
            if resultado:
                c_id = resultado[0]
            else:
                # Si no existe, lo creamos
                cursor.execute("INSERT INTO campos (nombre) VALUES (?)", (lote['nombre'],))
                conn.commit()
                c_id = cursor.lastrowid
                print(f"🌱 [DB] Nuevo lote detectado y registrado: {lote['nombre']}")
            
            # Creamos el objeto Campo con la data de la DB + coordenadas de config.py
            campos_objetos.append(Campo(
                id_db=c_id, 
                nombre=lote['nombre'], 
                lat=float(lote['lat']), 
                lon=float(lote['lon'])
            ))
            
        conn.close()
        return campos_objetos

    def guardar_pronosticos(self, pronosticos: list[ForecastData]):
        """Guarda masivamente una lista de objetos ForecastData."""
        if not pronosticos:
            print("⚠️ [DB] Sin datos para guardar.")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = """INSERT INTO pronosticos_full 
                 (campo_id, modelo_id, fecha_pronosticada, dias_antelacion, 
                  temp_c, punto_rocio_c, humedad_relativa, viento_ms, 
                  viento_dir_deg, lluvia_mm, presion_hpa, fecha_consulta) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        
        # Usamos el método to_tuple() que definimos en models.py
        datos_insert = [p.to_tuple() for p in pronosticos]
        
        try:
            # Borramos pronósticos viejos del mismo modelo para no duplicar si re-ejecutamos el mismo día
            # (Opcional: podrías preferir acumular todo, pero esto limpia la visualización)
            # cursor.execute("DELETE FROM pronosticos_full WHERE modelo_id = ?", (pronosticos[0].modelo_id,))
            
            cursor.executemany(sql, datos_insert)
            conn.commit()
            print(f"✅ [DB] Éxito: {len(datos_insert)} registros guardados.")
        except Exception as e:
            print(f"❌ [DB] Error en la inserción masiva: {e}")
        finally:
            conn.close()