import sqlite3
import os

DB_PATH = "monitoreo_agricola.db"

def purgar_datos_viejos():
    if not os.path.exists(DB_PATH):
        print("La base de datos no existe.")
        return

    # Conectamos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Encontrar la fecha de la última consulta
        cursor.execute("SELECT MAX(fecha_consulta) FROM pronosticos_full")
        ultima_fecha = cursor.fetchone()[0]

        if ultima_fecha:
            print(f"Última consulta detectada: {ultima_fecha}")
            
            # 2. Borrar todo lo viejo
            cursor.execute("DELETE FROM pronosticos_full WHERE fecha_consulta < ?", (ultima_fecha,))
            filas_borradas = cursor.rowcount
            conn.commit() # Guardamos los cambios primero
            print(f"✅ Se eliminaron {filas_borradas} registros viejos.")
            
            # 3. VACUUM (Debe ejecutarse fuera de una transacción)
            # Cerramos la conexión y la volvemos a abrir en modo especial para limpiar
            conn.close()
            
            print("Iniciando compactación (VACUUM)...")
            conn_vacuum = sqlite3.connect(DB_PATH)
            conn_vacuum.execute("VACUUM")
            conn_vacuum.close()
            print("✅ Base de datos compactada con éxito.")
            
        else:
            print("No se encontraron registros.")
            conn.close()

    except Exception as e:
        print(f"❌ Error durante la purga: {e}")
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    purgar_datos_viejos()