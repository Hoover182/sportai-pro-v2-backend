import sys, time
sys.path.insert(0, "app/services")
from futbol_service import get_jugadores_partido

inicio = time.time()
r, e = get_jugadores_partido("Deportivo Cuenca", "Emelec")
print(f"Tiempo: {time.time()-inicio:.1f}s | Error: {e}")
if r:
    for eq, datos in r.get("equipos", {}).items():
        print(f"  {eq}: {len(datos['jugadores'])} jugadores")
