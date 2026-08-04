with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# LOCAL: agregar campo liga_partido
old_l = '"tarjetas_favor_2t": int(r["tarjetas_local_2t"] if es_local else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,'
new_l = '"tarjetas_favor_2t": int(r["tarjetas_local_2t"] if es_local else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,\n                  "liga_partido": str(r["liga"]) if "liga" in r.index else "",'

# VISITANTE: igual
old_v = '"tarjetas_favor_2t": int(r["tarjetas_local_2t"] if r["equipo_local"] == visitante else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,'
new_v = '"tarjetas_favor_2t": int(r["tarjetas_local_2t"] if r["equipo_local"] == visitante else r["tarjetas_visitante_2t"]) if "tarjetas_local_2t" in r.index and str(r["tarjetas_local_2t"]) not in ["nan","None"] else None,\n                "liga_partido": str(r["liga"]) if "liga" in r.index else "",'

cambios = 0
if old_l in content:
    content = content.replace(old_l, new_l, 1)
    cambios += 1
    print("OK: liga_partido local")
else:
    print("ERROR local")

if old_v in content:
    content = content.replace(old_v, new_v, 1)
    cambios += 1
    print("OK: liga_partido visitante")
else:
    print("ERROR visitante")

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("Total: " + str(cambios) + "/2")
