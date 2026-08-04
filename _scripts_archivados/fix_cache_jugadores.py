with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def obtener_squad_equipo(team_id, liga_id, temporada):"

new = '''import os
import json
from datetime import datetime, timedelta

CACHE_JUGADORES_DIR = os.path.join(os.path.dirname(__file__), "cache_jugadores")
CACHE_DIAS_VALIDEZ = 3

def _cache_path(team_id, liga_id, temporada):
    os.makedirs(CACHE_JUGADORES_DIR, exist_ok=True)
    return os.path.join(CACHE_JUGADORES_DIR, f"team_{team_id}_{liga_id}_{temporada}.json")


def _leer_cache_jugadores(team_id, liga_id, temporada):
    path = _cache_path(team_id, liga_id, temporada)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fecha_guardado = datetime.fromisoformat(data["_fecha_cache"])
        if datetime.now() - fecha_guardado > timedelta(days=CACHE_DIAS_VALIDEZ):
            return None
        return data["response"]
    except Exception:
        return None


def _guardar_cache_jugadores(team_id, liga_id, temporada, response):
    path = _cache_path(team_id, liga_id, temporada)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_fecha_cache": datetime.now().isoformat(), "response": response}, f)
    except Exception:
        pass


def obtener_squad_equipo(team_id, liga_id, temporada):
    cacheado = _leer_cache_jugadores(team_id, liga_id, temporada)
    if cacheado is not None:
        return cacheado
    data = api_get("players", params={
        "team": team_id,
        "league": liga_id,
        "season": temporada
    })
    response = data.get("response", [])
    if response:
        _guardar_cache_jugadores(team_id, liga_id, temporada, response)
    return response'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: sistema de cache de jugadores agregado")
else:
    print("ERROR: no encontrado")
