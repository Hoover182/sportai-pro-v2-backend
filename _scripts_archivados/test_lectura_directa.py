import sys
sys.path.insert(0, "app/services")
from player_model import _leer_jugadores_data_por_nombre

datos = _leer_jugadores_data_por_nombre("Colo Colo")
print("Jugadores encontrados:", len(datos) if datos else "None/vacio")
