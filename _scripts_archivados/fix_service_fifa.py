with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "    goles_a, goles_b, corners_a, corners_b, tarjetas = ajustar_medias_con_rival(\n        stats_a, stats_b, h2h\n    )"
new = "    goles_a, goles_b, corners_a, corners_b, tarjetas = ajustar_medias_con_rival(\n        stats_a, stats_b, h2h, equipo_local=local, equipo_visitante=visitante\n    )"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK")
else:
    print("ERROR: patron no encontrado")
    idx = content.find("ajustar_medias_con_rival(")
    print(repr(content[idx:idx+150]))
