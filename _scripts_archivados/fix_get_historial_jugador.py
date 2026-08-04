with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def get_jugadores_partido(local_input, visitante_input):
    """Devuelve jugadores agrupados por equipo: 5 atacantes y 5 defensivos por equipo."""
    from player_model import obtener_jugadores_partido, obtener_fixture_id'''

new = '''def get_historial_jugador(equipo_input, jugador_nombre, n=5):
    """Devuelve el desglose real (partido por partido) de un jugador especifico,
    buscando en los ultimos n partidos de su equipo."""
    import requests as _requests
    from player_model import obtener_historial_jugador, API_KEY as _PM_API_KEY, BASE_URL as _PM_BASE_URL

    df = cargar_df()
    if df.empty:
        return None, "No hay datos disponibles"
    equipo = obtener_equipo_por_nombre(df, equipo_input)
    if equipo is None:
        return None, f"Equipo no encontrado: {equipo_input}"

    try:
        liga_series = df[
            (df["equipo_local"] == equipo) | (df["equipo_visitante"] == equipo)
        ]["liga"]
        liga = liga_series.iloc[0] if not liga_series.empty else None
    except Exception:
        liga = None
    if not liga:
        return None, "Liga no encontrada"
    liga_id, temporada = get_temporada(liga)
    if not liga_id:
        return None, f"No se pudo resolver liga_id para {liga}"

    try:
        headers = {"x-apisports-key": _PM_API_KEY}
        resp_team = _requests.get(f"{_PM_BASE_URL}/teams", headers=headers, params={"search": equipo})
        data_team = resp_team.json()
        if not data_team.get("response"):
            return None, "Equipo no encontrado en la API"
        team_id = data_team["response"][0]["team"]["id"]

        resp_fixtures = _requests.get(
            f"{_PM_BASE_URL}/fixtures", headers=headers,
            params={"team": team_id, "season": temporada, "last": n}
        )
        data_fixtures = resp_fixtures.json()
        fixture_ids = [f["fixture"]["id"] for f in data_fixtures.get("response", [])]
        if not fixture_ids:
            return [], None

        historial = obtener_historial_jugador(jugador_nombre, fixture_ids, n=n)
        return historial, None
    except Exception as e:
        return None, str(e)


def get_jugadores_partido(local_input, visitante_input):
    """Devuelve jugadores agrupados por equipo: 5 atacantes y 5 defensivos por equipo."""
    from player_model import obtener_jugadores_partido, obtener_fixture_id'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: get_historial_jugador agregada")
else:
    print("ERROR: no encontrado")
