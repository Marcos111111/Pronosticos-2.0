import sqlite3
import os

# Ruta a tu base de datos
DB_PATH = "monitoreo_agricola.db"

def purgar_datos_viejos():
    if not os.path.exists(DB_PATH):
        print("La base de datos no existe.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Encontrar la fecha de la última consulta global
        cursor.execute("SELECT MAX(fecha_consulta) FROM pronosticos_full")
        ultima_fecha = cursor.fetchone()[0]

        if ultima_fecha:
            print(f"Última consulta detectada: {ultima_fecha}")
            
            # 2. Borrar todo lo que NO sea esa fecha
            cursor.execute("DELETE FROM pronosticos_full WHERE fecha_consulta < ?", (ultima_fecha,))
            filas_borradas = cursor.rowcount
            
            # 3. COMPACTAR el archivo (vital para que baje el peso en MB)
            cursor.execute("VACUUM")
            
            conn.commit()
            print(f"✅ Limpieza completada. Se eliminaron {filas_borradas} registros viejos.")
        else:
            print("No se encontraron registros para borrar.")

    except Exception as e:
        print(f"❌ Error durante la purga: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    purgar_datos_viejos()