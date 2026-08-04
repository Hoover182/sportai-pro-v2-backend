import sys
sys.path.insert(0, "app/services")
from futbol_service import cargar_df, obtener_equipo_por_nombre, get_temporada

df = cargar_df()
local = obtener_equipo_por_nombre(df, "Colo Colo")
visitante = obtener_equipo_por_nombre(df, "Palestino")
print("Nombre local resuelto:", repr(local))
print("Nombre visitante resuelto:", repr(visitante))
