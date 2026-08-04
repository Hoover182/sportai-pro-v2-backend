with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=None):"

new = '''def _cache_path_fixture_players(fixture_id):
    return os.path.join(CACHE_JUGADORES_DIR, f"fixture_{fixture_id}_players.json")


def obtener_stats_jugadores_fixture(fixture_id):
    """Devuelve las estadisticas reales de todos los jugadores de un partido especifico."""
    path = _cache_path_fixture_players(fixture_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = api_get("fixtures/players", params={"fixture": fixture_id})
    response = data.get("response", [])
    try:
        os.makedirs(CACHE_JUGADORES_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(response, f)
    except Exception:
        pass
    return response


def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    """Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]"""
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        for equipo in datos_fixture:
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if nombre.lower() != nombre_jugador.lower():
                    continue
                stats = j.get("statistics", [{}])[0] if j.get("statistics") else {}
                shots = stats.get("shots", {}) or {}
                goals = stats.get("goals", {}) or {}
                cards = stats.get("cards", {}) or {}
                resultado.append({
                    "fixture_id": fid,
                    "tiros_total": shots.get("total"),
                    "tiros_arco": shots.get("on"),
                    "goles": goals.get("total"),
                    "asistencias": goals.get("assists"),
                    "tarjetas_amarillas": cards.get("yellow"),
                    "minutos": (stats.get("games", {}) or {}).get("minutes"),
                })
    return resultado


def obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=None):'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: funciones de historial por partido agregadas")
else:
    print("ERROR: no encontrado")
