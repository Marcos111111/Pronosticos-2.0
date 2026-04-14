# api_providers.py
import requests
import datetime
from models import Campo, ForecastData
from providers import WeatherProvider

class OpenMeteoProvider(WeatherProvider):
    """
    Proveedor para Open-Meteo. 
    Permite obtener datos de varios modelos globales (GFS, ECMWF, MET Norway).
    """
    def __init__(self, dias=7):
        super().__init__(modelo_id=1) # ID 1 para OpenMeteo en tu DB
        self.dias = dias

    def get_forecast(self, campos: list[Campo]) -> list[ForecastData]:
        resultados = []
        ahora_local = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        str_consulta = ahora_local.strftime("%Y-%m-%d %H:%M")

        print(f"📡 [Open-Meteo] Consultando {len(campos)} campos...")

        for campo in campos:
            # Seteamos los parámetros para que nos devuelva m/s y Celsius
            # Usamos el modelo 'best_match' que combina lo mejor disponible
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": campo.lat,
                "longitude": campo.lon,
                "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,surface_pressure,wind_speed_10m",
                "wind_speed_unit": "ms",
                "timezone": "America/Sao_Paulo", # UTC-3 igual que Argentina
                "forecast_days": self.dias
            }

            try:
                response = requests.get(url, params=params)
                data = response.json()

                hourly = data["hourly"]
                tiempos = hourly["time"]

                for i in range(len(tiempos)):
                    fecha_p_dt = datetime.datetime.fromisoformat(tiempos[i])
                    str_fecha_p = fecha_p_dt.strftime("%Y-%m-%d %H:%M")
                    diff_dias = (fecha_p_dt.date() - ahora_local.date()).days

                    resultados.append(ForecastData(
                        campo_id=campo.id_db,
                        modelo_id=self.modelo_id,
                        fecha_pronosticada=str_fecha_p,
                        dias_antelacion=diff_dias,
                        temp_c=hourly["temperature_2m"][i],
                        punto_rocio_c=hourly["dew_point_2m"][i],
                        humedad_relativa=hourly["relative_humidity_2m"][i],
                        viento_ms=hourly["wind_speed_10m"][i],
                        viento_dir_deg=0,
                        lluvia_mm=hourly["precipitation"][i],
                        presion_hpa=hourly["surface_pressure"][i],
                        fecha_consulta=str_consulta
                    ))
            except Exception as e:
                print(f"⚠️ [Open-Meteo] Error en campo {campo.nombre}: {e}")
                continue

        return resultados

class YRProvider(WeatherProvider):
    """
    Proveedor oficial de MET Norway (api.met.no).
    """
    def __init__(self, dias=4):
        super().__init__(modelo_id=2)
        self.dias = dias
        # MET.no requiere un User-Agent identificable
        self.headers = {'User-Agent': 'MonitorAgricolaArgentina/1.0 vitorchelo@gmail.com'}

    def get_forecast(self, campos: list[Campo]) -> list[ForecastData]:
        resultados = []
        ahora = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        str_consulta = ahora.strftime("%Y-%m-%d %H:%M")
        
        # Límites de tiempo según tu función original
        inicio_hoy = ahora.replace(hour=0)
        limite_futuro = ahora + datetime.timedelta(days=self.dias)

        print(f"📡 [YR.no] Consultando API oficial para {len(campos)} campos...")

        for campo in campos:
            url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={campo.lat}&lon={campo.lon}"
            
            try:
                res = requests.get(url, headers=self.headers, timeout=15)
                res.raise_for_status()
                data_json = res.json()
                timeseries = data_json['properties']['timeseries']
                
                for ts in timeseries:
                    # Convertimos de UTC a Local (UTC-3)
                    fecha_dt = datetime.datetime.strptime(ts['time'], "%Y-%m-%dT%H:%M:%SZ") - datetime.timedelta(hours=3)
                    
                    if inicio_hoy <= fecha_dt <= limite_futuro:
                        data = ts.get('data', {})
                        det = data.get('instant', {}).get('details', {})
                        diff_dias = (fecha_dt.date() - ahora.date()).days
                        
                        # Extraemos la lluvia de la siguiente hora
                        lluvia = data.get('next_1_hours', {}).get('details', {}).get('precipitation_amount', 0)

                        resultados.append(ForecastData(
                            campo_id=campo.id_db,
                            modelo_id=self.modelo_id,
                            fecha_pronosticada=fecha_dt.strftime("%Y-%m-%d %H:%M"),
                            dias_antelacion=diff_dias,
                            temp_c=det.get('air_temperature'),
                            punto_rocio_c=det.get('dew_point_temperature'),
                            humedad_relativa=det.get('relative_humidity'),
                            viento_ms=det.get('wind_speed'), # Lo dejamos en m/s como pediste
                            viento_dir_deg=det.get('wind_from_direction'),
                            lluvia_mm=lluvia,
                            presion_hpa=det.get('air_pressure_at_sea_level'),
                            fecha_consulta=str_consulta
                        ))
                print(f"✅ [YR.no] {campo.nombre} procesado.")
            
            except Exception as e:
                print(f"⚠️ [YR.no] Error en {campo.nombre}: {e}")
                continue
        
        return resultados

class GFSProvider(WeatherProvider):
    """
    Proveedor para el modelo GFS (Global Forecast System) de la NOAA.
    """
    def __init__(self, dias=10):
        super().__init__(modelo_id=3) # Usaremos el ID 3 para GFS
        self.dias = dias

    def get_forecast(self, campos: list[Campo]) -> list[ForecastData]:
        resultados = []
        ahora_local = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        str_consulta = ahora_local.strftime("%Y-%m-%d %H:%M")

        print(f"📡 [GFS] Consultando {len(campos)} campos...")

        for campo in campos:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": campo.lat,
                "longitude": campo.lon,
                "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,surface_pressure,wind_speed_10m",
                "wind_speed_unit": "ms",
                "models": "gfs_seamless", # Usamos la versión seamless de GFS
                "timezone": "America/Sao_Paulo",
                "forecast_days": self.dias
            }

            try:
                response = requests.get(url, params=params)
                data = response.json()
                hourly = data["hourly"]
                
                for i in range(len(hourly["time"])):
                    fecha_p_dt = datetime.datetime.fromisoformat(hourly["time"][i])
                    resultados.append(ForecastData(
                        campo_id=campo.id_db,
                        modelo_id=self.modelo_id,
                        fecha_pronosticada=fecha_p_dt.strftime("%Y-%m-%d %H:%M"),
                        dias_antelacion=(fecha_p_dt.date() - ahora_local.date()).days,
                        temp_c=hourly["temperature_2m"][i],
                        punto_rocio_c=hourly["dew_point_2m"][i],
                        humedad_relativa=hourly["relative_humidity_2m"][i],
                        viento_ms=hourly["wind_speed_10m"][i],
                        viento_dir_deg=0,
                        lluvia_mm=hourly["precipitation"][i],
                        presion_hpa=hourly["surface_pressure"][i],
                        fecha_consulta=str_consulta
                    ))
            except Exception as e:
                print(f"⚠️ [GFS] Error en campo {campo.nombre}: {e}")
        
        return resultados