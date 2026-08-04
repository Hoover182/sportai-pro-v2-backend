with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '"fuera_juego": games_stats.get("offsides"),'
new = '"fuera_juego": stats.get("offsides"),'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: ubicacion de offsides corregida")
else:
    print("ERROR: no encontrado")
