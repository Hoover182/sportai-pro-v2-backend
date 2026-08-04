with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "        data = obtener_jugadores_partido(fixture_id, liga_id, temporada)"
new = "        data = obtener_jugadores_partido(fixture_id, liga_id, temporada, nombre_local=local, nombre_visitante=visitante)"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: llamada actualizada")
else:
    print("ERROR: no encontrado")
