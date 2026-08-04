import json
import os

CACHE_DIR = "app/services/jugadores_data"
vacios = []

for archivo in os.listdir(CACHE_DIR):
    if not archivo.endswith(".json") or archivo.startswith("fixture_"):
        continue
    try:
        with open(os.path.join(CACHE_DIR, archivo), "r", encoding="utf-8") as f:
            data = json.load(f)
        if len(data.get("jugadores", [])) == 0:
            vacios.append(archivo)
    except Exception as e:
        print(f"Error leyendo {archivo}: {e}")

print(f"Archivos con 0 jugadores: {len(vacios)}")
for v in vacios:
    print(" ", v)
