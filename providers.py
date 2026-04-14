# providers.py
import datetime
import s3fs
import xarray as xr
import numpy as np
import cartopy.crs as ccrs
from abc import ABC, abstractmethod
from models import Campo, ForecastData

class WeatherProvider(ABC):
    """
    Clase base para cualquier modelo de pronóstico.
    """
    def __init__(self, modelo_id: int):
        self.modelo_id = modelo_id

    @abstractmethod
    def get_forecast(self, campos: list[Campo]) -> list[ForecastData]:
        """
        Debe ser implementado por cada proveedor para devolver 
        una lista de objetos ForecastData.
        """
        pass

class SMNProvider(WeatherProvider):
    """
    Proveedor de datos para el modelo WRF del SMN desde AWS S3.
    """
    def __init__(self, dias=4):
        super().__init__(modelo_id=4)
        self.dias = dias

    def get_forecast(self, campos: list[Campo]) -> list[ForecastData]:
        fs = s3fs.S3FileSystem(anon=True, client_kwargs={'region_name': 'us-west-2'})
        resultados = []
        horas_totales = self.dias * 24
        
        # 1. Búsqueda de la corrida más reciente
        ahora_utc = datetime.datetime.now(datetime.UTC)
        hora_ejecucion, fecha_final = None, None

        for delta_dias in [0, 1]:
            fecha_evaluar = ahora_utc - datetime.timedelta(days=delta_dias)
            ruta_dia = fecha_evaluar.strftime('%Y/%m/%d')
            for h in [18, 12, 6, 0]:
                test_path = f'smn-ar-wrf/DATA/WRF/DET/{ruta_dia}/{h:02d}/'
                # Verificamos si existe el primer archivo de la serie
                if fs.exists(f'{test_path}WRFDETAR_01H_{fecha_evaluar:%Y%m%d}_{h:02d}_001.nc'):
                    hora_ejecucion, fecha_final = h, fecha_evaluar
                    break
            if hora_ejecucion is not None: break

        if fecha_final is None:
            print("❌ [SMN] No se encontró ninguna corrida válida en AWS S3.")
            return []

        init_date = fecha_final.replace(hour=hora_ejecucion, minute=0, second=0, microsecond=0)
        print(f"📡 [SMN] Procesando corrida: {init_date.strftime('%d/%m/%Y %H:00')} UTC")
        
        ahora_local = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        str_consulta = ahora_local.strftime("%Y-%m-%d %H:%M")

        # Diccionario para controlar la lluvia acumulada por campo (ID_DB como clave)
        pp_acum_anterior = {campo.id_db: 0.0 for campo in campos}

        # 2. Bucle de archivos horarios
        for lt in range(1, horas_totales + 1):
            s3_path = f'smn-ar-wrf/DATA/WRF/DET/{init_date:%Y/%m/%d/%H}/WRFDETAR_01H_{init_date:%Y%m%d_%H}_{lt:03d}.nc'
            
            if not fs.exists(s3_path):
                continue

            try:
                with fs.open(s3_path) as f:
                    # Cargamos el dataset con h5netcdf para mayor compatibilidad
                    ds = xr.open_dataset(f, decode_coords='all', engine='h5netcdf')
                    
                    # Extraer parámetros de proyección Lambert
                    lc = ds['Lambert_Conformal'].attrs
                    data_crs = ccrs.LambertConformal(
                        central_longitude=float(lc['longitude_of_central_meridian']),
                        central_latitude=float(lc['latitude_of_projection_origin']),
                        standard_parallels=[float(x) for x in lc['standard_parallel']]
                    )

                    # Ajuste de tiempo (UTC a Local aproximado UTC-3)
                    fecha_p = init_date + datetime.timedelta(hours=lt - 3)
                    diff_dias = (fecha_p.date() - ahora_local.date()).days
                    str_fecha_p = fecha_p.strftime("%Y-%m-%d %H:%M")

                    for campo in campos:
                        # Transformar coordenadas y seleccionar punto
                        x_p, y_p = data_crs.transform_point(campo.lon, campo.lat, src_crs=ccrs.PlateCarree())
                        punto = ds.sel(dict(x=x_p, y=y_p), method='nearest')
                        
                        # Extraer variables físicas
                        temp = float(punto['T2'].values.item())
                        hum = float(punto['HR2'].values.item())
                        viento_ms = float(punto['magViento10'].values.item())
                        presion = float(punto['PSFC'].values.item())
                        
                        # Cálculo de Delta Lluvia (lluvia caída en esta hora específica)
                        pp_total_actual = float(punto['PP'].values.item())
                        lluvia_hora = max(0.0, pp_total_actual - pp_acum_anterior[campo.id_db])
                        pp_acum_anterior[campo.id_db] = pp_total_actual
                        
                        # Cálculo de Punto de Rocío (Fórmula de Magnus)
                        a, b = 17.27, 237.7
                        alpha = ((a * temp) / (b + temp)) + np.log(hum/100.0)
                        rocio = (b * alpha) / (a - alpha)

                        # Crear objeto de datos unificado
                        resultados.append(ForecastData(
                            campo_id=campo.id_db,
                            modelo_id=self.modelo_id,
                            fecha_pronosticada=str_fecha_p,
                            dias_antelacion=diff_dias,
                            temp_c=round(temp, 1),
                            punto_rocio_c=round(rocio, 1),
                            humedad_relativa=round(hum, 1),
                            viento_ms=round(viento_ms, 1),
                            viento_dir_deg=0, # No disponible en este extracto directo
                            lluvia_mm=round(lluvia_hora, 2),
                            presion_hpa=round(presion, 1),
                            fecha_consulta=str_consulta
                        ))
                
                if lt % 24 == 0:
                    print(f"✅ [SMN] Día {lt // 24} procesado...")

            except Exception as e:
                print(f"⚠️ [SMN] Error procesando hora {lt}: {e}")
                continue

        return resultados