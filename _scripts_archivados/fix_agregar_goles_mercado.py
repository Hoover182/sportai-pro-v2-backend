with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''                    "tiros_arco":  simular_jugador(j["_tiros_arco_media"],  [0.5, 1.5, 2.5, 3.5]),'''
new = '''                    "goles": simular_jugador(j["_goles_media"], [0.5, 1.5]),
                    "tiros_arco":  simular_jugador(j["_tiros_arco_media"],  [0.5, 1.5, 2.5, 3.5]),'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: mercado goles agregado a jugador_completo")
else:
    print("ERROR: no encontrado")
