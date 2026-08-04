import sys
sys.path.insert(0, "app/services")
from player_model import obtener_historial_jugador

fixture_ids = [1505468, 1567687, 1544484, 1544437, 1544469]
historial = obtener_historial_jugador("Jeyson Rojas", fixture_ids, n=5)
print("Historial de Jeyson Rojas:")
for h in historial:
    print(" ", h)
