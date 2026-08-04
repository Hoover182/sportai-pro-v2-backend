with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    \"\"\"Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]\"\"\"
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        for equipo in datos_fixture:
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if not _nombres_coinciden(nombre, nombre_jugador):
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
    return resultado"""

new = """def obtener_historial_jugador(nombre_jugador, fixture_ids, n=5):
    \"\"\"Busca el desglose real de un jugador especifico en una lista de fixture_ids.
    Devuelve lista de dicts: [{fixture_id, rival, tiros_total, tiros_arco, goles, asistencias, tarjetas_amarillas}, ...]\"\"\"
    resultado = []
    for fid in fixture_ids[:n]:
        datos_fixture = obtener_stats_jugadores_fixture(fid)
        nombres_equipos = [eq.get("team", {}).get("name", "") for eq in datos_fixture]
        for equipo in datos_fixture:
            equipo_jugador = equipo.get("team", {}).get("name", "")
            rival = next((n for n in nombres_equipos if n != equipo_jugador), "")
            for j in equipo.get("players", []):
                nombre = j.get("player", {}).get("name", "")
                if not _nombres_coinciden(nombre, nombre_jugador):
                    continue
                stats = j.get("statistics", [{}])[0] if j.get("statistics") else {}
                shots = stats.get("shots", {}) or {}
                goals = stats.get("goals", {}) or {}
                cards = stats.get("cards", {}) or {}
                resultado.append({
                    "fixture_id": fid,
                    "rival": rival,
                    "tiros_total": shots.get("total"),
                    "tiros_arco": shots.get("on"),
                    "goles": goals.get("total"),
                    "asistencias": goals.get("assists"),
                    "tarjetas_amarillas": cards.get("yellow"),
                    "minutos": (stats.get("games", {}) or {}).get("minutes"),
                })
    return resultado"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: rival agregado al historial")
else:
    print("ERROR: no encontrado")
