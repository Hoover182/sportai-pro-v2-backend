with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''        resp_fixtures = _requests.get(
            f"{_PM_BASE_URL}/fixtures", headers=headers,
            params={"team": team_id, "season": temporada, "last": n}
        )
        data_fixtures = resp_fixtures.json()
        fixture_ids = [f["fixture"]["id"] for f in data_fixtures.get("response", [])]
        if not fixture_ids:
            return [], None

        historial = obtener_historial_jugador(jugador_nombre, fixture_ids, n=n)
        return historial, None'''

new = '''        # Buscar un rango amplio de fixtures del equipo (no solo n), porque el
        # jugador puede no haber participado en varios partidos recientes
        # (lesion, suspension, no convocado). Se sigue buscando hacia atras
        # hasta encontrar n partidos REALES donde el jugador jugo.
        RANGO_BUSQUEDA = max(n * 4, 20)
        resp_fixtures = _requests.get(
            f"{_PM_BASE_URL}/fixtures", headers=headers,
            params={"team": team_id, "season": temporada, "last": RANGO_BUSQUEDA}
        )
        data_fixtures = resp_fixtures.json()
        fixture_ids = [f["fixture"]["id"] for f in data_fixtures.get("response", [])]
        if not fixture_ids:
            return [], None

        historial = obtener_historial_jugador(jugador_nombre, fixture_ids, n=n, rango_busqueda=RANGO_BUSQUEDA)
        return historial, None'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: rango de busqueda ampliado en futbol_service")
else:
    print("ERROR: no encontrado")
