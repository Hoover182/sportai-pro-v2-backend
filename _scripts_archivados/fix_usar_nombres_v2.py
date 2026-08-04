with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''        if home_id:
            equipos_info.append({"id": home_id, "nombre": home_name})
        if away_id:
            equipos_info.append({"id": away_id, "nombre": away_name})'''

new = '''        if home_id:
            equipos_info.append({"id": home_id, "nombre": nombre_local or home_name})
        if away_id:
            equipos_info.append({"id": away_id, "nombre": nombre_visitante or away_name})'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: nombres reemplazados por los del CSV")
else:
    print("ERROR: aun no coincide")
