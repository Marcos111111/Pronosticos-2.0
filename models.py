# models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Campo:
    """
    Representa un lote o ubicación geográfica.
    """
    id_db: int      # El ID que le asigna SQLite
    nombre: str    # Nombre identificador (ej: 'Elida')
    lat: float     # Latitud en formato decimal
    lon: float     # Longitud en formato decimal

@dataclass
class ForecastData:
    """
    Contenedor para un registro individual de pronóstico.
    Unifica los datos de cualquier modelo (SMN, OpenMeteo, etc.)
    """
    campo_id: int              # ID del campo al que pertenece
    modelo_id: int             # ID del modelo (ej: 4 para SMN)
    fecha_pronosticada: str    # Formato: 'YYYY-MM-DD HH:MM'
    dias_antelacion: int       # Diferencia entre fecha actual y pronosticada
    temp_c: float              # Temperatura en Celsius
    punto_rocio_c: float       # Punto de rocío en Celsius
    humedad_relativa: float    # Humedad en %
    viento_ms: float           # Velocidad del viento en METROS POR SEGUNDO
    viento_dir_deg: int        # Dirección en grados (0-360)
    lluvia_mm: float           # Precipitación de la hora en milímetros
    presion_hpa: float         # Presión atmosférica en hPa
    fecha_consulta: str        # Cuándo se ejecutó la descarga (Timestamp)

    def to_tuple(self):
        """Convierte el objeto en una tupla para facilitar el insert en SQLite"""
        return (
            self.campo_id,
            self.modelo_id,
            self.fecha_pronosticada,
            self.dias_antelacion,
            self.temp_c,
            self.punto_rocio_c,
            self.humedad_relativa,
            self.viento_ms,
            self.viento_dir_deg,
            self.lluvia_mm,
            self.presion_hpa,
            self.fecha_consulta
        )