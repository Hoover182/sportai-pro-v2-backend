import sys
sys.path.insert(0, "app/services")
from player_model import obtener_stats_jugadores_fixture
import json

datos = obtener_stats_jugadores_fixture(1535299)  # fixture vs Cruzeiro
for equipo in datos:
    if equipo.get("team", {}).get("name") == "Boca Juniors":
        for j in equipo.get("players", []):
            nombre = j.get("player", {}).get("name", "")
            if "erentiel" in nombre.lower():
                stats = j.get("statistics", [{}])[0]
                print(json.dumps(stats, indent=2, ensure_ascii=False))
