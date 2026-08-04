with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def obtener_squad_equipo(team_id, liga_id, temporada):\n    cacheado = _leer_cache_jugadores(team_id, liga_id, temporada)\n    if cacheado is not None:\n        return cacheado"

new = '''JUGADORES_DATA_DIR = os.path.join(os.path.dirname(__file__), "jugadores_data")

def _leer_jugadores_data_por_nombre(nombre_equipo):
    """Busca el archivo descargado masivamente por nombre de equipo."""
    path = os.path.join(JUGADORES_DATA_DIR, f"{nombre_equipo.replace('/', '_')}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("jugadores", [])
    except Exception:
        return None


def obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=None):
    if nombre_equipo:
        datos_masivos = _leer_jugadores_data_por_nombre(nombre_equipo)
        if datos_masivos:
            return datos_masivos
    cacheado = _leer_cache_jugadores(team_id, liga_id, temporada)
    if cacheado is not None:
        return cacheado'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funcion actualizada para usar jugadores_data primero")
else:
    print("ERROR: no encontrado")
