with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '        team_id = data_team["response"][0]["team"]["id"]'

new = '''        LIGA_PAIS = {
            "Liga Profesional Argentina": "Argentina", "Brasileirao": "Brazil",
            "Brasileirao Serie A": "Brazil", "Liga Colombia": "Colombia",
            "Primera Division Chile": "Chile", "Primera Division Uruguay": "Uruguay",
            "Primera Division Peru": "Peru", "Liga Pro Ecuador": "Ecuador",
            "Primera Division Venezuela": "Venezuela", "Primera Division Bolivia": "Bolivia",
            "Division Profesional Paraguay": "Paraguay", "Liga MX": "Mexico", "MLS": "USA",
            "Copa Argentina": "Argentina", "Copa Chile": "Chile", "Copa Colombia": "Colombia",
            "Copa Uruguay": "Uruguay", "Copa do Brasil": "Brazil",
        }
        pais_esperado = LIGA_PAIS.get(liga)
        candidatos_team = data_team["response"]
        team_id = None
        if pais_esperado:
            for c in candidatos_team:
                if c["team"]["country"] == pais_esperado:
                    team_id = c["team"]["id"]
                    break
        if team_id is None:
            team_id = candidatos_team[0]["team"]["id"]'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: filtro de pais agregado a get_historial_jugador")
else:
    print("ERROR: no encontrado")
