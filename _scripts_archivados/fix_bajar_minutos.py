with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "MINUTOS_MIN_TEMPORADA = 200"
new = "MINUTOS_MIN_TEMPORADA = 90"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: minimo bajado a 90 minutos")
else:
    print("ERROR: no encontrado")
