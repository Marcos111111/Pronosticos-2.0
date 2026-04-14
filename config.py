# config.py

# Lista de lotes/campos a monitorear
# El nombre debe ser único, ya que se usa para identificar el campo en la base de datos.
CAMPOS = [
    {
        "nombre": "Elida", 
        "lat": -34.030491, 
        "lon": -63.202952
    },
    {
        "nombre": "Magliano", 
        "lat": -34.243984, 
        "lon": -63.398968
    },
    {
        "nombre": "Chañar", 
        "lat": -34.534439, 
        "lon": -63.618381
    },
    {
        "nombre": "Gomez", 
        "lat": -34.105827, 
        "lon": -63.429345
    },
    {
        "nombre": "Serrano", 
        "lat": -34.470862, 
        "lon": -63.538062
    }
]

# Configuración global del sistema (opcional para el futuro)
SETTINGS = {
    "db_name": "monitoreo_agricola.db",
    "timezone": "America/Argentina/Buenos_Aires",
    "smn_dias_pronostico": 4
}