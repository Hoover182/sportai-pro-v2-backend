with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "def obtener_jugadores_partido(fixture_id, liga_id, temporada):"
new = "def obtener_jugadores_partido(fixture_id, liga_id, temporada, nombre_local=None, nombre_visitante=None):"

if old in content:
    content = content.replace(old, new, 1)
    print("OK: firma actualizada")
else:
    print("ERROR firma")

old2 = "          if home_id:\n              equipos_info.append({\"id\": home_id, \"nombre\": home_name})\n          if away_id:\n              equipos_info.append({\"id\": away_id, \"nombre\": away_name})"
new2 = "          if home_id:\n              equipos_info.append({\"id\": home_id, \"nombre\": nombre_local or home_name})\n          if away_id:\n              equipos_info.append({\"id\": away_id, \"nombre\": nombre_visitante or away_name})"

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: nombres reemplazados por los del CSV")
else:
    print("ERROR nombres")

with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
