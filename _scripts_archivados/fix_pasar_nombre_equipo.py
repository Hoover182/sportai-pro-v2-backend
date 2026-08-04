with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "squad = obtener_squad_equipo(team_id, liga_id, temporada)"
new = "squad = obtener_squad_equipo(team_id, liga_id, temporada, nombre_equipo=nombre_equipo)"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: nombre_equipo pasado a la funcion")
else:
    print("ERROR: no encontrado")
