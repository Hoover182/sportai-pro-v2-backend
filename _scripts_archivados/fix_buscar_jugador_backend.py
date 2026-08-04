with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def get_jugadores_partido(local_input, visitante_input):"

new = '''def buscar_jugador_general(query, limite=20):
    """Busca jugadores por nombre en los equipos ya descargados localmente.
    Devuelve lista de coincidencias con nombre, equipo, posicion y stats basicas."""
    import json as _json
    q = query.lower().strip()
    if len(q) < 2:
        return []

    resultados = []
    if not os.path.exists(JUGADORES_DATA_DIR):
        return []

    for archivo in os.listdir(JUGADORES_DATA_DIR):
        if not archivo.endswith(".json") or archivo.startswith("fixture_"):
            continue
        try:
            with open(os.path.join(JUGADORES_DATA_DIR, archivo), "r", encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            continue

        equipo_nombre = data.get("equipo", "")
        for jraw in data.get("jugadores", []):
            info = jraw.get("player", {})
            nombre = info.get("name", "")
            if q not in nombre.lower():
                continue
            stats_list = jraw.get("statistics", [])
            stats = stats_list[0] if stats_list else {}
            games = stats.get("games", {}) or {}
            resultados.append({
                "nombre": nombre,
                "equipo": equipo_nombre,
                "posicion": games.get("position", "") or "",
                "partidos": games.get("appearences", 0) or 0,
                "foto": info.get("photo", ""),
            })
            if len(resultados) >= limite:
                return resultados
    return resultados


def get_jugadores_partido(local_input, visitante_input):'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: buscar_jugador_general agregada")
else:
    print("ERROR: no encontrado")
