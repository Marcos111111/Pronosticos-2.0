# orquestador.py
import time
from config import CAMPOS
from db_manager import DatabaseManager
from providers import SMNProvider
from api_providers import OpenMeteoProvider, YRProvider, GFSProvider

def ejecutar_actualizacion():
    inicio_total = time.time()
    print("="*50)
    print("🚀 INICIANDO SISTEMA DE ACTUALIZACIÓN CLIMÁTICA")
    print("="*50)

    try:
        # 1. Inicializar la conexión a la base de datos
        # Al instanciarlo, se crean las tablas automáticamente si no existen
        db = DatabaseManager()

        # 2. Sincronizar campos (Punto 1 de tu pedido: Dinámico)
        # Si agregaste un lote en config.py, aquí se registra solo
        print(f"\n🔍 Verificando configuración de campos...")
        campos_procesar = db.sincronizar_campos(CAMPOS)
        print(f"✅ Campos activos para procesar: {len(campos_procesar)}")

        # 3. Configurar Proveedores
        # Podés agregar más modelos a esta lista en el futuro
        proveedores = [
            OpenMeteoProvider(dias=7),
            YRProvider(dias=7),
            GFSProvider(dias=7),
            SMNProvider(dias=4)
        ]   

        # 4. Ciclo de descarga y guardado
        for provider in proveedores:
            nombre_mod = provider.__class__.__name__
            print(f"\n📡 Iniciando descarga desde: {nombre_mod}")
            
            inicio_descarga = time.time()
            
            # Obtenemos la lista de objetos ForecastData
            datos = provider.get_forecast(campos_procesar)
            
            if datos:
                # Guardamos masivamente en la DB
                db.guardar_pronosticos(datos)
                fin_descarga = time.time()
                tiempo_mod = (fin_descarga - inicio_descarga) / 60
                print(f"⏱️ Tiempo {nombre_mod}: {tiempo_mod:.2f} minutos.")
            else:
                print(f"⚠️ {nombre_mod} no devolvió datos.")

        fin_total = time.time()
        print("\n" + "="*50)
        print(f"✨ PROCESO FINALIZADO CON ÉXITO")
        print(f"⏱️ Tiempo total de ejecución: {(fin_total - inicio_total)/60:.2f} minutos")
        print("="*50)

    except KeyboardInterrupt:
        print("\n\n🛑 Proceso cancelado por el usuario.")
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO EN EL ORQUESTADOR: {e}")

if __name__ == "__main__":
    ejecutar_actualizacion()