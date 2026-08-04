import sys, time
sys.path.insert(0, "app/services")
from futbol_service import get_jugadores_partido

print("Primera consulta...")
inicio = time.time()
r1, e1 = get_jugadores_partido("Deportivo Cuenca", "Emelec")
print(f"Tiempo: {time.time()-inicio:.1f}s | Error: {e1}")
if r1:
    equipos = list(r1.get("equipos", {}).keys())
    print("Equipos:", equipos)
    for eq in equipos:
        print(f"  {eq}: {len(r1['equipos'][eq]['jugadores'])} jugadores")

print()
print("Segunda consulta (deberia usar cache)...")
inicio = time.time()
r2, e2 = get_jugadores_partido("Deportivo Cuenca", "Emelec")
print(f"Tiempo: {time.time()-inicio:.1f}s | Error: {e2}")
