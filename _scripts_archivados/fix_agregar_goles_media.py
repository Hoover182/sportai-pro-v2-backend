with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '"_tiros_arco_media":  max(tiros_arco_pg,  0.1),'
new = '"_goles_media": max(goles_pg, 0.05),\n        "_tiros_arco_media":  max(tiros_arco_pg,  0.1),'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/player_model.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: _goles_media agregado")
else:
    print("ERROR: no encontrado")
