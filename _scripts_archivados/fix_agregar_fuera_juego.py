with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''                stats = j.get("statistics", [{}])[0] if j.get("statistics") else {}
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
                })'''

new = '''                stats = j.get("statistics", [{}])[0] if j.get("statistics") else {}
                shots = stats.get("shots", {}) or {}
                goals = stats.get("goals", {}) or {}
                cards = stats.get("cards", {}) or {}
                games_stats = stats.get("games", {}) or {}
                fouls = stats.get("fouls", {}) or {}
                resultado.append({
                    "fixture_id": fid,
                    "rival": rival,
                    "tiros_total": shots.get("total"),
                    "tiros_arco": shots.get("on"),
                    "goles": goals.get("total"),
                    "asistencias": goals.get("assists"),
                    "tarjetas_amarillas": cards.get("yellow"),
                    "fuera_juego": games_stats.get("offsides"),
                    "faltas": fouls.get("committed"),
                    "minutos": games_stats.get("minutes"),
                })'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: fuera_juego y faltas agregados al historial")
else:
    print("ERROR: no encontrado")
